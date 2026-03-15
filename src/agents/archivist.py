# src/agents/archivist.py
# The Brownfield Cartographer Archivist

import logging
from pathlib import Path
from typing import Any, Dict

from src.models.models import DataLineageGraph

logging.basicConfig(level=logging.INFO)


class Archivist:
    """
    Archivist generates human-readable documentation from the KnowledgeGraph.
    Produces CODEBASE.md, onboarding briefs, and day-one guides.
    """

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        # Repo name derived from folder name
        self.repo_name = repo_path.name

    def generate_codebase_md(self, knowledge_graph: Dict[str, Any]) -> str:
        """
        Create CODEBASE.md: a high-level overview of modules, lineage, and bridge nodes.
        """
        module_nodes = knowledge_graph["graphs"]["module"]["nodes"]
        lineage_nodes = knowledge_graph["graphs"]["lineage"]["nodes"]
        bridge_nodes = knowledge_graph["analytics"]["cross_graph"]["bridge_nodes"]

        doc = [f"# CODEBASE Overview: {self.repo_name}\n"]
        doc.append("## Module Graph\n")
        doc.append(f"- Total modules: {len(module_nodes)}\n")
        doc.append("### Example Modules:\n")
        for node in module_nodes[:10]:
            doc.append(f"- {node['id']}\n")

        doc.append("\n## Lineage Graph\n")
        doc.append(f"- Total lineage nodes: {len(lineage_nodes)}\n")
        doc.append("### Example Lineage Entities:\n")
        for node in lineage_nodes[:10]:
            doc.append(f"- {node['id']} ({node['attrs'].get('type','')})\n")

        doc.append("\n## Bridge Nodes\n")
        doc.append(f"- Identified connectors: {len(bridge_nodes)}\n")
        for b in bridge_nodes[:10]:
            doc.append(f"- {b}\n")

        return "\n".join(doc)

    def generate_onboarding_brief(self, knowledge_graph: Dict[str, Any]) -> str:
        """
        Create a short onboarding brief for new engineers.
        """
        bridge_nodes = knowledge_graph["analytics"]["cross_graph"]["bridge_nodes"]
        blast_radius = knowledge_graph["analytics"]["cross_graph"]["blast_radius"]

        brief = [f"# Onboarding Brief for {self.repo_name}\n"]
        brief.append(
            f"Welcome to the {self.repo_name} codebase. Here are key insights:\n"
        )
        brief.append(
            f"- There are {len(bridge_nodes)} bridge nodes connecting code and data pipelines.\n"
        )
        brief.append(
            "- Focus first on these connectors, as they have the highest impact.\n"
        )
        brief.append(
            "- Blast radius analysis shows which modules affect the most downstream nodes.\n"
        )

        # Highlight top 3 by blast radius
        top_nodes = sorted(blast_radius.items(), key=lambda x: x[1], reverse=True)[:3]
        brief.append("\n## Top Impact Nodes\n")
        for node, radius in top_nodes:
            brief.append(f"- {node} (impacts {radius} downstream nodes)\n")

        return "\n".join(brief)

    def generate_day_one_guide(self, semanticist_answers: Dict[str, Any]) -> str:
        """
        Create a Day-One guide answering the Five FDE questions with structured evidence.
        """
        guide = [f"# Day-One Guide for {self.repo_name}\n"]
        guide.append("This guide answers the Five FDE Day-One Questions:\n")

        answers = semanticist_answers.get("day_one_answers", "")
        evidence = semanticist_answers.get("evidence", {})

        # Split answers into lines if the model returned them as a block
        answer_lines = [line.strip() for line in answers.split("\n") if line.strip()]

        questions = [
            "Primary Data Ingestion Path",
            "Critical Output Datasets/Endpoints",
            "Blast Radius of Critical Module Failure",
            "Business Logic Concentration vs. Distribution",
            "Most Frequent Changes in Last 90 Days",
        ]

        for i, q in enumerate(questions, 1):
            guide.append(f"\n## {i}. {q}\n")
            if i - 1 < len(answer_lines):
                guide.append(answer_lines[i - 1])
            # Attach evidence if available
            if i == 1 and "ingestion_nodes" in evidence:
                guide.append(f"- Evidence: {evidence['ingestion_nodes']}")
            elif i == 2 and "critical_edges" in evidence:
                guide.append(f"- Evidence: {evidence['critical_edges']}")
            elif i == 3 and "blast_radius" in evidence:
                guide.append(f"- Evidence: {evidence['blast_radius']}")
            elif i == 4 and "pagerank" in evidence:
                guide.append(f"- Evidence: {evidence['pagerank']}")
            elif i == 5 and "velocity" in evidence:
                guide.append(f"- Evidence: {evidence['velocity']}")

        return "\n".join(guide)
