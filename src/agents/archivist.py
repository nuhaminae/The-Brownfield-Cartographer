# src/agents/archivist.py
# The Brownfield Cartographer Archivist

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO)


class Archivist:
    """
    Archivist generates human-readable documentation and artifacts from the knowledge_graph.
    Phase 4 deliverables:
      - CODEBASE.md (architecture overview, critical path, data sources/sinks, known debt, velocity)
      - onboarding_brief.md (Day-One Brief answering Five FDE questions with evidence citations)
      - lineage_graph.json (serialised lineage graph portion of knowledge_graph)
      - semantic_index/ (vector store of module purpose statements)
      - cartography_trace.jsonl (audit log of agent actions, evidence sources, confidence levels)
    """

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.repo_name = repo_path.name

    # ---------------- CODEBASE.md ----------------
    def generate_codebase_md(
        self, knowledge_graph: Dict[str, Any], doc_drift_flags: Dict[str, Any] = None
    ) -> str:
        module = knowledge_graph.get("graphs", {}).get("module", {})
        lineage = knowledge_graph.get("graphs", {}).get("lineage", {})

        doc = [f"# CODEBASE Overview: {self.repo_name}\n"]

        # ---------------- Architecture Overview ----------------
        doc.append("## Architecture Overview\n")
        module_count = len(module.get("nodes", []))

        # Aggregate metrics across modules
        loc_total, cc_total, cr_total, metric_count = 0, 0, 0, 0
        for node in module.get("nodes", []):
            attrs = {}
            if isinstance(node, dict):
                attrs = node.get("attrs", {})
            elif isinstance(node, (list, tuple)) and len(node) == 2:
                attrs = node[1].get("attrs", {})
            metrics_node = attrs.get("metrics", {})
            if metrics_node:
                loc_total += metrics_node.get("loc", 0)
                cc_total += metrics_node.get("cyclomatic_complexity", 0)
                cr_total += metrics_node.get("comment_ratio", 0)
                metric_count += 1

        avg_cc = cc_total / metric_count if metric_count else None
        avg_cr = cr_total / metric_count if metric_count else None
        debt = module.get("dead_code_summary", {})

        # Optional: domain clusters
        domain_map_path = (
            Path(self.repo_path.parent) / ".cartography" / "domain_map.json"
        )
        domain_count = None
        if domain_map_path.exists():
            with open(domain_map_path, "r", encoding="utf-8") as f:
                domain_map = json.load(f)
            domain_count = len(domain_map.keys())

        # Build narrative overview
        overview_text = f"This codebase contains {module_count} modules"
        if loc_total:
            overview_text += f", totaling ~{loc_total} lines of code"
        if avg_cc is not None:
            overview_text += f". The average cyclomatic complexity is {avg_cc:.2f}"
        if avg_cr is not None:
            overview_text += f", with a comment ratio of {avg_cr:.2f}"
        if debt:
            overview_text += (
                f". Dead code analysis found {debt.get('dead_functions_count' ,0)} unused functions "
                f"and {debt.get('orphan_modules_count' ,0)} orphan modules"
            )
        if domain_count:
            overview_text += f". Modules cluster into ~{domain_count} domains"

        doc.append(overview_text + ".\n")
        doc.append("\n---\n")

        # ---------------- Critical Path ----------------
        pagerank = module.get("pagerank", {})
        doc.append("## Critical Path (Top 5 Modules by PageRank)\n")
        if isinstance(pagerank, dict) and pagerank:
            # Handle nested pagerank dicts (e.g. {"scores": {...}})
            scores = pagerank.get("scores", pagerank)
            if isinstance(scores, dict):
                top_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
                for mod, score in top_items:
                    doc.append(f"- {mod} (score {score:.6f})")
        elif isinstance(pagerank, list) and pagerank:
            for item in pagerank[:5]:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    mod, score = item
                    doc.append(f"- {mod} (score {score:.6f})")
                else:
                    doc.append(f"- {item}")
        else:
            doc.append("- No pagerank data available")
        doc.append("\n---\n")

        # ---------------- Data Sources & Sinks ----------------
        sources = lineage.get("sources", [])
        sinks = lineage.get("sinks", [])
        doc.append("## Data Sources & Sinks\n")
        doc.append(f"- Sources: {', '.join(sources[:10]) if sources else 'None'}")
        doc.append(f"- Sinks: {', '.join(sinks[:10]) if sinks else 'None'}")
        doc.append("\n---\n")

        # ---------------- Known Debt ----------------
        doc.append("## Known Debt\n")
        if doc_drift_flags:
            drifted = {k: v for k, v in doc_drift_flags.items() if v}
            if drifted:
                for k in drifted.keys():
                    doc.append(f"- {k}: Drift detected")
            else:
                doc.append("- No drift detected")
        elif debt:
            doc.append(f"- Dead functions: {debt.get('dead_functions_count', 0)}")
            doc.append(f"- Dead classes: {debt.get('dead_classes_count', 0)}")
            doc.append(f"- Orphan modules: {debt.get('orphan_modules_count', 0)}")
        else:
            doc.append("- No debt metrics available")
        doc.append("\n---\n")

        # ---------------- High-Velocity Files ----------------
        velocity_mod = module.get("velocity", [])
        # In your JSON, velocity is a list of files, not a dict with hotspots
        hotspots = (
            velocity_mod
            if isinstance(velocity_mod, list)
            else velocity_mod.get("hotspots", [])
        )
        doc.append("## High-Velocity Files\n")
        if hotspots:
            for h in hotspots[:10]:
                doc.append(f"- {h}")
        else:
            doc.append("- No hotspots detected")
        doc.append("\n---\n")

        # ---------------- Supplementary Evidence: Blast Radius ----------------
        doc.append("## Supplementary Evidence: Blast Radius\n")
        blast_module = module.get("blast_radius", {})
        blast_lineage = lineage.get("blast_radius", {})
        if blast_module or blast_lineage:
            if blast_module:
                for node, impact in list(blast_module.items())[:10]:
                    doc.append(f"- {node}: {impact} descendants (module)")
            if blast_lineage:
                for node, impact in list(blast_lineage.items())[:10]:
                    doc.append(f"- {node}: {impact} descendants (lineage)")
        else:
            doc.append("- No blast radius data available")
        doc.append("\n---\n")

        return "\n".join(doc)

    # ---------------- Onboarding Brief ----------------
    def generate_onboarding_brief(
        self, semanticist_file: Path, knowledge_graph: Dict[str, Any] = None
    ) -> str:
        with open(semanticist_file, "r", encoding="utf-8") as f:
            semanticist_answers = json.load(f)

        answers = semanticist_answers.get("day_one_answers", [])
        evidence = semanticist_answers.get("evidence", {})

        brief = [f"# Onboarding Brief for {self.repo_name}\n"]
        brief.append(
            "This brief answers the Five FDE Day-One Questions with evidence:\n"
        )

        for ans in answers[:5]:
            clean = re.sub(r"^#+\s*", "", ans).strip()
            brief.append(clean)
            brief.append("\n---\n")

        if "ingestion_nodes" in evidence:
            brief.append("### Evidence: Ingestion Nodes")
            for src in evidence["ingestion_nodes"]:
                brief.append(f"- {src}")
            brief.append("\n---\n")

        if "critical_outputs" in evidence:
            brief.append("### Evidence: Critical Outputs")
            for s, d in evidence["critical_outputs"]:
                brief.append(f"- {s} (degree {d})")
            brief.append("\n---\n")

        if "blast_radius" in evidence:
            brief.append("### Evidence: Blast Radius")
            for f, c in evidence["blast_radius"].get("structural", []):
                brief.append(f"- {f} ({c})")
            for f, c in evidence["blast_radius"].get("dataflow", []):
                brief.append(f"- {f} ({c})")
            brief.append("\n---\n")

        if "top_pagerank" in evidence:
            brief.append("### Evidence: Top Pagerank Modules")
            for m, v in evidence["top_pagerank"]:
                brief.append(f"- {m} (score {v:.6f})")
            brief.append("\n---\n")

        if "hotspots" in evidence:
            brief.append("### Evidence: Hotspots")
            for h in evidence["hotspots"]:
                brief.append(f"- {h}")
            brief.append("\n---\n")

        if len(answers) > 5:
            for extra in answers[5:]:
                clean = re.sub(r"^#+\s*", "", extra).strip()
                brief.append(f"## Additional Risks and Dependencies\n{clean}\n---\n")

        if knowledge_graph:
            debt = (
                knowledge_graph.get("graphs", {})
                .get("module", {})
                .get("dead_code_summary", {})
            )
            if debt:
                brief.append("## Supplementary Evidence: Dead Code Summary")
                brief.append(f"- Dead functions: {debt.get('dead_functions_count', 0)}")
                brief.append(f"- Dead classes: {debt.get('dead_classes_count', 0)}")
                brief.append(f"- Orphan modules: {debt.get('orphan_modules_count', 0)}")
                brief.append("\n---\n")

        return "\n".join(brief)

    # ---------------- Lineage Graph ----------------
    def export_lineage_graph(self, knowledge_graph: Dict[str, Any], out_path: Path):
        lineage = knowledge_graph.get("graphs", {}).get("lineage", {})
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(lineage, f, indent=2)
        logging.info(f"[Archivist] Exported lineage graph to {out_path}")

    # ---------------- Semantic Index ----------------
    def build_semantic_index(self, knowledge_graph: Dict[str, Any], out_dir: Path):
        def safe_filename(name: str, max_length: int = 100) -> str:
            cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", name)
            if len(cleaned) > max_length:
                cleaned = cleaned[:max_length]
            return cleaned

        out_dir.mkdir(parents=True, exist_ok=True)
        modules = knowledge_graph.get("graphs", {}).get("module", {}).get("nodes", [])

        for node in modules:
            # Case 1: node is a tuple/list like (id, attrs)
            if isinstance(node, (list, tuple)) and len(node) == 2:
                raw_id = node[0]
                attrs = node[1].get("attrs", {})
            # Case 2: node is a dict with id + attrs
            elif isinstance(node, dict):
                raw_id = node.get("id", "unknown")
                attrs = node.get("attrs", {})
            else:
                continue

            purpose = attrs.get("purpose_statement", "")
            mod_id = safe_filename(Path(str(raw_id)).stem)

            with open(out_dir / f"{mod_id}.txt", "w", encoding="utf-8") as f:
                f.write(purpose)

    # ---------------- Trace Log ----------------
    def write_trace_log(
        self,
        trace_events: List[Dict[str, Any]],
        out_path: Path,
        knowledge_graph: Dict[str, Any] = None,
    ):
        """
        Write cartography_trace.jsonl: audit log of agent actions, evidence sources, confidence levels.
        Optionally include references to which graph sections were used and confidence scores.
        """
        lineage = knowledge_graph.get("graphs", {}).get("lineage", {})
        velocity = knowledge_graph.get("velocity", {})
        enriched_events = []

        for event in trace_events:
            enriched = dict(event)  # copy base event

            if knowledge_graph:
                enriched["graphs_used"] = []
                enriched["confidence"] = "medium"  # default

                # CODEBASE.md
                if "codebase_md" in event.get("artifact", ""):
                    enriched["graphs_used"].append(
                        "module:pagerank,velocity,dead_code_summary,metrics"
                    )
                    enriched["graphs_used"].append("lineage:sources,sinks,blast_radius")
                    # Confidence: high if pagerank + velocity exist
                    if knowledge_graph["graphs"]["module"].get(
                        "pagerank"
                    ) and velocity.get("hotspots"):
                        enriched["confidence"] = "high"

                # Onboarding Brief
                if "onboarding_brief" in event.get("artifact", ""):
                    enriched["graphs_used"].append(
                        "module:pagerank,velocity,dead_code_summary"
                    )
                    enriched["graphs_used"].append("lineage:sources,sinks,blast_radius")
                    # Confidence: high if sources + sinks exist
                    if lineage.get("sources") and lineage.get("sinks"):
                        enriched["confidence"] = "high"

                # Semantic Index
                if "semantic_index" in event.get("artifact", ""):
                    enriched["graphs_used"].append("module:nodes")
                    # Confidence: high if purpose statements exist
                    nodes = knowledge_graph["graphs"]["module"].get("nodes", [])
                    if any(
                        (
                            isinstance(n, dict)
                            and n.get("attrs", {}).get("purpose_statement")
                        )
                        or (
                            isinstance(n, (list, tuple))
                            and n[1].get("attrs", {}).get("purpose_statement")
                        )
                        for n in nodes
                    ):
                        enriched["confidence"] = "high"

            enriched_events.append(enriched)

        with open(out_path, "w", encoding="utf-8") as f:
            for event in enriched_events:
                f.write(json.dumps(event) + "\n")

        logging.info(f"[Archivist] Wrote trace log to {out_path}")
