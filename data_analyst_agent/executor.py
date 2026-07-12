from __future__ import annotations

import os
import sqlite3
import time
from collections.abc import Callable
from typing import Any

import pandas as pd

from data_analyst_agent.guardrails import GuardrailPolicy, validate_python_code, validate_tool
from data_analyst_agent.models import AnalysisPlan, AnalysisStep, ToolResult
from data_analyst_agent.sandbox import run_python_in_docker
from data_analyst_agent.sql_safety import validate_readonly_select


class ToolRouter:
    def __init__(
        self,
        policy: GuardrailPolicy | None = None,
        *,
        timeout_seconds: int = 30,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> None:
        self.policy = policy or GuardrailPolicy()
        self.timeout_seconds = timeout_seconds
        self.is_cancelled = is_cancelled

    def run_plan(self, df: pd.DataFrame, plan: AnalysisPlan) -> list[ToolResult]:
        return [self.run_step(df, step) for step in plan.steps]

    def run_step(self, df: pd.DataFrame, step: AnalysisStep) -> ToolResult:
        if self.is_cancelled and self.is_cancelled():
            raise TimeoutError("Analysis job was cancelled before tool execution.")
        validate_tool(step.tool, self.policy)
        started = time.monotonic()
        if step.tool == "python":
            if os.getenv("DATA_ANALYST_AGENT_EXECUTOR_MODE") == "docker":
                validate_python_code(step.code or "")
                output = run_python_in_docker(df, step.code or "", timeout_seconds=self.timeout_seconds)
                safety = docker_safety_evidence(self.timeout_seconds)
            else:
                output = run_guarded_python(df, step.code or "")
                safety = guarded_python_safety_evidence()
        elif step.tool == "sql":
            output = run_sql(df, step.query or "")
            safety = sql_safety_evidence()
        else:
            raise ValueError(f"Unsupported tool: {step.tool}")
        duration = time.monotonic() - started
        if duration > self.timeout_seconds:
            raise TimeoutError(f"Analysis step {step.id} exceeded {self.timeout_seconds} seconds.")
        if self.is_cancelled and self.is_cancelled():
            raise TimeoutError("Analysis job was cancelled after tool execution.")
        return ToolResult(step_id=step.id, title=step.title, output=output, safety=safety)


def guarded_python_safety_evidence() -> dict[str, Any]:
    return {
        "executor": "guarded_python",
        "ast_validated": True,
        "blocked": ["import", "open", "eval", "exec", "dunder access", "file export"],
        "network": "not available in execution scope",
        "timeout_seconds": None,
    }


def docker_safety_evidence(timeout_seconds: int) -> dict[str, Any]:
    return {
        "executor": "docker_sandbox",
        "ast_validated": True,
        "network": "disabled",
        "filesystem": "read-only root filesystem; temporary work volume only",
        "capabilities": "dropped",
        "resources": "1 CPU; 512 MB memory; 128 PIDs",
        "timeout_seconds": timeout_seconds,
    }


def sql_safety_evidence() -> dict[str, Any]:
    return {
        "executor": "sqlite_memory",
        "query_policy": "single read-only SELECT against in-memory data",
        "network": "not used",
        "filesystem": "not used",
    }

def run_guarded_python(df: pd.DataFrame, code: str) -> Any:
    validate_python_code(code)
    scope: dict[str, Any] = {
        "df": df.copy(),
        "pd": pd,
        "len": len,
        "list": list,
        "dict": dict,
        "int": int,
        "float": float,
        "str": str,
        "abs": abs,
        "sorted": sorted,
        "round": round,
        "max": max,
        "min": min,
        "sum": sum,
        "range": range,
    }
    exec(code, {"__builtins__": {}}, scope)
    if "result" not in scope:
        raise ValueError("Python step must assign a variable named 'result'.")
    return normalize_output(scope["result"])


def run_sql(df: pd.DataFrame, query: str) -> list[dict[str, Any]]:
    safe_query = validate_readonly_select(query, required_table="data")

    connection = sqlite3.connect(":memory:")
    try:
        df.to_sql("data", connection, index=False, if_exists="replace")
        cursor = connection.execute(safe_query)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
    finally:
        connection.close()
    return [dict(zip(columns, row)) for row in rows]


def normalize_output(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return value.head(20).to_dict(orient="records")
    if isinstance(value, pd.Series):
        return value.to_dict()
    if isinstance(value, dict):
        return {str(key): normalize_output(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_output(item) for item in value]
    if isinstance(value, tuple):
        return tuple(normalize_output(item) for item in value)
    if hasattr(value, "item"):
        return value.item()
    return value
