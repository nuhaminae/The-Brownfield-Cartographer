# src/analysers/tree_sitter_analyser.py
# The Brownfield Cartographer Tree Sitter Analyser

import logging
import os
from pathlib import Path

import tree_sitter_javascript as tsjavascript
import tree_sitter_python as tspython
import tree_sitter_sql as tssql
import tree_sitter_typescript as tsts
import tree_sitter_yaml as tsyaml
from tree_sitter import Language, Parser

from src.models.models import ClassNode, ModuleNode

logging.basicConfig(level=logging.INFO)


class LanguageRouter:
    """
    Routes file extensions to the correct Tree-sitter grammar.
    Only supports Python, JS, TS, SQL, YAML.
    """

    def __init__(self):
        self.languages = {
            ".py": Language(tspython.language()),
            ".js": Language(tsjavascript.language()),
            ".ts": Language(tsts.language_typescript()),
            ".sql": Language(tssql.language()),
            ".yaml": Language(tsyaml.language()),
            ".yml": Language(tsyaml.language()),
        }

    def get_language(self, filename: str):
        ext = os.path.splitext(filename)[1].lower()
        if ext not in self.languages:
            raise ValueError(f"Unsupported file type: {ext}")
        return self.languages[ext]


def analyse_module(file_path: Path) -> ModuleNode:
    """
    Analyse a source file with Tree-sitter.
    Language-aware parsing:
      - Python/JS/TS: imports, functions, classes
      - SQL: table references, query types
      - YAML: keys and values
    """
    try:
        ext = file_path.suffix.lower()
        source_code = file_path.read_bytes()

        router = LanguageRouter()
        language = router.get_language(str(file_path))
        parser = Parser(language)
        tree = parser.parse(source_code)
        root = tree.root_node

        # Initialise all fields
        imports, functions, classes, pairs, tables, queries = [], [], [], [], [], []

        if ext in [".py", ".js", ".ts"]:
            for child in root.children:
                if child.type in (
                    "import_statement",
                    "import_from_statement",
                    "require_call",
                ):
                    imports.append(
                        source_code[child.start_byte : child.end_byte].decode("utf8")
                    )
                if child.type in ("function_definition", "function_declaration"):
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        functions.append(
                            source_code[
                                name_node.start_byte : name_node.end_byte
                            ].decode("utf8")
                        )
                if child.type in ("class_definition", "class_declaration"):
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        classes.append(
                            ClassNode(
                                name=source_code[
                                    name_node.start_byte : name_node.end_byte
                                ].decode("utf8"),
                                bases=[],
                            )
                        )

        elif ext == ".sql":
            for child in root.children:
                if child.type == "table_reference":
                    tables.append(
                        source_code[child.start_byte : child.end_byte].decode("utf8")
                    )
                if child.type in (
                    "select_statement",
                    "insert_statement",
                    "update_statement",
                ):
                    queries.append(child.type.replace("_statement", "").upper())

        elif ext in [".yaml", ".yml"]:
            pairs = []

            SCALAR_TYPES = {
                "string_scalar",
                "plain_scalar",
                "single_quote_scalar",
                "double_quote_scalar",
                "block_scalar",
                "integer_scalar",
                "float_scalar",
                "boolean_scalar",
            }

            def walk(node):
                if node.type == "block_mapping_pair":
                    key_node = node.child_by_field_name("key")
                    val_node = node.child_by_field_name("value")

                    if key_node:
                        k = source_code[key_node.start_byte : key_node.end_byte].decode(
                            "utf8"
                        )

                        if val_node:
                            # If the value node itself is a scalar, capture it
                            if val_node.type in SCALAR_TYPES:
                                v = source_code[
                                    val_node.start_byte : val_node.end_byte
                                ].decode("utf8")
                                pairs.append({"key": k, "value": v})
                            else:
                                # Look inside children: sometimes the scalar is nested
                                scalar_child = next(
                                    (
                                        c
                                        for c in val_node.children
                                        if c.type in SCALAR_TYPES
                                    ),
                                    None,
                                )
                                if scalar_child:
                                    v = source_code[
                                        scalar_child.start_byte : scalar_child.end_byte
                                    ].decode("utf8")
                                    pairs.append({"key": k, "value": v})
                                else:
                                    pairs.append({"key": k, "value": None})
                                    walk(val_node)
                        else:
                            pairs.append({"key": k, "value": None})

                elif node.type == "block_sequence":
                    for item in node.children:
                        walk(item)

                for child in node.children:
                    walk(child)

            walk(root)

        return ModuleNode(
            path=str(file_path),
            imports=imports,
            functions=functions,
            classes=classes,
            pairs=pairs,
            tables=tables,
            queries=queries,
        )

    except Exception as e:
        logging.warning(f"[TreeSitterAnalyser] Failed to analyse {file_path}: {e}")
        return ModuleNode(
            path=str(file_path),
            imports=[],
            functions=[],
            classes=[],
            pairs=[],
            tables=[],
            queries=[],
        )
