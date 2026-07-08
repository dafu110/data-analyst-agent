from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from data_analyst_agent.agent import DataAnalystAgent


ROOT = Path(__file__).resolve().parents[1]


def load_cases(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    result = DataAnalystAgent().analyze_csv(ROOT / case["dataset"], case["goal"])
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    assertions = case["assertions"]
    failures: list[str] = []

    if len(result.plan.steps) < assertions.get("min_steps", 0):
        failures.append(f"预期至少 {assertions['min_steps']} 个分析步骤。")

    step_ids = {step.id for step in result.plan.steps}
    for step_id in assertions.get("required_step_ids", []):
        if step_id not in step_ids:
            failures.append(f"缺少必需步骤 ID：{step_id}。")

    for term in assertions.get("required_report_terms", []):
        if term not in result.report_markdown:
            failures.append(f"报告缺少关键词：{term}。")

    if len(result.chart_specs) < assertions.get("min_charts", 0):
        failures.append(f"预期至少 {assertions['min_charts']} 个图表规格。")

    if len(result.insights) < assertions.get("min_insights", 0):
        failures.append(f"预期至少 {assertions['min_insights']} 条中文洞察。")

    if len(result.semantic_roles) < assertions.get("min_semantic_roles", 0):
        failures.append(f"预期至少 {assertions['min_semantic_roles']} 个业务语义字段。")

    if result.profile.quality_score < assertions.get("min_quality_score", 0):
        failures.append(f"质量评分低于预期：{result.profile.quality_score:.2f}。")

    if len(result.trace_spans) < assertions.get("min_trace_spans", 0):
        failures.append(f"预期至少 {assertions['min_trace_spans']} 个 trace span。")

    if assertions.get("require_structured_insights"):
        weak = [insight.title for insight in result.insights if not insight.evidence and insight.insight_type != "recommendation"]
        if weak:
            failures.append(f"存在缺少证据的结构化结论：{weak[:3]}。")

    tool_names = {step.tool for step in result.plan.steps}
    disallowed = tool_names.difference(set(case.get("allowed_tools", [])))
    if disallowed:
        failures.append(f"计划使用了不允许的工具：{sorted(disallowed)}。")

    return {
        "id": case["id"],
        "risk_tag": case["risk_tag"],
        "expected_behavior": case.get("expected_behavior", ""),
        "passed": not failures,
        "failures": failures,
        "latency_ms": elapsed_ms,
        "steps": len(result.plan.steps),
        "charts": len(result.chart_specs),
        "insights": len(result.insights),
        "semantic_roles": len(result.semantic_roles),
        "quality_score": result.profile.quality_score,
        "trace_spans": len(result.trace_spans),
    }


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_risk: dict[str, dict[str, Any]] = {}
    for result in results:
        risk_tag = str(result["risk_tag"])
        bucket = by_risk.setdefault(risk_tag, {"total": 0, "passed": 0, "failed": 0})
        bucket["total"] += 1
        if result["passed"]:
            bucket["passed"] += 1
        else:
            bucket["failed"] += 1
    return {
        "total_cases": len(results),
        "passed_cases": sum(1 for result in results if result["passed"]),
        "failed_cases": sum(1 for result in results if not result["passed"]),
        "risk_tags": by_risk,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic Data Analyst Agent evals.")
    parser.add_argument("--cases", default=str(ROOT / "evals" / "cases.json"))
    parser.add_argument("--output", default=str(ROOT / "evals" / "last_results.json"))
    args = parser.parse_args()

    cases = load_cases(Path(args.cases))
    results = [run_case(case) for case in cases]
    payload = {
        "passed": all(result["passed"] for result in results),
        "summary": summarize_results(results),
        "results": results,
    }
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
