<h1 align="center"> The Brownfield Cartographer </h1>

[![CI](https://github.com/nuhaminae/The-Brownfield-Cartographer/actions/workflows/CI.yml/badge.svg)](https://github.com/nuhaminae/The-Brownfield-Cartographer/actions/workflows/CI.yml)
![Black Formatting](https://img.shields.io/badge/code%20style-black-000000.svg)
![isort Imports](https://img.shields.io/badge/imports-isort-blue.svg)
![Flake8 Lint](https://img.shields.io/badge/lint-flake8-yellow.svg)

---

## Project Review

The Brownfield Cartographer is a multi‑agent codebase intelligence system designed to accelerate **Forward Deployed Engineer (FDE)** onboarding in brownfield environments.  
It ingests any GitHub repository or local path and produces a **living, queryable knowledge graph** of the system’s architecture, data flows, and semantic structure.  

This project directly addresses the **Day‑One Problem**: within 72 hours, an FDE must become useful in a large, undocumented production codebase. The Cartographer reduces navigation blindness, contextual amnesia, dependency opacity, and silent debt by building instruments that make codebases legible.

---

## Key Feature

- **Surveyor (Phase 1)**:  
  Static structure analysis using tree‑sitter. Builds module graphs, detects imports, computes PageRank, identifies dead code, and overlays git velocity.  

- **Hydrologist (Phase 2)**:  
  Data lineage analysis across Python, SQL, and YAML. Constructs DAGs of data flow, identifies sources and sinks, and computes blast radius for module failures.  

- **Semanticist (Phase 3)**:  
  LLM‑powered semantic enrichment. Generates purpose statements, detects documentation drift, clusters modules into domains, and synthesises answers to the Five FDE Day‑One Questions.  

- **Archivist (Phase 4)**:  
  Produces living artifacts: `CODEBASE.md`, onboarding briefs, semantic indexes, and trace logs. Maintains context for AI agents and human engineers.  

- **Navigator (Phase 5)**:  
  Interactive query interface. Supports dependency queries, lineage tracing, blast radius analysis, and module explanations. Enables both natural language and structured interrogation of the knowledge graph.  

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
- [Architecture Diagram](#architecture-diagram)
- [Day-One Accuracy Analysis](#day-one-accuracy-analysis)
- [Limitations](#limitations)
- [FDE Applicability](#fde-applicability)
- [Self-Audit Results](#self-audit-results)
- [Project Status](#project-status)

---

## Project Structure (Snippet)

```bash
The-Brownfield-Cartographer/
├── src/
│   ├── cli.py                  # Entry point, runs analysis
│   ├── orchestrator.py         # Wires all agents, serialises outputs
│   ├── models/                 # Pydantic schemas (Node, Edge, Graph)
│   ├── analyzers/              # AST, SQL, DAG parsers
│   ├── agents/                 # Surveyor, Hydrologist, Semanticist, Archivist, Navigator
│   └── graph/knowledge_graph.py# NetworkX wrapper, integration
├── .cartography/               # Analysis artifacts
│   ├── module_graph.json
│   ├── lineage_graph.json
│   ├── knowledge_graph.json
│   ├── CODEBASE.md
│   ├── onboarding_brief.md
│   └── cartography_trace.jsonl
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
git clone https://github.com/nuhaminae/The-Brownfield-Cartographer.git
cd The-Brownfield-Cartographer
uv sync   # recommended
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

# Step by step execution
python -m src.cli --repo ./meltano --days 90 --phase surveyor
python -m src.cli --repo ./meltano --days 90 --phase hydrologist
python -m src.cli --repo ./meltano --days 90 --phase semanticist
python -m src.cli --repo ./meltano --days 90 --phase archivist
python -m src.cli --repo ./meltano --days 90 --phase navigator

```

Artifacts will be written to `.cartography/` (or your chosen output directory).

---

## Architecture Diagram

**Pipeline Design Rationale:**  
Surveyor builds the structural skeleton → Hydrologist overlays lineage → Semanticist adds semantic meaning → Archivist produces living artifacts → Navigator enables interactive queries.  
The knowledge graph is the central data store, combining structural, lineage, and semantic layers.  

---

## Day-One Accuracy Analysis

Manual reconnaissance vs. system outputs showed:  

- **Correct:** Velocity hotspots, blast radius candidates.  
- **Weak:** Ingestion detection (Surveyor missed taps), critical outputs (Hydrologist edges not mapped to datasets), business logic concentration (Pagerank skewed to configs).  
- **Root Causes:** Sparse ingestion signals, pagerank noise, lineage limited to direct descendants.  

*(See RECONNAISSANCE.md for full side-by-side comparison.)*

---

## Limitations

The Cartographer accelerates onboarding but cannot fully replace human judgment.  

- Dynamic SQL/Python references unresolved.  
- Semantic clustering mislabels domains.  
- Pagerank overweights configs.  
- Ingestion detection fails when sources are abstracted.  
- Business rules and organizational context remain opaque.  

---

## FDE Applicability

In a real client engagement, the Cartographer would be deployed on Day One to rapidly map the system. Surveyor and Hydrologist provide visibility, Semanticist adds meaning, Archivist produces living documentation, and Navigator enables interactive Q&A. This transforms the first 72 hours from guesswork into evidence‑driven onboarding, with human engineers validating ingestion paths and interpreting ambiguous lineage.

---

## Self-Audit Results

Running the Cartographer on the Week 1 repo revealed discrepancies:  

- Manual notes described ingestion as “simple CSV load.”  
- Cartographer flagged hidden dependencies.  
- This exposed blind spots in documentation and validated the Cartographer’s ability to surface overlooked complexity.  

---

## Project Status

The project is completed. Check the [commit history](https://github.com/nuhaminae/The-Brownfield-Cartographer/) for update.
