# src/cli.py
# The Brownfield Cartographer CLI entry point

import argparse
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
        print(f"Error cloning repo: {e}")
        sys.exit(1)


def main():
    """
    Main entry point for the Brownfield Cartographer CLI

    This function takes command-line arguments for a repository path (local or GitHub URL),
    git velocity window (default: 30 days), and output directory (default: .cartography).

    It clones the repository if necessary, runs the analysis pipeline, and writes the
    resulting artifacts to the specified output directory.

    :param args: Command-line arguments parsed by argparse
    :return: None
    """
    parser = argparse.ArgumentParser(description="Brownfield Cartographer CLI")
    parser.add_argument(
        "--repo", required=True, help="Path to local repo or GitHub URL"
    )
    parser.add_argument(
        "--days", type=int, default=30, help="Git velocity window (default: 30 days)"
    )
    parser.add_argument(
        "--output", default=".cartography", help="Directory to store analysis artifacts"
    )

    args = parser.parse_args()

    repo_path = Path(args.repo)
    if args.repo.startswith("http://") or args.repo.startswith("https://"):
        # Clone GitHub repo into temp dir
        temp_dir = Path(tempfile.mkdtemp())
        repo_path = clone_repo(args.repo, temp_dir)

    if not repo_path.exists():
        print(f"Repository path {repo_path} does not exist.")
        sys.exit(1)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running analysis on {repo_path}...")
    run_analysis(repo_path, output_dir, days=args.days)
    print(f"Analysis complete. Artifacts written to {output_dir}")

    print("\n[CLI] Analysis Summary:")
    for file_name in [
        "module_graph.json",
        "lineage_graph.json",
        "knowledge_graph.json",
    ]:
        file_path = output_dir / file_name
        if file_path.exists():
            size_kb = file_path.stat().st_size / 1024
            print(f" - {file_name}: {size_kb:.1f} KB at {file_path}")


if __name__ == "__main__":
    main()
