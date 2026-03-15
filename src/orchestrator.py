# src/orchestrator.py
# The Brownfield Cartographer orchestrator

import json
import logging
from pathlib import Path

from src.agents.hydrologist import Hydrologist
from src.agents.semanticist import Semanticist
from src.agents.surveyor import Surveyor
from src.graph.knowledge_graph import KnowledgeGraph
from src.models.models import ModuleNode

logging.basicConfig(level=logging.INFO)


def run_analysis(repo_path: Path, output_dir: Path, days: int = 30, phase: str = "all"):
    """
    Orchestrates the analysis pipeline:
    1. Surveyor (Phase 1: static structure, git velocity, dead code, pagerank, blast radius)
    2. Hydrologist (Phase 2: data lineage)
    3. Semanticist (Phase 3: purpose statements, domain clustering, day-one answers, doc drift detection)
    4. Optional KnowledgeGraph integration
    5. Serialises outputs into .cartography/
    """

    surveyor_graph, lineage_graph, semanticist_outputs = None, None, {}

    # --- Phase 1: Surveyor ---
    if phase in ("all", "surveyor"):
        print("[Orchestrator] Running Surveyor...")
        surveyor = Surveyor(repo_path, days=days)
        surveyor_graph = surveyor.run()
        with open(output_dir / "module_graph.json", "w", encoding="utf-8") as f:
            json.dump(surveyor_graph.to_dict(), f, indent=2)

    # --- Phase 2: Hydrologist ---
    if phase in ("all", "hydrologist"):
        print("[Orchestrator] Running Hydrologist...")
        hydrologist = Hydrologist(repo_path)
        lineage_graph = hydrologist.run()
        with open(output_dir / "lineage_graph.json", "w", encoding="utf-8") as f:
            json.dump(lineage_graph.to_dict(), f, indent=2)

    # --- Phase 3: Semanticist ---
    if phase in ("all", "semanticist"):
        print("[Orchestrator] Running Semanticist...")

        # Ensure Surveyor and Hydrologist have run
        if not surveyor_graph:
            surveyor = Surveyor(repo_path, days=days)
            surveyor_graph = surveyor.run()
        if not lineage_graph:
            hydrologist = Hydrologist(repo_path)
            lineage_graph = hydrologist.run()

        semanticist = Semanticist(repo_path)

        # Convert dict nodes back into ModuleNode objects
        hydrologist_output = lineage_graph.to_dict()

        def normalise_path(path: str) -> str:
            """Ensure consistent path formatting across Windows/Linux and lowercase."""
            return path.replace("\\", "/").strip().lower()

        for node_dict in surveyor_graph.nodes:
            try:
                node_dict["path"] = normalise_path(node_dict.get("path", ""))
                node = ModuleNode(**node_dict)
                semanticist.generate_purpose_statement(node)
            except Exception as e:
                logging.warning(f"Skipping node due to error: {e}")

        # Cluster into domains
        semanticist.cluster_into_domains()

        # Answer Day-One Questions
        semanticist_outputs = semanticist.answer_day_one_questions(
            surveyor_output=surveyor_graph.to_dict(),
            hydrologist_output=hydrologist_output,
        )

        # Write outputs
        with open(output_dir / "purpose_statements.json", "w", encoding="utf-8") as f:
            json.dump(semanticist.purpose_statements, f, indent=2)
        with open(output_dir / "domain_map.json", "w", encoding="utf-8") as f:
            json.dump(semanticist.domain_clusters, f, indent=2)
        with open(output_dir / "day_one_answers.json", "w", encoding="utf-8") as f:
            json.dump(semanticist_outputs, f, indent=2)
        with open(output_dir / "doc_drift_flags.json", "w", encoding="utf-8") as f:
            json.dump(semanticist.doc_drift_flags, f, indent=2)

    # --- Integration into KnowledgeGraph wrapper ---
    if phase == "all":
        print("[Orchestrator] Integrating graphs...")
        kg = KnowledgeGraph()
        if surveyor_graph:
            kg.add_graph("module", surveyor_graph)
        if lineage_graph:
            kg.add_graph("lineage", lineage_graph)
        kg.run_cross_graph_analytics()
        with open(output_dir / "knowledge_graph.json", "w", encoding="utf-8") as f:
            json.dump(kg.to_dict(), f, indent=2)

    print("[Orchestrator] Pipeline complete.")
