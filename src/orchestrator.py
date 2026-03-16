# src/orchestrator.py
# The Brownfield Cartographer orchestrator

import json
import logging
import subprocess
from pathlib import Path
from typing import List

from src.agents.archivist import Archivist
from src.agents.hydrologist import Hydrologist
from src.agents.semanticist import Semanticist
from src.agents.surveyor import Surveyor
from src.graph.knowledge_graph import KnowledgeGraph
from src.models.models import ModuleNode

logging.basicConfig(level=logging.INFO)


def normalise_path(path: str) -> str:
    """Ensure consistent path formatting across Windows/Linux and lowercase."""
    return path.replace("\\", "/").strip().lower()


def ensure_surveyor(repo_path: Path, days: int, output_dir: Path, surveyor_graph=None):
    if not surveyor_graph:
        logging.info("[Orchestrator] Running Surveyor...")
        surveyor = Surveyor(repo_path, days=days)
        surveyor_graph = surveyor.run()
        with open(output_dir / "module_graph.json", "w", encoding="utf-8") as f:
            json.dump(surveyor_graph.to_dict(), f, indent=2)
    return surveyor_graph


def ensure_hydrologist(repo_path: Path, output_dir: Path, lineage_graph=None):
    if not lineage_graph:
        logging.info("[Orchestrator] Running Hydrologist...")
        hydrologist = Hydrologist(repo_path)
        lineage_graph = hydrologist.run()
        with open(output_dir / "lineage_graph.json", "w", encoding="utf-8") as f:
            json.dump(lineage_graph.to_dict(), f, indent=2)
    return lineage_graph


def ensure_semanticist(
    repo_path: Path, surveyor_graph, lineage_graph, output_dir: Path
):
    logging.info("[Orchestrator] Running Semanticist...")
    semanticist = Semanticist(repo_path)
    hydrologist_output = lineage_graph.to_dict()

    for node_dict in surveyor_graph.nodes:
        try:
            node_dict["path"] = normalise_path(node_dict.get("path", ""))
            node = ModuleNode(**node_dict)
            semanticist.generate_purpose_statement(node)
        except Exception as e:
            logging.warning(f"Skipping node due to error: {e}")

    semanticist.cluster_into_domains()
    outputs = semanticist.answer_day_one_questions(
        surveyor_output=surveyor_graph.to_dict(),
        hydrologist_output=hydrologist_output,
    )

    with open(output_dir / "purpose_statements.json", "w", encoding="utf-8") as f:
        json.dump(semanticist.purpose_statements, f, indent=2)
    with open(output_dir / "domain_map.json", "w", encoding="utf-8") as f:
        json.dump(semanticist.domain_clusters, f, indent=2)
    with open(output_dir / "day_one_answers.json", "w", encoding="utf-8") as f:
        json.dump(outputs, f, indent=2)
    with open(output_dir / "doc_drift_flags.json", "w", encoding="utf-8") as f:
        json.dump(semanticist.doc_drift_flags, f, indent=2)

    return outputs


def ensure_archivist(
    repo_path: Path, output_dir: Path, knowledge_graph: dict, doc_drift_flags: dict
):
    logging.info("[Orchestrator] Running Archivist...")
    archivist = Archivist(repo_path)

    # CODEBASE.md
    codebase_md = archivist.generate_codebase_md(knowledge_graph, doc_drift_flags)
    with open(output_dir / "CODEBASE.md", "w", encoding="utf-8") as f:
        f.write(codebase_md)

    # Onboarding Brief
    semanticist_file = output_dir / "day_one_answers.json"
    if semanticist_file.exists():
        onboarding_brief = archivist.generate_onboarding_brief(
            semanticist_file, knowledge_graph
        )
        with open(output_dir / "onboarding_brief.md", "w", encoding="utf-8") as f:
            f.write(onboarding_brief)

    # Lineage Graph export
    archivist.export_lineage_graph(knowledge_graph, output_dir / "lineage_graph.json")

    # Semantic Index
    archivist.build_semantic_index(knowledge_graph, output_dir / "semantic_index")

    return archivist


