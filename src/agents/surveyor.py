# src/agents/surveyor.py
# The Brownfield Cartographer Surveyor

import ast
import logging
import subprocess
from pathlib import Path

import networkx as nx

from src.analysers.tree_sitter_analyser import analyse_module
from src.models.models import DataLineageGraph, Edge, EdgeType

logging.basicConfig(level=logging.INFO)


class Surveyor:
    """
    Surveyor builds the module import graph and enriches it with:
    - Git velocity hotspots (summarised)
    - Dead code detection (basic heuristic)
    - PageRank and circular dependency analysis (summarised)
    - Blast radius computation (top percentile only)
    """

    def __init__(self, repo_path: Path, days: int = 30):
        self.repo_path = repo_path
        self.days = days

    def extract_git_velocity(self):
        """Summarise velocity hotspots only, omit raw counts."""
        cmd = [
            "git",
            "-C",
            str(self.repo_path),
            "log",
            f"--since={self.days}.days.ago",
            "--pretty=format:",
            "--name-only",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        changes = {}
        for line in result.stdout.splitlines():
            if line.strip():
                changes[line] = changes.get(line, 0) + 1

        sorted_files = sorted(changes.items(), key=lambda x: x[1], reverse=True)
        cutoff = max(1, int(len(sorted_files) * 0.2))
        hotspots = [f for f, _ in sorted_files[:cutoff]]
        return {"hotspots": hotspots}

    def detect_dead_code(self, module_nodes):
        """Summarise dead code counts across languages."""
        dead_functions, dead_classes, orphan_modules = 0, 0, 0
        for module in module_nodes:
            # Python/JS/TS
            if module.functions and not module.imports:
                dead_functions += len(module.functions)
            if module.classes and not module.imports:
                dead_classes += len(module.classes)

            # YAML heuristic: pairs with None values (nested mappings without scalars)
            if hasattr(module, "pairs") and module.pairs:
                dead_functions += sum(1 for p in module.pairs if p["value"] is None)

            # SQL heuristic: queries without tables
            if module.queries and not module.tables:
                dead_functions += len(module.queries)

            # Orphan modules
            if not (
                module.imports
                or module.functions
                or module.classes
                or module.pairs
                or module.tables
                or module.queries
            ):
                orphan_modules += 1

        return {
            "dead_functions_count": dead_functions,
            "dead_classes_count": dead_classes,
            "orphan_modules_count": orphan_modules,
        }

    def compute_blast_radius(self, graph):
        """Keep only top percentile blast radius nodes."""
        blast_radius = {node: len(nx.descendants(graph, node)) for node in graph.nodes}
        cutoff = max(1, int(len(blast_radius) * 0.1))
        return dict(
            sorted(blast_radius.items(), key=lambda x: x[1], reverse=True)[:cutoff]
        )

    def run(self) -> DataLineageGraph:
        graph = nx.DiGraph()
        module_nodes = []

        def normalise_path(path: str) -> str:
            return str(path).replace("\\", "/").strip().lower()

        for file_path in self.repo_path.rglob("*"):
            if file_path.suffix.lower() in [
                ".py",
                ".js",
                ".ts",
                ".sql",
                ".yaml",
                ".yml",
            ]:
                try:
                    module = analyse_module(file_path)

                    # --- Read full source code and docstrings ---
                    source_code, docstring, extra_docstrings = "", "", {}
                    if file_path.suffix.lower() == ".py":
                        try:
                            source_code = file_path.read_text(encoding="utf-8")
                            tree = ast.parse(source_code)

                            # Module-level docstring
                            docstring = ast.get_docstring(tree) or ""

                            # Collect function/class docstrings
                            for node in ast.walk(tree):
                                if isinstance(
                                    node,
                                    (
                                        ast.FunctionDef,
                                        ast.AsyncFunctionDef,
                                        ast.ClassDef,
                                    ),
                                ):
                                    doc = ast.get_docstring(node) or ""
                                    if doc:
                                        extra_docstrings[node.name] = doc
                        except Exception as e:
                            logging.warning(
                                f"[Surveyor] Failed to extract code/docstrings from {file_path}: {e}"
                            )

                    elif file_path.suffix.lower() in [".yml", ".yaml", ".sql"]:
                        try:
                            source_code = file_path.read_text(encoding="utf-8")
                        except Exception as e:
                            logging.warning(
                                f"[Surveyor] Failed to read {file_path}: {e}"
                            )

                    # populate attrs
                    module.attrs["code"] = source_code
                    module.attrs["docstring"] = docstring
                    if extra_docstrings:
                        module.attrs["function_docstrings"] = extra_docstrings

                    module_nodes.append(module)

                    # Normalised path
                    norm_path = normalise_path(module.path)

                    # Add node with all attributes
                    graph.add_node(
                        norm_path,
                        imports=module.imports,
                        functions=module.functions,
                        classes=[c.to_dict() for c in module.classes],
                        pairs=module.pairs,
                        tables=module.tables,
                        queries=module.queries,
                        attrs=module.attrs,
                    )

                    # Add edges for imports
                    for imp in module.imports:
                        graph.add_edge(
                            norm_path, normalise_path(imp), type=EdgeType.IMPORT.value
                        )

                    # Add edges for SQL tables
                    for table in module.tables:
                        graph.add_edge(
                            norm_path, normalise_path(table), type=EdgeType.SQL.value
                        )

                    # Add edges for YAML pairs
                    for pair in module.pairs:
                        if pair["value"] is not None:
                            graph.add_edge(
                                norm_path,
                                f"{pair['key']}={pair['value']}",
                                type=EdgeType.CONFIG.value,
                            )
                        else:
                            graph.add_edge(
                                norm_path, pair["key"], type=EdgeType.DAG.value
                            )

                except Exception as e:
                    logging.warning(f"[Surveyor] Failed to analyse {file_path}: {e}")
                    continue

        pagerank_scores = nx.pagerank(graph) if graph.number_of_nodes() > 0 else {}
        velocity = self.extract_git_velocity()
        dead_code = self.detect_dead_code(module_nodes)
        blast_radius = self.compute_blast_radius(graph)

        return DataLineageGraph(
            nodes=[m.to_dict() for m in module_nodes],
            edges=[
                Edge(source=u, target=v, type=d["type"]).to_dict()
                for u, v, d in graph.edges(data=True)
            ],
            pagerank=pagerank_scores,
            velocity={"hotspots": velocity["hotspots"], "dead_code_summary": dead_code},
            blast_radius=blast_radius,
        )
