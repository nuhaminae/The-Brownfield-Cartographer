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
        return target_dir
    except subprocess.CalledProcessError as e:
        print(f"[CLI] Error cloning repo: {e}")
        sys.exit(1)


def main():
    """
    CLI entry point.
    Supports:
    - Local repo path or GitHub URL
    - Git velocity window (default: 30 days)
    - Output directory (default: .cartography)
    - Optional flags to run only Surveyor, Hydrologist, or Semanticist
    Phases:
    - Surveyor (Phase 1: static structure, git velocity, dead code, pagerank, blast radius)
    - Hydrologist (Phase 2: data lineage)
    - Semanticist (Phase 3: purpose statements, domain clustering, day-one answers, doc drift detection)
    - All (runs full pipeline and integrates into KnowledgeGraph)
    """
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
        choices=["all", "surveyor", "hydrologist", "semanticist"],
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

    # Print artifact summary for Semanticist phase
    if args.phase in ("all", "semanticist"):
        print("[CLI] Semanticist artifacts generated:")
        print(f" - {output_dir}/purpose_statements.json")
        print(f" - {output_dir}/domain_map.json")
        print(f" - {output_dir}/day_one_answers.json")
        print(f" - {output_dir}/doc_drift_flags.json (if enabled in orchestrator)")

    print(f"[CLI] Analysis complete. Artifacts written to {output_dir}")

    if temp_dir:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
