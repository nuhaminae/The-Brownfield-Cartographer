# src/orchestrator.py
# The Brownfield Cartographer orchestrator

import json
import logging
from pathlib import Path

from src.agents.hydrologist import Hydrologist
from src.agents.surveyor import Surveyor
from src.graph.knowledge_graph import KnowledgeGraph

logging.basicConfig(level=logging.INFO)


def run_analysis(repo_path: Path, output_dir: Path, days: int = 30, phase: str = "all"):
    """
    Orchestrates the analysis pipeline:
    1. Surveyor (Phase 1: static structure, git velocity, dead code, pagerank, blast radius)
    2. Hydrologist (Phase 2: data lineage)
    3. Optional KnowledgeGraph integration
    4. Serialises outputs into .cartography/
    """

    surveyor_graph, lineage_graph = None, None
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
