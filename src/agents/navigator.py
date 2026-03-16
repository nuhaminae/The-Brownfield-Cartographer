# src/agents/navigator.py
# The Brownfield Cartographer Navigator


from typing import Any, Dict, List

import networkx as nx


class Navigator:
    """
    Navigator Agent: unified query interface over Module and Lineage graphs.
    Designed to be wrapped as a LangGraph agent with four tools.
    """

    def __init__(self, module_graph: Dict[str, Any], lineage_graph: Dict[str, Any]):
        # Handle both cases: JSON with "graphs" or direct nodes/edges
        module_dict = module_graph.get("graphs", {}).get("module", module_graph)
        lineage_dict = lineage_graph.get("graphs", {}).get("lineage", lineage_graph)

        self.module_graph = self._build_graph(module_dict, graph_type="module")
        self.lineage_graph = self._build_graph(lineage_dict, graph_type="lineage")

        # Merge graphs into a unified view
        self.merged = nx.compose(self.module_graph, self.lineage_graph)

    def _build_graph(self, graph_dict: Dict[str, Any], graph_type: str) -> nx.DiGraph:
        G = nx.DiGraph()
        for node in graph_dict.get("nodes", []):
            if isinstance(node, list):
                node_id, node_data = node
            elif isinstance(node, dict):
                node_id = node.get("id") or node.get("path")
                node_data = node
            else:
                continue

            attrs = node_data.get("attrs", {})
            G.add_node(
                node_id,
                file_path=node_data.get("path") or attrs.get("file", ""),
                line_range=attrs.get("line_range", attrs.get("lineno", "")),
                analysis_method=(
                    "static analysis"
                    if graph_type in ["module", "lineage"]
                    else "unknown"
                ),
                attrs=attrs,
            )

        for edge in graph_dict.get("edges", []):
            if isinstance(edge, list):
                src, tgt, edge_data = edge
            elif isinstance(edge, dict):
                src, tgt, edge_data = edge["source"], edge["target"], edge
            else:
                continue

            attrs = edge_data.get("attrs", {})
            G.add_edge(
                src,
                tgt,
                type=edge_data.get("type", ""),
                file_path=attrs.get("file", ""),
                line_range=str(attrs.get("lineno", "")),
                analysis_method=(
                    "static analysis" if graph_type == "lineage" else "unknown"
                ),
                attrs=attrs,
            )
        return G

    # === Query tools ===
    def find_dependencies(self, node_id: str) -> Dict[str, Any]:
        if node_id not in self.merged:
            return {"dependencies": [], "evidence": []}
        deps, evidence = [], []
        for succ in self.merged.successors(node_id):
            node_attrs = self.merged.nodes[succ]
            deps.append(succ)
            evidence.append(
                {
                    "file": node_attrs.get("file_path"),
                    "lines": node_attrs.get("line_range"),
                    "method": node_attrs.get("analysis_method"),
                }
            )
        return {"dependencies": deps, "evidence": evidence}

    def trace_lineage(self, node_id: str) -> Dict[str, Any]:
        if node_id not in self.merged:
            return {"predecessors": [], "successors": [], "evidence": []}
        preds = list(nx.ancestors(self.merged, node_id))
        succs = list(nx.descendants(self.merged, node_id))
        evidence = []
        for n in preds + succs:
            node_attrs = self.merged.nodes[n]
            evidence.append(
                {
                    "node": n,
                    "file": node_attrs.get("file_path"),
                    "lines": node_attrs.get("line_range"),
                    "method": node_attrs.get("analysis_method"),
                }
            )
        return {"predecessors": preds, "successors": succs, "evidence": evidence}

    def search_by_attribute(self, key: str, value: Any) -> List[str]:
        return [
            node
            for node, data in self.merged.nodes(data=True)
            if data.get("attrs", {}).get(key) == value
        ]

    def shortest_path(self, source: str, target: str) -> List[str]:
        try:
            return nx.shortest_path(self.merged, source=source, target=target)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def blast_radius(self, node_id: str) -> int:
        return (
            len(nx.descendants(self.merged, node_id)) if node_id in self.merged else 0
        )


# How to use
# import json
# from src.agents.navigator import Navigator
#
# with open(".cartography/module_graph.json") as f:
#    module_graph = json.load(f)
#
# with open(".cartography/lineage_graph.json") as f:
#    lineage_graph = json.load(f)
#
# nav = Navigator(module_graph, lineage_graph)
#
# print(nav.find_dependencies("meltano\\tests\\meltano\\core\\tracking\\test"))
# print(nav.trace_lineage("lineage:tap-gitlab"))
