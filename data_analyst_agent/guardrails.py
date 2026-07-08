from __future__ import annotations

import ast
from dataclasses import dataclass


class GuardrailError(ValueError):
    """Raised when an analysis action violates the agent safety policy."""


@dataclass(frozen=True)
class GuardrailPolicy:
    max_rows: int = 100_000
    max_columns: int = 200
    allowed_tools: tuple[str, ...] = ("python", "sql")


class PythonSafetyVisitor(ast.NodeVisitor):
    blocked_nodes = (
        ast.Import,
        ast.ImportFrom,
        ast.With,
        ast.AsyncWith,
        ast.Try,
        ast.ClassDef,
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.Lambda,
        ast.Global,
        ast.Nonlocal,
        ast.Delete,
    )
    blocked_calls = {
        "__import__",
        "compile",
        "eval",
        "exec",
        "globals",
        "locals",
        "open",
        "print",
        "input",
        "help",
        "dir",
        "vars",
    }
    blocked_attributes = {
        "__class__",
        "__dict__",
        "__globals__",
        "__subclasses__",
        "__mro__",
        "to_csv",
        "to_excel",
        "to_json",
        "to_parquet",
        "to_pickle",
    }

    def visit(self, node: ast.AST) -> None:
        if isinstance(node, self.blocked_nodes):
            raise GuardrailError(f"Python code uses blocked syntax: {type(node).__name__}")
        super().visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in self.blocked_calls:
            raise GuardrailError(f"Python code calls blocked function: {node.func.id}")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in self.blocked_attributes or node.attr.startswith("__"):
            raise GuardrailError(f"Python code accesses blocked attribute: {node.attr}")
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        literal = literal_subscript_key(node.slice)
        if literal in self.blocked_attributes or (literal or "").startswith("__"):
            raise GuardrailError(f"Python code indexes blocked attribute: {literal}")
        self.generic_visit(node)


def validate_dataset_shape(rows: int, columns: int, policy: GuardrailPolicy) -> None:
    if rows > policy.max_rows:
        raise GuardrailError(f"Dataset has {rows} rows; limit is {policy.max_rows}.")
    if columns > policy.max_columns:
        raise GuardrailError(f"Dataset has {columns} columns; limit is {policy.max_columns}.")


def validate_tool(tool: str, policy: GuardrailPolicy) -> None:
    if tool not in policy.allowed_tools:
        raise GuardrailError(f"Tool '{tool}' is not allowed. Allowed tools: {policy.allowed_tools}.")


def validate_python_code(code: str) -> None:
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        raise GuardrailError(f"Invalid Python code: {exc}") from exc
    PythonSafetyVisitor().visit(tree)


def literal_subscript_key(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Index):  # pragma: no cover - compatibility with older Python ASTs
        return literal_subscript_key(node.value)
    return None
