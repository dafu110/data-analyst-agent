from __future__ import annotations

import re
from typing import Any

from data_analyst_agent.guardrails import GuardrailError, GuardrailPolicy, validate_python_code, validate_tool
from data_analyst_agent.models import AnalysisPlan, AnalysisStep, DatasetProfile
from data_analyst_agent.sql_safety import validate_readonly_select


class PlanValidationError(ValueError):
    """Raised when a generated analysis plan does not match the tool contract."""


STEP_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}$")


def plan_from_dict(payload: dict[str, Any], profile: DatasetProfile, policy: GuardrailPolicy) -> AnalysisPlan:
    if not isinstance(payload, dict):
        raise PlanValidationError("Plan payload must be a JSON object.")
    user_goal = str(payload.get("user_goal") or "").strip()
    steps_payload = payload.get("steps")
    if not user_goal:
        raise PlanValidationError("Plan must include user_goal.")
    if not isinstance(steps_payload, list) or not steps_payload:
        raise PlanValidationError("Plan must include at least one step.")

    steps = [step_from_dict(item) for item in steps_payload]
    plan = AnalysisPlan(user_goal=user_goal, steps=steps)
    validate_plan(plan, profile, policy)
    return plan


def step_from_dict(payload: dict[str, Any]) -> AnalysisStep:
    if not isinstance(payload, dict):
        raise PlanValidationError("Each step must be a JSON object.")
    return AnalysisStep(
        id=str(payload.get("id") or "").strip(),
        title=str(payload.get("title") or "").strip(),
        tool=str(payload.get("tool") or "").strip(),
        objective=str(payload.get("objective") or "").strip(),
        query=payload.get("query"),
        code=payload.get("code"),
    )


def validate_plan(plan: AnalysisPlan, profile: DatasetProfile, policy: GuardrailPolicy) -> None:
    if not plan.steps:
        raise PlanValidationError("Plan must contain at least one step.")
    seen_ids: set[str] = set()
    for step in plan.steps:
        validate_step(step, profile, policy, seen_ids)


def validate_step(step: AnalysisStep, profile: DatasetProfile, policy: GuardrailPolicy, seen_ids: set[str]) -> None:
    if not STEP_ID_PATTERN.match(step.id):
        raise PlanValidationError(f"Invalid step id: {step.id!r}.")
    if step.id in seen_ids:
        raise PlanValidationError(f"Duplicate step id: {step.id}.")
    seen_ids.add(step.id)

    if not step.title or not step.objective:
        raise PlanValidationError(f"Step {step.id} must include title and objective.")
    validate_tool(step.tool, policy)

    if step.tool == "python":
        if not step.code:
            raise PlanValidationError(f"Python step {step.id} must include code.")
        try:
            validate_python_code(step.code)
        except GuardrailError as exc:
            raise PlanValidationError(str(exc)) from exc
    elif step.tool == "sql":
        if not step.query:
            raise PlanValidationError(f"SQL step {step.id} must include query.")
        validate_sql_query(step.query, profile)


def validate_sql_query(query: str, profile: DatasetProfile) -> None:
    try:
        validate_readonly_select(query, required_table="data")
    except ValueError as exc:
        raise PlanValidationError(str(exc)) from exc


def build_planner_contract(profile: DatasetProfile) -> dict[str, Any]:
    """Return the schema-like contract an LLM planner must satisfy."""
    return {
        "output_format": {
            "user_goal": "string",
            "steps": [
                {
                    "id": "lowercase-kebab-id",
                    "title": "short user-facing title",
                    "tool": "python | sql",
                    "objective": "why this step exists",
                    "code": "required for python; must assign result",
                    "query": "required for sql; SELECT from data only",
                }
            ],
        },
        "available_tools": ["python", "sql"],
        "dataset_table": "data",
        "columns": profile.column_names,
        "numeric_columns": list(profile.numeric_summary),
        "categorical_columns": list(profile.categorical_summary),
        "safety_rules": [
            "Do not write files.",
            "Do not import modules.",
            "Do not access network or OS APIs.",
            "SQL must be SELECT-only and read from data.",
            "Python code must assign the final value to result.",
        ],
    }
