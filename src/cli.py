# src/cli.py
# The Brownfield Cartographer CLI entry point

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from src.orchestrator import run_analysis


def clone_repo(github_url: str, target_dir: Path) -> Path:
    """Clone a GitHub repo into target_dir and return the local path."""
    try:
        subprocess.run(["git", "clone", github_url, str(target_dir)], check=True)
        print(f"[CLI] Successfully cloned {github_url} into {target_dir}")
        return target_dir
    except subprocess.CalledProcessError as e:
        print(f"[CLI] Error cloning repo: {e}")
        sys.exit(1)


def print_artifact_summary(output_dir: Path, phase: str):
    """Print a summary of generated artifacts with descriptions."""
    summaries = {
        "surveyor": [
            ("module_graph.json", "static code/config structure"),
        ],
        "hydrologist": [
            ("lineage_graph.json", "data pipeline lineage"),
            ("knowledge_graph.json", "unified graph with blast radius + bridge nodes"),
        ],
        "semanticist": [
            ("purpose_statements.json", "purpose statements per module"),
            ("domain_map.json", "clustered domains"),
            ("day_one_answers.json", "answers to onboarding questions"),
            ("doc_drift_flags.json", "documentation drift detection"),
        ],
        "archivist": [
            ("CODEBASE.md", "structured overview for AI coding agents"),
            ("onboarding_brief.md", "Day-One Brief answering Five FDE questions"),
            ("lineage_graph.json", "serialised lineage graph"),
            ("semantic_index/", "vector store of module purpose statements"),
            ("cartography_trace.jsonl", "audit log of agent actions"),
        ],
    }

    if phase == "all":
        print("[CLI] Full pipeline artifacts generated:")
        for p in ("surveyor", "hydrologist", "semanticist"):
            for fname, desc in summaries[p]:
                print(f" - {output_dir}/{fname} ({desc})")
    else:
        print(f"[CLI] {phase.capitalize()} artifacts generated:")
        for fname, desc in summaries[phase]:
            print(f" - {output_dir}/{fname} ({desc})")


def main():
    parser = argparse.ArgumentParser(description="Brownfield Cartographer CLI")
    parser.add_argument(
        "--repo", required=True, help="Path to local repo or GitHub URL"
    )
    parser.add_argument("--days", type=int, default=30, help="Git velocity window")
    parser.add_argument(
        "--output", default=".cartography", help="Directory for artifacts"
    )
    parser.add_argument(
        "--phase",
        choices=["all", "surveyor", "hydrologist", "semanticist", "archivist"],
        default="all",
    )

    args = parser.parse_args()

    repo_path = Path(args.repo)
    temp_dir = None
    if args.repo.startswith(("http://", "https://")):
        temp_dir = Path(tempfile.mkdtemp())
        repo_path = clone_repo(args.repo, temp_dir)
    if not repo_path.exists():
        print(f"[CLI] Repository path {repo_path} does not exist.")
        sys.exit(1)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[CLI] Running analysis on {repo_path} (phase={args.phase})...")
    run_analysis(repo_path, output_dir, days=args.days, phase=args.phase)

    # Print artifact summary
    print_artifact_summary(output_dir, args.phase)

    print(f"[CLI] Analysis complete. Artifacts written to {output_dir}")

    if temp_dir:
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"[CLI] Cleaned up temporary directory {temp_dir}")


if __name__ == "__main__":
    main()
