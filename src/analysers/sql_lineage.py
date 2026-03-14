# src/analysers/sql_lineage.py
# Extract lineage from SQL files

import logging
from pathlib import Path

import sqlglot

logging.basicConfig(level=logging.INFO)


class SQLLineageAnalyser:
    """
    Analyser for SQL files to extract table-level and column-level lineage.
    Summarised for downstream semantic analysis.
    """

    def __init__(self, sql_file: Path):
        self.sql_file = sql_file

    def extract(self):
        edges = []
        try:
            sql_text = self.sql_file.read_text(encoding="utf-8")
            parsed = sqlglot.parse(sql_text)
            for stmt in parsed:
                for src, tgt in sqlglot.lineage(stmt):
                    edges.append({"source": src, "target": tgt, "type": "table"})
        except Exception as e:
            logging.error(f"[SQLLineageAnalyser] Failed to parse {self.sql_file}: {e}")
        return edges
