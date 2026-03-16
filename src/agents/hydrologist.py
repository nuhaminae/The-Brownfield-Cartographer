# src/agents/hydrologist.py
# The Brownfield Cartographer Hydrologist

import logging
from pathlib import Path
from typing import List

import networkx as nx

from src.analysers.dag_config_analyser import DAGConfigAnalyser
from src.analysers.python_dataflow_analyser import PythonDataFlowAnalyser
from src.analysers.sql_lineage import SQLLineageAnalyser
from src.models.models import DataLineageGraph, Edge, EdgeType

logging.basicConfig(level=logging.INFO)


class Hydrologist:
    """
    Hydrologist builds the Data Lineage Graph:
    - Extracts SQL dependencies (tables + columns)
    - Parses configs (Airflow/dbt/Meltano) for DAG structure
    - Parses Python ETL scripts for sources/sinks/transformations
    - Identifies sources and sinks
    - Computes blast radius (summarised)
    """

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.graph = nx.DiGraph()

    # --- SQL lineage ---
    def analyse_sql(self, sql_file: Path):
        try:
            analyser = SQLLineageAnalyser(sql_file)
            edges = analyser.extract()
            for edge in edges:
                e = Edge(
                    source=str(sql_file),
                    target=edge["target"],
                    type=self.normalise_edge_type(edge.get("type", "sql")),
                    attrs=edge.get("attrs", {}),
                )
                self.graph.add_edge(
                    e.source, e.target, type=e.type.value, attrs=e.attrs
                )
            # Add node metadata
            self.graph.add_node(str(sql_file), file=str(sql_file), type="sql")
        except Exception as e:
            logging.warning(f"[Hydrologist] Failed to analyse SQL file {sql_file}: {e}")

    # --- DAG configs (YAML/JSON) ---
    def analyse_dag(self, config_file: Path):
        try:
            analyser = DAGConfigAnalyser(config_file)
            dag_edges, node_attrs = analyser.parse()
            for edge in dag_edges:
                e = Edge(
                    source=edge["source"],
                    target=edge["target"],
                    type=self.normalise_edge_type(edge.get("type", "dag")),
                    attrs=edge.get("attrs", {}),
                )
                self.graph.add_edge(
                    e.source, e.target, type=e.type.value, attrs=e.attrs
                )
            for node, attrs in node_attrs.items():
                self.graph.add_node(node, file=str(config_file), type=attrs.get("type"))
        except Exception as e:
            logging.warning(
                f"[Hydrologist] Failed to analyse DAG config {config_file}: {e}"
            )

    # --- Python ---
    def analyse_python(self, py_file: Path):
        try:
            analyser = PythonDataFlowAnalyser(py_file)
            edges = analyser.extract()
            for edge in edges:
                e = Edge(
                    source=edge["source"],
                    target=edge["target"],
                    type=self.normalise_edge_type(edge.get("type", "transform")),
                    attrs=edge.get("attrs", {}),
                )
                self.graph.add_edge(
                    e.source, e.target, type=e.type.value, attrs=e.attrs
                )
            # Add node metadata
            self.graph.add_node(str(py_file), file=str(py_file), type="python")
        except Exception as e:
            logging.warning(
                f"[Hydrologist] Failed to analyse Python file {py_file}: {e}"
            )

    def normalise_edge_type(self, raw_type: str) -> EdgeType:
        mapping = {
            "source": EdgeType.SOURCE,
            "sink": EdgeType.SINK,
            "transform": EdgeType.DATAFLOW,
            "sql": EdgeType.SQL,
            "dag": EdgeType.DAG,
            "table": EdgeType.SQL,
            "airflow": EdgeType.DAG,
            "dbt": EdgeType.DAG,
        }
        return mapping.get(raw_type, EdgeType.DATAFLOW)

    def run(self) -> DataLineageGraph:
        for sql_file in self.repo_path.rglob("*.sql"):
            self.analyse_sql(sql_file)
        for config_file in (
            list(self.repo_path.rglob("*.yml"))
            + list(self.repo_path.rglob("*.yaml"))
            + list(self.repo_path.rglob("*.json"))
        ):
            self.analyse_dag(config_file)
        for py_file in self.repo_path.rglob("*.py"):
            self.analyse_python(py_file)

        sources = [n for n in self.graph.nodes if self.graph.in_degree(n) == 0]
        sinks = [n for n in self.graph.nodes if self.graph.out_degree(n) == 0]

        # Compute blast radius: for each node, how many downstream nodes are impacted
        blast_radius = {
            node: len(nx.descendants(self.graph, node)) for node in self.graph.nodes
        }
        cutoff = max(1, int(len(blast_radius) * 0.1))
        blast_radius = dict(
            sorted(blast_radius.items(), key=lambda x: x[1], reverse=True)[:cutoff]
        )

        return DataLineageGraph(
            nodes=[{"id": n, "attrs": self.graph.nodes[n]} for n in self.graph.nodes],
            edges=[
                Edge(
                    source=u, target=v, type=d["type"], attrs=d.get("attrs", {})
                ).to_dict()
                for u, v, d in self.graph.edges(data=True)
            ],
            sources=sources,
            sinks=sinks,
            blast_radius=blast_radius,
        )

    def update_nodes(self, changed_files: List[str]) -> None:
        """
        Incrementally re-analyse only the changed files and update the lineage graph.
        This avoids re-running the full hydrologist analysis on the entire repo.
        """
        for file_path in changed_files:
            path_obj = Path(file_path)
            if not path_obj.exists():
                continue

            # Remove old node/edges for this file if present
            if self.graph.has_node(str(path_obj)):
                self.graph.remove_node(str(path_obj))

            # Re-analyse based on file type
            if path_obj.suffix.lower() == ".sql":
                self.analyse_sql(path_obj)
            elif path_obj.suffix.lower() in [".yml", ".yaml", ".json"]:
                self.analyse_dag(path_obj)
            elif path_obj.suffix.lower() == ".py":
                self.analyse_python(path_obj)

        # Recompute sources, sinks, blast radius after updates
        sources = [n for n in self.graph.nodes if self.graph.in_degree(n) == 0]
        sinks = [n for n in self.graph.nodes if self.graph.out_degree(n) == 0]
        blast_radius = {
            node: len(nx.descendants(self.graph, node)) for node in self.graph.nodes
        }
        cutoff = max(1, int(len(blast_radius) * 0.1))
        blast_radius = dict(
            sorted(blast_radius.items(), key=lambda x: x[1], reverse=True)[:cutoff]
        )

        # Update stored DataLineageGraph
        self.data_graph = DataLineageGraph(
            nodes=[{"id": n, "attrs": self.graph.nodes[n]} for n in self.graph.nodes],
            edges=[
                Edge(
                    source=u, target=v, type=d["type"], attrs=d.get("attrs", {})
                ).to_dict()
                for u, v, d in self.graph.edges(data=True)
            ],
            sources=sources,
            sinks=sinks,
            blast_radius=blast_radius,
        )
