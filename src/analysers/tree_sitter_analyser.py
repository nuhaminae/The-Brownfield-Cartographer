# src/analysers/tree_sitter_analyser.py
import ast
import re
from pathlib import Path

import sqlglot
import yaml

from src.models.models import ClassNode, ModuleNode


def analyse_python_ast(file_path: Path) -> ModuleNode:
    """Analyse Python files using built-in ast."""
    code = file_path.read_text(encoding="utf-8")
    tree = ast.parse(code)

    imports, functions, classes = [], [], []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.FunctionDef):
            functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
            classes.append(ClassNode(name=node.name, bases=bases))

    return ModuleNode(
        path=str(file_path), imports=imports, functions=functions, classes=classes
    )


def analyse_sql(file_path: Path) -> ModuleNode:
    """Analyse SQL files using sqlglot."""
    code = file_path.read_text(encoding="utf-8")
    imports, functions, classes = [], [], []

    try:
        expressions = sqlglot.parse(code)
        for expr in expressions:
            for table in expr.find_all(sqlglot.exp.Table):
                imports.append(table.name)
            for func in expr.find_all(sqlglot.exp.Func):
                functions.append(func.name)
    except Exception:
        pass

    return ModuleNode(
        path=str(file_path), imports=imports, functions=functions, classes=classes
    )


def analyse_yaml(file_path: Path) -> ModuleNode:
    """Analyse YAML files using PyYAML."""
    code = file_path.read_text(encoding="utf-8")
    imports, functions, classes = [], [], []

    try:
        data = yaml.safe_load(code)
        if isinstance(data, dict):
            imports.extend(data.keys())
    except Exception:
        pass

    return ModuleNode(
        path=str(file_path), imports=imports, functions=functions, classes=classes
    )


def analyse_js_ts(file_path: Path) -> ModuleNode:
    """Analyse JS/TS files using regex for imports and functions."""
    code = file_path.read_text(encoding="utf-8")
    imports, functions, classes = [], [], []

    # Match ES6 imports
    imports.extend(re.findall(r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]', code))
    # Match CommonJS requires
    imports.extend(re.findall(r'require\([\'"]([^\'"]+)[\'"]\)', code))

    # Match function definitions
    functions.extend(re.findall(r"function\s+([a-zA-Z0-9_]+)\s*\(", code))
    functions.extend(re.findall(r"([a-zA-Z0-9_]+)\s*=\s*\([^)]*\)\s*=>", code))

    # Match class definitions
    for cls in re.findall(r"class\s+([a-zA-Z0-9_]+)", code):
        classes.append(ClassNode(name=cls, bases=[]))

    return ModuleNode(
        path=str(file_path), imports=imports, functions=functions, classes=classes
    )


def analyse_module(file_path: Path) -> ModuleNode:
    """Dispatch analyser based on file extension."""
    if file_path.suffix == ".py":
        return analyse_python_ast(file_path)
    elif file_path.suffix == ".sql":
        return analyse_sql(file_path)
    elif file_path.suffix in (".yaml", ".yml"):
        return analyse_yaml(file_path)
    elif file_path.suffix in (".js", ".ts"):
        return analyse_js_ts(file_path)
    else:
        raise NotImplementedError(f"No analyser for {file_path.suffix}")
