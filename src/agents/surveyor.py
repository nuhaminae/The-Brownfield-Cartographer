# src/agents/surveyor.py
# The Brownfield Cartographer Surveyor

import subprocess
from pathlib import Path

import networkx as nx

from src.analysers.tree_sitter_analyser import analyse_module
from src.models.models import Edge, EdgeType, GraphSchema


def extract_git_velocity(repo_path: Path, days: int = 30):
    """
    Parse git log output to compute change frequency per file.
    Identify the 20% of files responsible for 80% of changes.
    """
    cmd = [
        "git",
        "-C",
        str(repo_path),
        "log",
        f"--since={days}.days.ago",  # corrected syntax
        "--pretty=format:",
        "--name-only",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    changes = {}
    for line in result.stdout.splitlines():
        if line.strip():
            changes[line] = changes.get(line, 0) + 1

    # Pareto principle: top 20% of files
    sorted_files = sorted(changes.items(), key=lambda x: x[1], reverse=True)
    cutoff = max(1, int(len(sorted_files) * 0.2))
    high_velocity = sorted_files[:cutoff]

    return {"changes": changes, "high_velocity": high_velocity}


def run_surveyor(repo_path: Path, days: int = 30) -> GraphSchema:
    """
    Build the module import graph using tree-sitter analysis.
    Run PageRank to identify architectural hubs.
    Detect circular dependencies.
    """
    graph = nx.DiGraph()
    module_nodes = []

    # Walk repo and analyse Python files
    for file_path in repo_path.rglob("*.py"):
        module = analyse_module(file_path)
        module_nodes.append(module)

        # Add node
        graph.add_node(
            module.path,
            functions=module.functions,
            classes=[c.to_dict() for c in module.classes],
        )

        # Add edges for imports
        for imp in module.imports:
            e = Edge(source=module.path, target=imp, type=EdgeType.IMPORT)
            graph.add_edge(e.source, e.target, type=e.type.value)

    # Compute PageRank
    pagerank_scores = nx.pagerank(graph)

    # Detect strongly connected components (circular dependencies)
    scc = list(nx.strongly_connected_components(graph))

    # Git velocity analysis
    velocity = extract_git_velocity(repo_path, days=days)

    # Wrap in schema for serialisation
    module_graph = GraphSchema(
        nodes=[m.to_dict() for m in module_nodes],
        edges=[
            Edge(source=u, target=v, type=d["type"]).to_dict()
            for u, v, d in graph.edges(data=True)
        ],
        pagerank=pagerank_scores,
        circular_dependencies=[list(c) for c in scc],
        velocity=velocity,
    )

    return module_graph
