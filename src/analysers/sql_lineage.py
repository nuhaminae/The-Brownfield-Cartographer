# src/analysers/sql_lineage.py
# Extract lineage from SQL files


from pathlib import Path

import sqlglot


def extract_sql_lineage(sql_file: Path):
    """
    Parse SQL file and extract lineage edges (source -> target tables).
    Returns a list of edges: [{"source": ..., "target": ...}]
    """
    edges = []
    with open(sql_file, "r", encoding="utf-8") as f:
        sql_text = f.read()

    try:
        parsed = sqlglot.parse(sql_text)
        for stmt in parsed:
            # Extract lineage: e.g., SELECT col FROM source_table -> target_table
            lineage = sqlglot.lineage(stmt)
            for src, tgt in lineage:
                edges.append({"source": src, "target": tgt})
    except Exception as e:
        print(f"[SQL Lineage] Failed to parse {sql_file}: {e}")

    return edges
