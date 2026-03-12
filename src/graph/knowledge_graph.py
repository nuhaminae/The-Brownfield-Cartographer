# src/graph/knowledge_graph.py
# The Brownfield Cartographer Knowledge Graph


from typing import Any, Dict

import networkx as nx

from src.models.models import Edge, GraphSchema


class KnowledgeGraph:
    """
    Wrapper around NetworkX to unify multiple graphs (module + lineage).
    Provides serialisation and integration utilities.
    """

    def __init__(self):
        self.graphs: Dict[str, nx.DiGraph] = {}

    def add_graph(self, name: str, graph_schema: GraphSchema):
        """
        Add a graph from a GraphSchema object.
        Ensures nodes and edges are consistently typed.
        """
        g = nx.DiGraph()

        # Add nodes
        for node in graph_schema.nodes:
            # If node looks like a ModuleNode dict, normalize
            node_id = node.get("id") or node.get("path")
            attrs = node.get("attrs", {})
            g.add_node(node_id, **attrs)

        # Add edges
        for edge in graph_schema.edges:
            # Normalize into Edge model
            e = Edge(
                source=edge["source"],
                target=edge["target"],
                type=edge.get("type", "import"),
            )
            g.add_edge(e.source, e.target, type=e.type.value)

        self.graphs[name] = g

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialise all graphs into a dictionary for JSON export.
        """
        return {
            name: {
                "nodes": [{"id": n, **data} for n, data in g.nodes(data=True)],
                "edges": [
                    Edge(source=u, target=v, type=data.get("type", "import")).to_dict()
                    for u, v, data in g.edges(data=True)
                ],
            }
            for name, g in self.graphs.items()
        }

    def merge_graphs(self) -> nx.DiGraph:
        """
        Merge all graphs into a single unified NetworkX DiGraph.
        """
        merged = nx.DiGraph()
        for g in self.graphs.values():
            merged.add_nodes_from(g.nodes(data=True))
            merged.add_edges_from(g.edges(data=True))
        return merged
