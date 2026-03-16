# src/agents/semanticist.py
# The Brownfield Cartographer


import logging
from pathlib import Path
from typing import Any, Dict

import ollama
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity

from src.models.models import ModuleNode

logging.basicConfig(level=logging.INFO)


class ContextWindowBudget:
    """Tracks token usage and enforces tiered model selection."""

    def __init__(self, max_tokens: int = 100000):
        self.max_tokens = max_tokens
        self.used_tokens = 0

    def estimate_tokens(self, text: str) -> int:
        return len(text.split())

    def reserve(self, text: str) -> bool:
        tokens = self.estimate_tokens(text)
        if self.used_tokens + tokens > self.max_tokens:
            return False
        self.used_tokens += tokens
        return True


class Semanticist:
    """
    Phase 3 agent:
    - Generates purpose statements (from code first, docstrings fallback)
    - Detects doc drift
    - Clusters modules into domains
    - Synthesises answers to Five Day-One Questions
    """

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.purpose_statements: Dict[str, str] = {}
        self.doc_drift_flags: Dict[str, bool] = {}
        self.domain_clusters: Dict[str, str] = {}
        self.context_budget = ContextWindowBudget()

    def _select_model(self, heavy: bool = False) -> str:
        return "gemma:2b" if heavy else "Qwen2.5:3B"

    def _run_model(self, model: str, prompt: str, max_tokens: int = 300) -> str:
        """
        Run the LLM with improved sanitisation and logging.
        Ensures valid answers are not stripped and provides transparency.
        """

        def _sanitise_output(text: str) -> str:
            if not text:
                return ""

            # Only strip preambles if they are at the start
            preambles = [
                "Sure, here is a concise purpose statement for this module:",
                "Sure, here's a concise purpose statement for the code:",
                "Sure, here is a concise purpose statement for the module:",
                "Sure, here is the concise purpose statement for the module:",
                "Sure, here's the purpose statement:",
                "Sure, here's a concise purpose statement for the module:",
                "Sure, here's the concise purpose statement:",
                "Here is a concise purpose statement:",
                "Sure, here is the concise purpose statement for the module:",
            ]

            for p in preambles:
                if text.startswith(p):
                    text = text[len(p) :].lstrip()

            # Strip markdown artifacts but preserve line breaks
            text = text.replace("**", "").replace("```", "")

            # Do NOT collapse whitespace — just trim leading/trailing spaces
            return text.strip()

        try:
            response = ollama.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                options={"num_predict": max_tokens},
            )
            raw = response["message"]["content"].strip()

            # Debug logging
            logging.info(f"[LLM Raw Output]: {raw if raw else '(Empty)'}")
            sanitised = _sanitise_output(raw)
            logging.info(
                f"[LLM Sanitised Output]: {sanitised if sanitised else '(Empty after sanitisation)'}"
            )
            return sanitised
            # return raw
        except Exception as e:
            logging.error(f"Ollama call failed for model {model}: {e}")
            return ""

    def _semantic_similarity(self, text1: str, text2: str) -> float:
        """
        Compute semantic similarity between two texts using embeddings.
        """
        try:
            # Use Ollama or another embedding model
            emb1 = ollama.embeddings(model="gemma:2b", prompt=text2)["embedding"]
            emb2 = ollama.embeddings(model="Qwen2.5:3B", prompt=text1)["embedding"]
            return cosine_similarity([emb1], [emb2])[0][0]
        except Exception as e:
            logging.error(f"Embedding similarity failed: {e}")
            return 0.0

    def generate_purpose_statement(self, module_node: ModuleNode) -> str:
        """
        Generate a concise purpose statement for a module.
        Uses lightweight model for small modules, escalates to heavy model for complex ones.
        Also detects semantic drift against docstrings.
        """
        code = (module_node.attrs.get("code") or "").strip()
        docstring = (module_node.attrs.get("docstring") or "").strip()
        extra_docstrings = module_node.attrs.get("function_docstrings") or {}

        if not self.context_budget.reserve(code):
            logging.warning(f"Skipping {module_node.path} due to budget.")
            return ""

        # Decide model based on complexity
        code_length = len(code.split())
        heavy_needed = code_length > 500 or len(docstring.split()) > 100
        model_choice = "Qwen2.5:3B" if heavy_needed else self._select_model(False)

        # Generate from code
        prompt = (
            "Return only a concise purpose statement for this module. "
            "Focus on its business function, not implementation detail. "
            "Do not include preambles, markdown, or formatting. "
            "Limit to 2-3 sentences.\n\n"
            f"Code:\n{code[:1500]}"
        )
        statement = self._run_model(model_choice, prompt, 400)

        # Normalise path
        norm_path = self._normalise_path(module_node.path)
        statement = (statement or "").strip()
        self.purpose_statements[norm_path] = statement
        module_node.purpose_statement = statement

        # Semantic drift detection
        drift_flag = False
        if docstring or extra_docstrings:
            combined_docs = docstring + "\n" + "\n".join(extra_docstrings.values())
            similarity = self._semantic_similarity(statement, combined_docs)
            if similarity < 0.7:  # threshold can be tuned
                drift_flag = True
        self.doc_drift_flags[norm_path] = drift_flag

        # Debug transparency
        logging.info(
            f"[Purpose] Generated for {norm_path} using {'heavy' if heavy_needed else 'light'} model."
        )
        logging.info(f"[Purpose] Drift flag: {drift_flag}")

        return statement

    def cluster_into_domains(self):
        """
        Cluster modules into business domains using embeddings + KMeans.
        Logs when fallback vectors are used to highlight degraded cluster quality.
        Uses heavy reasoning model for labeling clusters.
        """
        texts = list(self.purpose_statements.values())
        if not texts:
            logging.warning("[Cluster] No purpose statements available to cluster.")
            return

        embeddings = []
        fallback_count = 0
        for text in texts:
            try:
                emb = ollama.embeddings(model="glm-5:cloud", prompt=text)["embedding"]
                embeddings.append(emb)
            except Exception as e:
                logging.error(
                    f"[Cluster] Embedding failed for text: {text[:50]}... Error: {e}"
                )
                embeddings.append([0] * 768)  # fallback vector
                fallback_count += 1

        if fallback_count > 0:
            logging.warning(
                f"[Cluster] {fallback_count} modules used fallback vectors. Cluster quality may be degraded."
            )

        # Enforce k between 5 and 8
        k = min(8, max(5, len(texts)))
        km = KMeans(n_clusters=k, random_state=42)
        km.fit(embeddings)

        # Assign provisional domain labels
        for i, module in enumerate(self.purpose_statements.keys()):
            self.domain_clusters[module] = f"Domain-{km.labels_[i]}"

        # Label clusters with LLM
        for cluster_id in set(km.labels_):
            cluster_texts = [
                text for i, text in enumerate(texts) if km.labels_[i] == cluster_id
            ][:10]
            prompt = (
                "Return only a short, clean business domain name for this cluster. "
                "Do not include preambles, markdown, or formatting. "
                "Examples: 'Data Ingestion', 'Reporting', 'Configuration'.\n\n"
                f"Module summaries:\n{cluster_texts}"
            )
            label = self._run_model("Qwen2.5:3B", prompt, 50).strip()
            if not label:
                label = f"Domain-{cluster_id} (Unlabeled)"
                logging.warning(
                    f"[Cluster] LLM failed to label cluster {cluster_id}, using fallback label."
                )
            for i, module in enumerate(self.purpose_statements.keys()):
                if km.labels_[i] == cluster_id:
                    self.domain_clusters[module] = label

        logging.info(f"[Cluster] Completed clustering into {k} domains.")

    def _normalise_path(self, path: str) -> str:
        """
        Ensure consistent path formatting across Windows/Linux and lowercase.
        """
        return path.replace("\\", "/").strip().lower()

    def _build_day_one_prompt(self, evidence: Dict[str, Any]) -> str:
        """
        Build a directive prompt for Day-One Questions.
        Explicitly instructs the LLM to interpret evidence into business insights.
        Formats outputs clearly with degrees and pagerank variance.
        """
        # Format critical outputs with degree counts
        critical_outputs_fmt = [
            f"{s} (degree {d})" for s, d in evidence["critical_outputs"]
        ]
        # Format pagerank with values
        pagerank_fmt = [f"{m} (score {v:.6f})" for m, v in evidence["top_pagerank"]]
        # Compute pagerank variance
        pagerank_values = [v for _, v in evidence["top_pagerank"]]
        variance = max(pagerank_values, default=0) - min(pagerank_values, default=0)

        return f"""
        You are an expert software cartographer. Use the following preprocessed evidence to answer the Five FDE Day-One Questions.

        Evidence Summary:
        - Ingestion Nodes (Singer taps feeding downstream): {evidence['ingestion_nodes']}
        - Critical Outputs (Singer targets ranked by degree): {critical_outputs_fmt}
        - Top Business Logic Modules (Python in src/meltano/core, ranked by pagerank): {pagerank_fmt}
        (Pagerank variance: {variance:.6f})
        - Velocity Hotspots (recently changed production .py files): {evidence['hotspots']}
        - Dead Code Summary: {evidence['dead_code_summary']}
        - Blast Radius (structural impact from module graph): {evidence['blast_radius']['structural']}
        - Blast Radius (dataflow impact from lineage graph): {evidence['blast_radius']['dataflow']}

        Answer concisely and directly. Do not just list evidence; interpret it into business insights.
        Provide short, clear analysis for each question, highlighting risks, dependencies, and areas of concentration.
        """

    def answer_day_one_questions(
        self, surveyor_output: Dict[str, Any], hydrologist_output: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Synthesise answers to the Five Day-One Questions using Surveyor + Hydrologist outputs.
        Preprocesses evidence to filter noise and highlight the most relevant signals.
        Always uses the heavy reasoning model (Qwen2.5:3B) for synthesis.
        Includes debug prints for transparency.
        Returns day_one_answers as a list of sections for readability.
        """
        # --- Ingestion nodes ---
        edges = hydrologist_output.get("edges", [])
        sources = hydrologist_output.get("sources", [])
        active_taps = {e["source"] for e in edges if e["source"].startswith("tap-")}
        ingestion_nodes = [
            s for s in sources if s.startswith("tap-") and s in active_taps
        ]
        if not ingestion_nodes:
            ingestion_nodes = [s for s in sources if s.startswith("tap-")]
        ingestion_nodes = [
            n for n in ingestion_nodes if "test" not in n and "yml" not in n
        ]

        # --- Critical outputs ---
        sinks = hydrologist_output.get("sinks", [])
        sink_counts = {}
        for e in edges:
            tgt = e["target"]
            if tgt.startswith("target-"):
                sink_counts[tgt] = sink_counts.get(tgt, 0) + 1
        critical_targets = sorted(
            sink_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]
        if not critical_targets and sinks:
            critical_targets = [(s, 0) for s in sinks if s.startswith("target-")][:5]

        # --- Pagerank ---
        pagerank = surveyor_output.get("pagerank", {})
        code_modules = {
            self._normalise_path(k): v
            for k, v in pagerank.items()
            if k.endswith(".py") and "src/meltano/core" in k
        }
        top_pagerank = sorted(code_modules.items(), key=lambda x: x[1], reverse=True)[
            :5
        ]

        # --- Velocity ---
        velocity = surveyor_output.get("velocity", {})
        hotspots = [
            self._normalise_path(h)
            for h in velocity.get("hotspots", [])
            if h.endswith(".py") and "src/meltano/" in h
        ][:5]
        dead_code_summary = velocity.get("dead_code_summary", {})

        # --- Blast radius ---
        module_blast = surveyor_output.get("blast_radius", {})
        lineage_blast = hydrologist_output.get("blast_radius", {})
        module_blast = {self._normalise_path(k): v for k, v in module_blast.items()}
        lineage_blast = {self._normalise_path(k): v for k, v in lineage_blast.items()}
        top_module_blast = [
            (k, v)
            for k, v in sorted(module_blast.items(), key=lambda x: x[1], reverse=True)
            if "src/meltano/core" in k
            and not k.endswith(".yml")
            and "tests/" not in k
            and ".github/" not in k
        ][:5]
        top_lineage_blast = sorted(
            lineage_blast.items(), key=lambda x: x[1], reverse=True
        )[:5]
        blast_radius = {
            "structural": top_module_blast,
            "dataflow": top_lineage_blast,
        }

        evidence = {
            "ingestion_nodes": ingestion_nodes,
            "critical_outputs": critical_targets,
            "top_pagerank": top_pagerank,
            "hotspots": hotspots,
            "dead_code_summary": dead_code_summary,
            "blast_radius": blast_radius,
        }

        # Debug transparency
        logging.info(f"[Evidence] Ingestion taps: {len(ingestion_nodes)}")
        logging.info(f"[Evidence] Critical outputs: {critical_targets}")
        logging.info(
            f"[Evidence] Pagerank variance: {max(code_modules.values(), default=0) - min(code_modules.values(), default=0)}"
        )
        logging.info(f"[Evidence] Hotspots: {hotspots}")
        logging.info(f"[Evidence] Blast radius structural top: {top_module_blast}")
        logging.info(f"[Evidence] Blast radius dataflow top: {top_lineage_blast}")

        # --- Build prompt ---
        prompt = self._build_day_one_prompt(evidence)

        # --- Run model with heavy reasoning model forced ---
        answers = self._run_model("Qwen2.5:3B", prompt, 600)

        # --- Fallback ---
        if "cannot answer" in answers.lower() or not answers.strip():
            answers = f"""
            1. Primary ingestion: {ingestion_nodes or "No ingestion nodes detected"}
            2. Critical outputs: {critical_targets or "No critical outputs detected"}
            3. Blast radius (structural): {blast_radius['structural'] or "No structural blast radius data"}
            Blast radius (dataflow): {blast_radius['dataflow'] or "No dataflow blast radius data"}
            4. Business logic concentration: {top_pagerank or "No pagerank data"}
            5. Frequent changes: {hotspots or "No hotspots"}; Dead code: {dead_code_summary}
            """

        # --- Split answers into sections for readability ---
        answers_sections = [
            section.strip()
            for section in answers.strip().split("\n###")
            if section.strip()
        ]
        # Prepend "###" back to each section except the first if needed
        answers_sections = [
            s if s.startswith("###") else "### " + s for s in answers_sections
        ]

        return {"day_one_answers": answers_sections, "evidence": evidence}
