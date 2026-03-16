# src/analysers/python_dataflow_analyser.py
# The Brownfield Cartographer Python Dataflow Analyser


import ast
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)


class PythonDataFlowAnalyser:
    """
    Analyser for Python ETL scripts.
    Identifies data sources, sinks, transformations, and SQL queries.
    Summarised for lineage graph.
    """

    def __init__(self, file_path: Path):
        self.file_path = file_path

    def extract(self):
        edges = []
        try:
            code = self.file_path.read_text(encoding="utf-8")
            tree = ast.parse(code)

            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                    if func_name in ["read_csv", "read_sql", "read_parquet"]:
                        edges.append(
                            {
                                "source": str(self.file_path),
                                "target": f"DataFrame:{func_name}",
                                "type": "source",
                            }
                        )
                    elif func_name in ["to_csv", "to_sql", "to_parquet"]:
                        edges.append(
                            {
                                "source": f"DataFrame:{func_name}",
                                "target": str(self.file_path),
                                "type": "sink",
                            }
                        )
                    elif func_name in ["groupby", "merge", "join", "concat"]:
                        edges.append(
                            {
                                "source": "DataFrame",
                                "target": f"DataFrame:{func_name}",
                                "type": "transform",
                                "attrs": {
                                    "function": func_name,
                                    "lineno": getattr(node, "lineno", None),
                                },
                            }
                        )
                    if node.func.attr == "execute":
                        edges.append(
                            {
                                "source": str(self.file_path),
                                "target": "SQLAlchemy:execute",
                                "type": "sql",
                                "attrs": {
                                    "function": node.func.attr,
                                    "lineno": getattr(node, "lineno", None),
                                },
                            }
                        )
        except Exception as e:
            logging.warning(
                f"[PythonDataFlowAnalyser] Failed to parse {self.file_path}: {e}"
            )
        return edges
