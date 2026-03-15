# src/agents/semanticist.py
# The Brownfield Cartographer

import json
import logging
from pathlib import Path
from typing import Any, Dict

import ollama
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity

from src.models.models import ModuleNode

logging.basicConfig(level=logging.INFO)
# ollama run glm-5:cloud


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

        def _sanitize_output(text: str) -> str:
            if not text:
                return ""

            # Common preambles we want to drop
            preambles = [
                "Sure, here is a concise purpose statement for this module:",
                "Sure, here's a concise purpose statement for the code: ",
                "Sure, here is a concise purpose statement for the module:",
                "Sure, here is the concise purpose statement for the module: ",
                "Sure, here's the purpose statement:",
                "Sure, here's a concise purpose statement for the module: ",
                "Sure, here's the concise purpose statement: ",
                "Here is a concise purpose statement:",
                "Sure, here is the concise purpose statement for the module: ",
            ]

            for p in preambles:
                text = text.replace(p, "")

            # Strip markdown artifacts
            text = text.replace("**", "").replace("```", "")

            # Clean up whitespace
            return " ".join(text.split()).strip()

        try:
            response = ollama.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                options={"num_predict": max_tokens},
            )
            raw = response["message"]["content"].strip()

            # Debug logging
            print("\n[DEBUG] Raw LLM output:\n", raw if raw else "(Empty)")
            sanitized = _sanitize_output(raw)
            print(
                "\n[DEBUG] Sanitized output:\n",
                sanitized if sanitized else "(Empty after sanitization)",
            )

            return sanitized
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
        code = (module_node.attrs.get("code") or "").strip()
        docstring = (module_node.attrs.get("docstring") or "").strip()
        extra_docstrings = module_node.attrs.get("function_docstrings") or {}

        if not self.context_budget.reserve(code):
            logging.warning(f"Skipping {module_node.path} due to budget.")
            return ""

        # Generate from code
        prompt = (
            "Return only a concise purpose statement for this module. "
            "Focus on its business function, not implementation detail. "
            "Do not include preambles, markdown, or formatting. "
            "Limit to 2-3 sentences.\n\n"
            f"Code:\n{code[:1500]}"
        )
        statement = self._run_model(self._select_model(False), prompt, 400)

        # Normalize path
        def normalise_key(path: str) -> str:
            return path.replace("\\", "/").strip().lower()

        norm_path = normalise_key(module_node.path)
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

        return statement

    def cluster_into_domains(self):
        texts = list(self.purpose_statements.values())
        if not texts:
            return

        # Use embedding
        embeddings = []
        for text in texts:
            try:
                emb = ollama.embeddings(model="glm-5:cloud", prompt=text)["embedding"]
                embeddings.append(emb)
            except Exception as e:
                logging.error(f"Embedding failed: {e}")
                embeddings.append([0] * 768)  # fallback vector

        k = min(8, max(5, len(texts)))  # enforce k=5–8
        km = KMeans(n_clusters=k, random_state=42)
        km.fit(embeddings)

        for i, module in enumerate(self.purpose_statements.keys()):
            self.domain_clusters[module] = f"Domain-{km.labels_[i]}"

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
            label = self._run_model(self._select_model(False), prompt, 50).strip()
            for i, module in enumerate(self.purpose_statements.keys()):
                if km.labels_[i] == cluster_id:
                    self.domain_clusters[module] = label

    def answer_day_one_questions(
        self, surveyor_output: Dict[str, Any], hydrologist_output: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Synthesise answers to the Five Day-One Questions using Surveyor + Hydrologist outputs.
        Preprocesses evidence to filter noise and highlight the most relevant signals.
        Includes debug prints for transparency.
        """

        # --- Debug raw inputs ---
        print("\n=== Surveyor Output ===")
        print("Sources:", surveyor_output.get("sources", []))
        print("Sinks:", surveyor_output.get("sinks", []))
        print(
            "Pagerank (top 10):",
            sorted(
                surveyor_output.get("pagerank", {}).items(),
                key=lambda x: x[1],
                reverse=True,
            )[:10],
        )
        print(
            "Velocity Hotspots:",
            surveyor_output.get("velocity", {}).get("hotspots", []),
        )
        print(
            "Dead Code Summary:",
            surveyor_output.get("velocity", {}).get("dead_code_summary", {}),
        )

        print("\n=== Hydrologist Output ===")
        print("Sources:", hydrologist_output.get("sources", []))
        print("Sinks:", hydrologist_output.get("sinks", []))
        print("Edges:", hydrologist_output.get("edges", []))
        print("Blast Radius:", hydrologist_output.get("blast_radius", {}))

        # --- Preprocess evidence ---
        # Ingestion nodes: prefer Surveyor, fallback to Hydrologist, filter to tap-* extractors
        ingestion_nodes = surveyor_output.get("sources", [])
        if not ingestion_nodes:
            ingestion_nodes = hydrologist_output.get("sources", [])
        ingestion_nodes = [n for n in ingestion_nodes if n.startswith("tap-")]

        # Critical outputs: use Hydrologist sinks, filter to target-* loaders
        critical_targets = [
            s for s in hydrologist_output.get("sinks", []) if s.startswith("target-")
        ][:5]

        # Pagerank: filter to Python modules in src/meltano/core
        pagerank = surveyor_output.get("pagerank", {})
        code_modules = {
            k: v
            for k, v in pagerank.items()
            if k.endswith(".py") and "src/meltano/core" in k
        }
        top_pagerank = sorted(code_modules.items(), key=lambda x: x[1], reverse=True)[
            :5
        ]

        # Velocity: highlight hotspots limited to .py files
        velocity = surveyor_output.get("velocity", {})
        hotspots = [h for h in velocity.get("hotspots", []) if h.endswith(".py")][:5]
        dead_code_summary = velocity.get("dead_code_summary", {})

        # Blast radius: expand to top 3 nodes
        blast_radius = hydrologist_output.get("blast_radius", {})
        top_blast = sorted(blast_radius.items(), key=lambda x: x[1], reverse=True)[:3]

        evidence = {
            "ingestion_nodes": ingestion_nodes,
            "critical_outputs": critical_targets,
            "top_pagerank": top_pagerank,
            "hotspots": hotspots,
            "dead_code_summary": dead_code_summary,
            "blast_radius": top_blast,
        }

        # --- Build prompt with explicit mapping ---
        prompt = f"""
        You are an expert software cartographer. Use the following preprocessed evidence to answer the Five FDE Day-One Questions.

        Evidence Summary:
        - Ingestion Nodes (Singer taps): {ingestion_nodes}
        - Critical Outputs (Singer targets): {critical_targets}
        - Top Business Logic Modules (Python in src/meltano/core): {top_pagerank}
        - Velocity Hotspots (recently changed .py files): {hotspots}
        - Dead Code Summary: {dead_code_summary}
        - Blast Radius (modules with downstream impact): {top_blast}

        Answer concisely and directly:

        1. What is the primary data ingestion path? (use ingestion_nodes)
        2. What are the 3-5 most critical output datasets/endpoints? (use critical_outputs)
        3. What is the blast radius if the most critical module fails? (use blast_radius)
        4. Where is the business logic concentrated vs. distributed? (use top_pagerank)
        5. What has changed most frequently in the last 90 days? (use velocity hotspots and dead_code_summary)
        """

        # --- Run model ---
        answers = self._run_model(self._select_model(True), prompt, 600)

        # --- Fallback if model refuses ---
        if "cannot answer" in answers.lower() or not answers.strip():
            answers = f"""
            1. Primary ingestion: {ingestion_nodes or "No ingestion nodes detected"}
            2. Critical outputs: {critical_targets or "No critical outputs detected"}
            3. Blast radius: {top_blast or "No blast radius data"}
            4. Business logic concentration: {top_pagerank or "No pagerank data"}
            5. Frequent changes: {hotspots or "No hotspots"}; Dead code: {dead_code_summary}
            """

        return {"day_one_answers": answers.strip(), "evidence": evidence}
