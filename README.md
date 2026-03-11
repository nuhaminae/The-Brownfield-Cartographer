<h1 align="center"> The Brownfield Cartographer </h1>

[![CI](https://github.com/nuhaminae/The-Brownfield-Cartographer/actions/workflows/CI.yml/badge.svg)](https://github.com/nuhaminae/The-Brownfield-Cartographer/actions/workflows/CI.yml)
![Black Formatting](https://img.shields.io/badge/code%20style-black-000000.svg)
![isort Imports](https://img.shields.io/badge/imports-isort-blue.svg)
![Flake8 Lint](https://img.shields.io/badge/lint-flake8-yellow.svg)

---

## Project Review

The Brownfield Cartographer is a multi‑agent system designed to analyse legacy codebases (brownfields) and produce actionable insights.  
It builds static and dynamic dependency graphs, extracts semantic meaning, overlays temporal velocity data, and generates recommendations for stabilisation and refactoring.

---

## Key Feature

- **Surveyor**: Static structure analysis (AST parsing, module graph, git velocity).  
- **Hydrologist**: Data lineage analysis (SQL lineage, DAG configs, blast radius).  
- **Semantisist**: Semantic enrichment (docstrings, classification, architectural smells).  
- **Archivist**: Temporal overlays (commit history, churn hotspots).  
- **Navigator**: Integration, CLI orchestration, recommendations, roadmap.  

---

## Table of Contents

- [Project Review](#project-review)
- [Key Feature](#key-feature)
- [Table of Contents](#table-of-contents)
- [Project Structure (Snippet)](#project-structure-snippet)
- [Installation](#installation)
  - [Prerequisites](#prerequisites)
  - [Setup](#setup)
- [Usage](#usage)
- [Project Status](#project-status)

---

## Project Structure (Snippet)

```bash
The-Brownfield-Cartographer/
├── src/
│   ├── cli.py                  # Entry point, runs analysis
│   ├── orchestrator.py         # Wires Surveyor + Hydrologist, serialises outputs
│   ├── models/                 # Pydantic schemas (Node, Edge, Graph)
│   │   ├── module_node.py
│   │   ├── edge.py
│   │   └── graph_schema.py
│   ├── analysers/
│   │   ├── tree_sitter_analyser.py   # AST parsing with LanguageRouter
│   │   ├── sql_lineage.py            # SQL lineage via sqlglot
│   │   └── dag_config_parser.py      # YAML DAG config parsing
│   ├── agents/
│   │   ├── surveyor.py          # Module graph, PageRank, git velocity
│   │   └── hydrologist.py       # DataLineageGraph, blast radius
│   └── graph/
│       └── knowledge_graph.py   # NetworkX wrapper, integration
├── .cartography/
│   ├── module_graph.json        # Static structure graph
│   ├── lineage_graph.json       # Data lineage graph
│   └── knowledge_graph.json     # Combined graph (optional)
├── pyproject.toml               # Dependencies (locked with uv)
└── README.md                    # Documentation
```

---

## Installation

### Prerequisites

- Python 3.12  
- Git  
- Docker & Docker Compose  

### Setup

```bash
# Clone repo
git clone https://github.com/nuhaminae/The-Brownfield-Cartographer.git
cd The-Brownfield-Cartographer

# Install dependencies
pip install -r requirements.txt

# Or with uv (recommended)
uv sync
```

---

## Usage

Run the CLI entry point to analyse a repository:

```bash
# Analyse a local repo
python -m src.cli --repo ./meltano

# Analyse a GitHub repo
python -m src.cli --repo https://github.com/meltano/meltano

# Specify git velocity window (default 30 days)
python -m src.cli --repo ./meltano --days 60

# Specify output directory (default .cartography/)
python -m src.cli --repo ./meltano --output ./analysis_output
```

Artifacts will be written to `.cartography/` (or your chosen output directory):

- `module_graph.json` → Static module graph.  
- `lineage_graph.json` → Data lineage graph.  
- `knowledge_graph.json` → Combined graph (optional).  

---

## Project Status

The project is ongoing.  

- **Interim submission** delivers Phases 1–2 (Surveyor + Hydrologist) with CLI + Orchestrator and `.cartography/` artifacts.  

- **Final submission** delivers Phases 3–5 (Semantisist, Archivist, Navigator) with semantic enrichment, temporal overlays, and strategic recommendations.  

Check the [commit history](https://github.com/nuhaminae/The-Brownfield-Cartographer/) for progress.
