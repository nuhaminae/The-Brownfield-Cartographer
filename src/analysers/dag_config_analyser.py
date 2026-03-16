# src/analysers/dag_config_analyser.py
# The Brownfield Cartographer DAG Config Analyser


import json
import logging
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO)


class DAGConfigAnalyser:
    """
    Analyser for Airflow/dbt/Meltano YAML/JSON configs.
    Extracts DAG edges and node attributes with summarised metadata.
    """

    def __init__(self, config_file: Path):
        self.config_file = config_file

    def parse(self):
        edges, node_attrs = [], {}
        try:
            text = self.config_file.read_text(encoding="utf-8")
            config = (
                yaml.safe_load(text)
                if self.config_file.suffix.lower() in [".yaml", ".yml"]
                else json.loads(text)
            )
        except Exception as e:
            logging.warning(
                f"[DAGConfigAnalyser] Failed to parse {self.config_file}: {e}"
            )
            return edges, node_attrs

        if not isinstance(config, dict):
            return edges, node_attrs

        # Summarise Meltano plugins
        if "plugins" in config and isinstance(config["plugins"], dict):
            for group, plugins in config["plugins"].items():
                if isinstance(plugins, list):
                    for plugin in plugins:
                        if "name" in plugin:
                            node_attrs[plugin["name"]] = {
                                "type": group[:-1],
                                "file": str(self.config_file),
                            }

        # Summarise Airflow tasks
        if "tasks" in config:
            for task in config.get("tasks", []):
                if "id" in task:
                    node_attrs[task["id"]] = {
                        "type": "task",
                        "file": str(self.config_file),
                    }
                if "upstream" in task and "id" in task:
                    for upstream in task["upstream"]:
                        edges.append(
                            {
                                "source": upstream,
                                "target": task["id"],
                                "type": "airflow",
                                "attrs": {
                                    "file": str(self.config_file),
                                    "task_type": "airflow_task",
                                },
                            }
                        )

        # Summarise dbt models
        if "models" in config:
            for model in config.get("models", []):
                if "name" in model:
                    node_attrs[model["name"]] = {
                        "type": "model",
                        "file": str(self.config_file),
                    }
                if "depends_on" in model and "name" in model:
                    for dep in model["depends_on"]:
                        edges.append(
                            {
                                "source": dep,
                                "target": model["name"],
                                "type": "dbt",
                                "attrs": {
                                    "file": str(self.config_file),
                                    "model_type": "dbt_model",
                                },
                            }
                        )
        return edges, node_attrs
