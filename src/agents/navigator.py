# src/agents/navigator.py
# The Brownfield Cartographer Navigator


from typing import Any, Dict, List

import networkx as nx


class Navigator:
    """
    Navigator provides interactive exploration of the Module and Lineage graphs.
    Supports queries like: find dependencies, trace lineage, search by attributes,
    shortest paths, and blast radius analysis.
    """

    def __init__(self, module_graph: Dict[str, Any], lineage_graph: Dict[str, Any]):
        # Build directed graphs from JSON-like dicts
        self.module_graph = self._build_graph(module_graph)
        self.lineage_graph = self._build_graph(lineage_graph)

        # Merge graphs into a unified view for cross-queries
        self.merged = nx.compose(self.module_graph, self.lineage_graph)

    def _build_graph(self, graph_dict: Dict[str, Any]) -> nx.DiGraph:
        """
        Convert a graph dictionary (with nodes and edges) into a NetworkX DiGraph.
        """
        G = nx.DiGraph()
        for node in graph_dict.get("nodes", []):
            G.add_node(node["id"], attrs=node.get("attrs", {}))
        for edge in graph_dict.get("edges", []):
            G.add_edge(edge["source"], edge["target"], type=edge.get("type", ""))
        return G

    def find_dependencies(self, node_id: str) -> List[str]:
        """
        Return direct dependencies (successors) of a given node.
        """
        if node_id not in self.merged:
            return []
        return list(self.merged.successors(node_id))

    def trace_lineage(self, node_id: str) -> Dict[str, List[str]]:
        """
        Trace full lineage: all predecessors and successors of a node.
        """
        if node_id not in self.merged:
            return {"predecessors": [], "successors": []}
        return {
            "predecessors": list(nx.ancestors(self.merged, node_id)),
            "successors": list(nx.descendants(self.merged, node_id)),
        }

    def search_by_attribute(self, key: str, value: Any) -> List[str]:
        """
        Search nodes by attribute key/value.
        Example: search_by_attribute("python_module", "tap_github")
        """
        results = []
        for node, data in self.merged.nodes(data=True):
            attrs = data.get("attrs", {})
            if attrs.get(key) == value:
                results.append(node)
        return results

    def shortest_path(self, source: str, target: str) -> List[str]:
        """
        Find shortest path between two nodes.
        """
        try:
            return nx.shortest_path(self.merged, source=source, target=target)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def blast_radius(self, node_id: str) -> int:
        """
        Return blast radius (number of downstream nodes).
        """
        if node_id not in self.merged:
            return 0
        return len(nx.descendants(self.merged, node_id))