def get_changed_files(repo_path: Path, last_commit: str) -> List[str]:
    """Return list of files changed since last_commit."""
    cmd = [
        "git",
        "-C",
        str(repo_path),
        "log",
        f"{last_commit}..HEAD",
        "--name-only",
        "--pretty=format:",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return list({line.strip() for line in result.stdout.splitlines() if line.strip()})


def run_analysis(
    repo_path: Path,
    output_dir: Path,
    days: int = 30,
    phase: str = "all",
    incremental: bool = False,
):
    """
    Orchestrates the analysis pipeline:
    If incremental=True, only re-analyse files changed since last commit.
    1. Surveyor (Phase 1: static structure, git velocity, dead code, pagerank, blast radius)
    2. Hydrologist (Phase 2: data lineage)
    3. KnowledgeGraph integration
    4. Semanticist (Phase 3: purpose statements, domain clustering, day-one answers, doc drift detection)
    5. Archivist (Phase 4: onboarding brief, day-one guide, documentation)
    6. Serialises outputs into .cartography/
    """

    last_commit_file = output_dir / "last_commit.txt"
    last_commit = None
    if incremental and last_commit_file.exists():
        last_commit = last_commit_file.read_text().strip()

    changed_files = []
    if incremental and last_commit:
        changed_files = get_changed_files(repo_path, last_commit)
        if not changed_files:
            logging.info(
                "[Orchestrator] No new commits since last run. Skipping analysis."
            )
            return

    surveyor_graph, lineage_graph, semanticist_outputs = None, None, {}
    archivist = Archivist(repo_path)

    # --- Phase 1: Surveyor ---
    if phase in ("all", "surveyor"):
        surveyor_graph = ensure_surveyor(repo_path, days, output_dir)
        if incremental and changed_files:
            logging.info(
                f"[Orchestrator] Incremental mode: re-analysing {len(changed_files)} changed files."
            )
            surveyor_graph.update_nodes(changed_files)  # implement in Surveyor

        trace_events = [
            {
                "phase": "surveyor",
                "artifact": "module_graph.json",
                "status": "complete",
                "mode": "incremental" if incremental else "full",
                "changed_files": changed_files,
            }
        ]
        archivist.write_trace_log(
            trace_events,
            output_dir / "cartography_trace.jsonl",
            surveyor_graph.to_dict(),
        )

        head_commit = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        last_commit_file.write_text(head_commit)

    # --- Phase 2: Hydrologist ---
    if phase in ("all", "hydrologist"):
        lineage_graph = ensure_hydrologist(repo_path, output_dir)
        if incremental and changed_files:
            lineage_graph.update_nodes(changed_files)  # implement in Hydrologist

        trace_events = [
            {
                "phase": "hydrologist",
                "artifact": "lineage_graph.json",
                "status": "complete",
                "mode": "incremental" if incremental else "full",
                "changed_files": changed_files,
            }
        ]
        archivist.write_trace_log(
            trace_events,
            output_dir / "cartography_trace.jsonl",
            lineage_graph.to_dict(),
        )

        head_commit = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        last_commit_file.write_text(head_commit)

    # --- KnowledgeGraph integration ---
    if phase in ("all", "hydrologist"):
        logging.info("[Orchestrator] Integrating graphs...")
        surveyor_graph = ensure_surveyor(repo_path, days, output_dir, surveyor_graph)
        lineage_graph = ensure_hydrologist(repo_path, output_dir, lineage_graph)

        surveyor_dict = surveyor_graph.to_dict()
        lineage_dict = lineage_graph.to_dict()

        kg = KnowledgeGraph()
        kg.add_graph("module", surveyor_dict)
        kg.add_graph("lineage", lineage_dict)
        kg.run_cross_graph_analytics()

        with open(output_dir / "knowledge_graph.json", "w", encoding="utf-8") as f:
            json.dump(kg.to_dict(), f, indent=2)

    # --- Phase 3: Semanticist ---
    if phase in ("all", "semanticist"):
        surveyor_graph = ensure_surveyor(repo_path, days, output_dir, surveyor_graph)
        lineage_graph = ensure_hydrologist(repo_path, output_dir, lineage_graph)

        semanticist_outputs = ensure_semanticist(
            repo_path, surveyor_graph, lineage_graph, output_dir
        )

        trace_events = [
            {
                "phase": "semanticist",
                "artifact": "purpose_statements.json",
                "status": "complete",
            },
            {
                "phase": "semanticist",
                "artifact": "domain_map.json",
                "status": "complete",
            },
            {
                "phase": "semanticist",
                "artifact": "day_one_answers.json",
                "status": "complete",
            },
            {
                "phase": "semanticist",
                "artifact": "doc_drift_flags.json",
                "status": "complete",
            },
        ]
        knowledge_graph = {
            "graphs": {
                "module": surveyor_graph.to_dict(),
                "lineage": lineage_graph.to_dict(),
            }
        }
        archivist.write_trace_log(
            trace_events, output_dir / "cartography_trace.jsonl", knowledge_graph
        )

        head_commit = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        last_commit_file.write_text(head_commit)

    # --- Phase 4: Archivist ---
    if phase in ("all", "archivist"):
        kg_path = output_dir / "knowledge_graph.json"
        drift_path = output_dir / "doc_drift_flags.json"

        if not kg_path.exists():
            logging.error(
                "[Archivist] knowledge_graph.json not found. Run hydrologist first."
            )
            return

        with open(kg_path, "r", encoding="utf-8") as f:
            knowledge_graph = json.load(f)

        doc_drift_flags = {}
        if drift_path.exists():
            with open(drift_path, "r", encoding="utf-8") as f:
                doc_drift_flags = json.load(f)

        ensure_archivist(repo_path, output_dir, knowledge_graph, doc_drift_flags)

        trace_events = [
            {"phase": "archivist", "artifact": "CODEBASE.md", "status": "complete"},
            {
                "phase": "archivist",
                "artifact": "onboarding_brief.md",
                "status": "complete",
            },
            {
                "phase": "archivist",
                "artifact": "lineage_graph.json",
                "status": "complete",
            },
            {"phase": "archivist", "artifact": "semantic_index", "status": "complete"},
        ]
        archivist.write_trace_log(
            trace_events, output_dir / "cartography_trace.jsonl", knowledge_graph
        )

        head_commit = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        last_commit_file.write_text(head_commit)

        logging.info("[Orchestrator] Archivist phase complete.")

    logging.info("[Orchestrator] Pipeline complete.")
