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

from src.models.models import ClassNode, ModuleNode, YamlPair

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


def compute_metrics(source_text: str, ext: str) -> dict:
    """
    Compute metrics for a given source file.

    Metrics computed are:
    - LOC (lines of code)
    - comment ratio (number of comment lines / total lines)
    - cyclomatic complexity (a measure of code complexity)

    The complexity metric is language-aware:
    - For Python, it is computed using the radon library.
    - For JS/TS, it is a simple heuristic counting the number of branching keywords.

    If an exception occurs while computing complexity, it defaults to 0.0.

    :param source_text: The source code to compute metrics for
    :param ext: The file extension of the source code
    :return: A dictionary containing the computed metrics
    """
    lines = source_text.splitlines()
    loc = len(lines)
    comment_lines = sum(1 for l in lines if l.strip().startswith(("#", "//", "/*")))
    comment_ratio = comment_lines / loc if loc > 0 else 0.0

    complexity = 0
    try:
        if ext == ".py":
            from radon.complexity import cc_visit

            blocks = cc_visit(source_text)
            complexity = sum(b.complexity for b in blocks) / max(1, len(blocks))
        elif ext in [".js", ".ts"]:
            # Simple heuristic: count branching keywords
            keywords = ["if", "for", "while", "case", "catch"]
            complexity = sum(source_text.count(k) for k in keywords)
    except Exception:
        complexity = 0

    return {
        "loc": loc,
        "comment_ratio": comment_ratio,
        "cyclomatic_complexity": complexity,
    }


def analyse_module(file_path: Path) -> ModuleNode:
    """
    Analyse a source file with Tree-sitter.
    Language-aware parsing:
      - Python/JS/TS: imports, functions, classes
      - SQL: table references, query types
      - YAML: keys and values
    """
    source_text = file_path.read_text(encoding="utf-8")
    metrics = compute_metrics(source_text, file_path.suffix.lower())
    attrs = {"code": source_text, "metrics": metrics}

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

        # --- python ---
        if ext == ".py":
            for child in root.children:
                # Imports
                if child.type in ("import_statement", "import_from_statement"):
                    imports.append(
                        source_code[child.start_byte : child.end_byte].decode("utf8")
                    )

                # Functions
                if child.type == "function_definition":
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        fn_name = source_code[
                            name_node.start_byte : name_node.end_byte
                        ].decode("utf8")
                        if not fn_name.startswith("_"):  # filter private
                            functions.append(fn_name)

                # Classes with bases
                if child.type == "class_definition":
                    name_node = child.child_by_field_name("name")
                    base_node = child.child_by_field_name("superclasses")
                    bases = []
                    if base_node:
                        for base in base_node.children:
                            if base.type == "identifier":
                                bases.append(
                                    source_code[base.start_byte : base.end_byte].decode(
                                        "utf8"
                                    )
                                )
                    if name_node:
                        classes.append(
                            ClassNode(
                                name=source_code[
                                    name_node.start_byte : name_node.end_byte
                                ].decode("utf8"),
                                bases=bases,
                            )
                        )

        # --- JavaScript/TypeScript ---
        elif ext in [".js", ".ts"]:
            for child in root.children:
                # Imports
                if child.type == "require_call":
                    imports.append(
                        source_code[child.start_byte : child.end_byte].decode("utf8")
                    )

                # Functions
                if child.type == "function_declaration":
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        fn_name = source_code[
                            name_node.start_byte : name_node.end_byte
                        ].decode("utf8")
                        if not fn_name.startswith("_"):
                            functions.append(fn_name)

                # Classes with bases
                if child.type == "class_declaration":
                    name_node = child.child_by_field_name("name")
                    base_node = child.child_by_field_name("superclass")
                    bases = []
                    if base_node:
                        bases.append(
                            source_code[
                                base_node.start_byte : base_node.end_byte
                            ].decode("utf8")
                        )
                    if name_node:
                        classes.append(
                            ClassNode(
                                name=source_code[
                                    name_node.start_byte : name_node.end_byte
                                ].decode("utf8"),
                                bases=bases,
                            )
                        )

        # --- SQL ---
        elif ext == ".sql":
            for child in root.children:
                if child.type in (
                    "select_statement",
                    "insert_statement",
                    "update_statement",
                    "delete_statement",
                ):
                    queries.append(child.type.replace("_statement", "").upper())
                    # Walk children to find tables referenced inside the query
                    for grandchild in child.children:
                        if grandchild.type == "table_reference":
                            tables.append(
                                source_code[
                                    grandchild.start_byte : grandchild.end_byte
                                ].decode("utf8")
                            )
                elif child.type == "table_reference":
                    # Capture standalone table references
                    tables.append(
                        source_code[child.start_byte : child.end_byte].decode("utf8")
                    )

        # --- YAML ---
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
                            if val_node.type in SCALAR_TYPES:
                                v = source_code[
                                    val_node.start_byte : val_node.end_byte
                                ].decode("utf8")
                                pairs.append(YamlPair(key=k, value=v, kind="scalar"))
                            else:
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
                                    pairs.append(
                                        YamlPair(key=k, value=v, kind="scalar")
                                    )
                                else:
                                    pairs.append(
                                        YamlPair(key=k, value=None, kind="mapping")
                                    )
                                    walk(val_node)
                        else:
                            pairs.append(YamlPair(key=k, value=None, kind="mapping"))

                elif node.type == "block_sequence":
                    for item in node.children:
                        if item.type in SCALAR_TYPES:
                            v = source_code[item.start_byte : item.end_byte].decode(
                                "utf8"
                            )
                            pairs.append(YamlPair(key=None, value=v, kind="scalar"))
                        else:
                            pairs.append(YamlPair(key=None, value=None, kind="mapping"))
                            walk(item)

                else:
                    # Recurse into children to reach nested mappings/sequences
                    for child in node.children:
                        walk(child)

            # Call the walker on the root
            walk(root)

        return ModuleNode(
            path=str(file_path),
            imports=imports,
            functions=functions,
            classes=classes,
            pairs=pairs,
            tables=tables,
            queries=queries,
            attrs=attrs,
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
            attrs={},
        )
