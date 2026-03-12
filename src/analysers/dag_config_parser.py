# src/analysers/dag_config_parser.py
# The Brownfield Cartographer DAG Config Parser

from pathlib import Path

import yaml


def parse_dag_config(yaml_file: Path):
    """
    Parse Airflow/dbt/Meltano YAML config to extract DAG edges.
    Returns a tuple: (edges, node_attrs)
    - edges: [{"source": ..., "target": ...}]
    - node_attrs: {node_name: {"type": ...}}
    """
    edges = []
    node_attrs = {}

    with open(yaml_file, "r", encoding="utf-8") as f:
        try:
            config = yaml.safe_load(f)
        except Exception as e:
            print(f"[DAG Config] Failed to parse {yaml_file}: {e}")
            return edges, node_attrs

    if not isinstance(config, dict):
        return edges, node_attrs

    # --- Meltano-style grouped plugins ---
    if "plugins" in config and isinstance(config["plugins"], dict):
        for group, plugins in config["plugins"].items():
            if isinstance(plugins, list):
                for plugin in plugins:
                    if "name" in plugin:
                        plugin_name = plugin["name"]
                        plugin_type = group[:-1] if group.endswith("s") else group
                        node_attrs[plugin_name] = {"type": plugin_type}

                        # Extractor → Loader
                        if group == "extractors":
                            for loader in config["plugins"].get("loaders", []):
                                if "name" in loader:
                                    edges.append(
                                        {
                                            "source": plugin_name,
                                            "target": loader["name"],
                                        }
                                    )

                        # Loader → Transformer
                        if group == "loaders":
                            for transformer in config["plugins"].get(
                                "transformers", []
                            ):
                                if "name" in transformer:
                                    edges.append(
                                        {
                                            "source": plugin_name,
                                            "target": transformer["name"],
                                        }
                                    )

    # --- Meltano-style flat plugins (legacy) ---
    if "plugins" in config and isinstance(config["plugins"], list):
        for plugin in config.get("plugins", []):
            if isinstance(plugin, dict) and "type" in plugin and "name" in plugin:
                plugin_type = plugin["type"]
                plugin_name = plugin["name"]
                node_attrs[plugin_name] = {"type": plugin_type}

                if plugin_type == "extractor":
                    for loader in config.get("plugins", []):
                        if loader.get("type") == "loader" and "name" in loader:
                            edges.append(
                                {"source": plugin_name, "target": loader["name"]}
                            )
                if plugin_type == "loader":
                    for transformer in config.get("plugins", []):
                        if (
                            transformer.get("type") == "transformer"
                            and "name" in transformer
                        ):
                            edges.append(
                                {"source": plugin_name, "target": transformer["name"]}
                            )

    # --- Airflow-style ---
    if "tasks" in config:
        for task in config.get("tasks", []):
            if "id" in task:
                node_attrs[task["id"]] = {"type": "task"}
            if "upstream" in task and "id" in task:
                for upstream in task["upstream"]:
                    edges.append({"source": upstream, "target": task["id"]})

    # --- dbt-style ---
    if "models" in config:
        for model in config.get("models", []):
            if "name" in model:
                node_attrs[model["name"]] = {"type": "model"}
            if "depends_on" in model and "name" in model:
                for dep in model["depends_on"]:
                    edges.append({"source": dep, "target": model["name"]})

    return edges, node_attrs
