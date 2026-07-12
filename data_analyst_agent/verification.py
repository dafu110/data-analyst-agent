from __future__ import annotations

from typing import Any

import pandas as pd

from data_analyst_agent.executor import ToolRouter
from data_analyst_agent.models import AnalysisStep, DatasetProfile, SemanticRole, ToolResult


def verify_execution(
    tool_results: list[ToolResult],
    *,
    profile: DatasetProfile,
    semantic_roles: list[SemanticRole],
    router: ToolRouter,
    df: pd.DataFrame,
) -> tuple[list[ToolResult], dict[str, Any]]:
    """Validate approved-plan output and add one fixed fallback only when needed."""
    usable = [result for result in tool_results if has_usable_output(result.output)]
    empty_steps = [result.step_id for result in tool_results if not has_usable_output(result.output)]
    warnings: list[str] = []
    supplemental: list[dict[str, str]] = []

    if not usable:
        fallback = build_fallback_step(profile, semantic_roles)
        fallback_result = router.run_step(df, fallback)
        tool_results = [*tool_results, fallback_result]
        if has_usable_output(fallback_result.output):
            usable.append(fallback_result)
            supplemental.append(
                {
                    "step_id": fallback.id,
                    "title": fallback.title,
                    "reason": "Approved plan returned no usable tool output; added a fixed profile fallback.",
                }
            )
        else:
            warnings.append("No approved or fallback step produced usable output.")

    if profile.quality_score < 0.85:
        warnings.append("Dataset quality is below the review threshold; business conclusions require confirmation.")
    if not semantic_roles:
        warnings.append("No business semantic role was confirmed; metric-level conclusions are limited.")

    status = "supplemented" if supplemental else "passed" if usable else "review"
    return tool_results, {
        "status": status,
        "approved_steps": len(tool_results) - len(supplemental),
        "usable_steps": len(usable),
        "empty_step_ids": empty_steps,
        "supplemental_steps": supplemental,
        "warnings": warnings,
    }


def has_usable_output(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, bytes, list, tuple, dict, set)):
        return bool(value)
    return True


def build_fallback_step(profile: DatasetProfile, semantic_roles: list[SemanticRole]) -> AnalysisStep:
    roles = {role.role: role.column for role in semantic_roles}
    metric = roles.get("revenue") or roles.get("profit") or roles.get("units")
    if metric:
        code = (
            f"series = pd.to_numeric(df[{metric!r}], errors='coerce').dropna()\n"
            f"result = {{'metric': {metric!r}, 'count': int(series.count()), 'sum': round(float(series.sum()), 4), 'mean': round(float(series.mean()), 4)}}"
        )
        objective = "Return a bounded, verified summary for the confirmed primary metric."
    else:
        code = "result = {'rows': len(df), 'columns': list(df.columns), 'missing_values': df.isna().sum().to_dict()}"
        objective = "Return a bounded dataset profile when no business metric is confirmed."
    return AnalysisStep(
        id="verification-fallback",
        title="Execution verification fallback",
        tool="python",
        objective=objective,
        code=code,
    )
