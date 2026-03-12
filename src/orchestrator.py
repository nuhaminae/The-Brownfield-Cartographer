# src/orchestrator.py
# The Brownfield Cartographer orchestrator


import json
from pathlib import Path

from src.agents.hydrologist import run_hydrologist
from src.agents.surveyor import run_surveyor
from src.graph.knowledge_graph import KnowledgeGraph


def run_analysis(repo_path: Path, output_dir: Path, days: int = 30):
    """
    Orchestrates the analysis pipeline:
    1. Runs Surveyor (static structure, git velocity).
    2. Runs Hydrologist (data lineage).
    3. Serialises outputs into .cartography/ directory.
    """

    # --- Phase 1: Surveyor ---
    print("[Orchestrator] Running Surveyor...")
    surveyor_graph = run_surveyor(repo_path, days=days)

    module_graph_path = output_dir / "module_graph.json"
    with open(module_graph_path, "w", encoding="utf-8") as f:
        json.dump(surveyor_graph.to_dict(), f, indent=2)
    print(f"[Orchestrator] Module graph written to {module_graph_path}")

    print(
        f"[Orchestrator] Surveyor found {len(surveyor_graph.nodes)} nodes "
        f"and {len(surveyor_graph.edges)} edges."
    )

    # --- Phase 2: Hydrologist ---
    print("[Orchestrator] Running Hydrologist...")
    lineage_graph = run_hydrologist(repo_path)

    lineage_graph_path = output_dir / "lineage_graph.json"
    with open(lineage_graph_path, "w", encoding="utf-8") as f:
        json.dump(lineage_graph.to_dict(), f, indent=2)
    print(f"[Orchestrator] Lineage graph written to {lineage_graph_path}")

    print(
        f"[Orchestrator] Hydrologist found {len(lineage_graph.nodes)} nodes "
        f"and {len(lineage_graph.edges)} edges."
    )

    # --- Integration into KnowledgeGraph wrapper ---
    print("[Orchestrator] Integrating graphs into KnowledgeGraph...")
    kg = KnowledgeGraph()
    kg.add_graph("module", surveyor_graph)
    kg.add_graph("lineage", lineage_graph)

    print(
        f"[Orchestrator] KnowledgeGraph merged "
        f"{sum(len(g.nodes) for g in kg.graphs.values())} nodes "
        f"and {sum(len(g.edges) for g in kg.graphs.values())} edges."
    )

    # Optionally serialise combined knowledge graph
    combined_path = output_dir / "knowledge_graph.json"
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump(kg.to_dict(), f, indent=2)
    print(f"[Orchestrator] Combined knowledge graph written to {combined_path}")

    print("[Orchestrator] Analysis pipeline complete.")
