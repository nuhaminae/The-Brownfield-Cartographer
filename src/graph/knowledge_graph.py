# src/graph/knowledge_graph.py
# The Brownfield Cartographer Knowledge Graph

import networkx as nx

from src.models.models import DataLineageGraph, Edge


class KnowledgeGraph:
    """
    Wrapper around NetworkX to unify multiple graphs (module + lineage).
    Provides optional cross-graph analytics:
    - Blast radius summary
    - Bridge node detection
    Can be omitted if not required for downstream phases.
    """

    def __init__(self):
        self.graphs = {}
        self.enriched_metrics = {}

    def add_graph(self, name: str, graph_schema: DataLineageGraph):
        """
        Add a graph from a DataLineageGraph object.
        Ensures nodes and edges are consistently typed.
        """
        g = nx.DiGraph()

        # Add nodes
        for node in graph_schema.nodes:
            # If node looks like a ModuleNode dict, normalise
            node_id = node.get("id") or node.get("path")
            g.add_node(f"{name}:{node_id}", attrs=node.get("attrs", {}))
        # Add edges
        for edge in graph_schema.edges:
            # Normalise into Edge model
            e = Edge(
                source=f"{name}:{edge['source']}",
                target=f"{name}:{edge['target']}",
                type=edge.get("type", "import"),
            )
            g.add_edge(e.source, e.target, type=e.type.value)
        self.graphs[name] = g

    def run_cross_graph_analytics(self):
        merged = nx.compose_all(self.graphs.values())
        blast_radius = {
            node: len(nx.descendants(merged, node)) for node in merged.nodes
        }
        cutoff = max(1, int(len(blast_radius) * 0.1))
        blast_radius_summary = dict(
            sorted(blast_radius.items(), key=lambda x: x[1], reverse=True)[:cutoff]
        )
        bridge_nodes = [
            n
            for n in merged.nodes
            if merged.in_degree(n) > 0 and merged.out_degree(n) > 0
        ]
        self.enriched_metrics["cross_graph"] = {
            "blast_radius_summary": blast_radius_summary,
            "bridge_nodes": bridge_nodes,
        }

    def to_dict(self):
        return {
            "graphs": {
                name: {
                    "nodes": list(g.nodes(data=True)),
                    "edges": list(g.edges(data=True)),
                }
                for name, g in self.graphs.items()
            },
            "analytics": self.enriched_metrics,
        }
