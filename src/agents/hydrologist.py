# src/agents/hydrologist.py
# The Brownfield Cartographer Hydrologist

from pathlib import Path

import networkx as nx

from src.analysers.dag_config_parser import parse_dag_config
from src.analysers.sql_lineage import extract_sql_lineage
from src.models.models import Edge, EdgeType, GraphSchema


def run_hydrologist(repo_path: Path) -> GraphSchema:
    """
    Build the Data Lineage Graph:
    - Extract SQL dependencies (tables, columns) using sqlglot.
    - Parse YAML configs (Airflow/dbt/Meltano) for DAG structure.
    - Identify sources and sinks.
    - Compute blast radius (downstream impact of changes).
    """

    graph = nx.DiGraph()

    # --- SQL lineage ---
    for sql_file in repo_path.rglob("*.sql"):
        lineage_edges = extract_sql_lineage(sql_file)
        for edge in lineage_edges:
            e = Edge(source=edge["source"], target=edge["target"], type=EdgeType.SQL)
            graph.add_edge(e.source, e.target, type=e.type.value)

    # --- DAG configs (YAML) ---
    for yaml_file in list(repo_path.rglob("*.yml")) + list(repo_path.rglob("*.yaml")):
        dag_edges, node_attrs = parse_dag_config(yaml_file)

        # Add edges
        for edge in dag_edges:
            e = Edge(source=edge["source"], target=edge["target"], type=EdgeType.DAG)
            graph.add_edge(e.source, e.target, type=e.type.value)

        # Add node attributes
        for node, attrs in node_attrs.items():
            if node not in graph.nodes:
                graph.add_node(node)
            graph.nodes[node].update(attrs)

    # Identify sources (nodes with no incoming edges) and sinks (nodes with no outgoing edges)
    sources = [n for n in graph.nodes if graph.in_degree(n) == 0]
    sinks = [n for n in graph.nodes if graph.out_degree(n) == 0]

    # Compute blast radius: for each node, how many downstream nodes are impacted
    blast_radius = {node: len(nx.descendants(graph, node)) for node in graph.nodes}

    # Wrap in schema for serialization
    lineage_graph = GraphSchema(
        nodes=[{"id": n, "attrs": graph.nodes[n]} for n in graph.nodes],
        edges=[
            Edge(source=u, target=v, type=d["type"]).to_dict()
            for u, v, d in graph.edges(data=True)
        ],
        sources=sources,
        sinks=sinks,
        blast_radius=blast_radius,
    )

    return lineage_graph
