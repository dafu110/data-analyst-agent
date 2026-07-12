from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from datetime import datetime, timezone
from collections.abc import Callable
import time
from typing import Any

from data_analyst_agent.executor import ToolRouter
from data_analyst_agent.guardrails import GuardrailPolicy
from data_analyst_agent.analysis_profile import build_time_series_summaries, infer_analysis_intent
from data_analyst_agent.models import AgentResult, TraceSpan
from data_analyst_agent.options import AnalysisOptions
from data_analyst_agent.planner import Planner
from data_analyst_agent.plan_validator import validate_plan
from data_analyst_agent.llm_provider import build_planner_client_from_env
from data_analyst_agent.datasets import load_dataset_bundle
from data_analyst_agent.profiler import profile_dataframe
from data_analyst_agent.relationships import infer_table_relationships, summarize_tables
from data_analyst_agent.report_templates import ReportGenerator
from data_analyst_agent.charting import build_chart_specs
from data_analyst_agent.insights import build_insights
from data_analyst_agent.semantics import infer_semantic_roles
from data_analyst_agent.business import (
    build_action_items,
    build_analysis_context,
    build_executive_summary,
    build_metric_definitions,
    build_quality_gates,
    build_suggested_questions,
)
from data_analyst_agent.verification import verify_execution


class DataAnalystAgent:
    def __init__(
        self,
        planner: Planner | None = None,
        router: ToolRouter | None = None,
        reporter: ReportGenerator | None = None,
        policy: GuardrailPolicy | None = None,
    ) -> None:
        self.policy = policy or GuardrailPolicy()
        self.planner = planner or Planner(llm_client=build_planner_client_from_env())
        self.router = router or ToolRouter(self.policy)
        self.reporter = reporter or ReportGenerator()

    def analyze_csv(
        self,
        dataset_path: str | Path,
        goal: str,
        source_name: str | Path | None = None,
        data_dictionary: dict[str, str] | None = None,
        input_security_findings: list[dict[str, Any]] | None = None,
        business_scenario: str | None = None,
        report_audience: str | None = None,
        analysis_depth: str | None = None,
        delivery_format: str | None = None,
        analysis_options: AnalysisOptions | dict[str, str] | None = None,
        approved_plan=None,
        is_cancelled: Callable[[], bool] | None = None,
        tool_timeout_seconds: int = 30,
    ) -> AgentResult:
        trace_spans: list[TraceSpan] = []
        check_cancelled(is_cancelled)
        options = self._resolve_options(
            analysis_options=analysis_options,
            business_scenario=business_scenario,
            report_audience=report_audience,
            analysis_depth=analysis_depth,
            delivery_format=delivery_format,
        )
        analysis_context = build_analysis_context(goal, options=options)
        started = time.monotonic()
        dataset = load_dataset_bundle(dataset_path)
        df = dataset.primary
        trace_spans.append(build_span("load", "读取数据集", "completed", started, "python"))
        check_cancelled(is_cancelled)
        started = time.monotonic()
        table_summaries = summarize_tables(dataset.tables)
        table_relationships = infer_table_relationships(dataset.tables) if len(dataset.tables) > 1 else []
        trace_spans.append(build_span("relationships", "识别多表结构和关系", "completed", started, "rules"))
        check_cancelled(is_cancelled)
        started = time.monotonic()
        profile = profile_dataframe(df, source_name or dataset_path, self.policy)
        trace_spans.append(build_span("profile", "生成数据画像", "completed", started, "python"))
        check_cancelled(is_cancelled)
        started = time.monotonic()
        semantic_roles = infer_semantic_roles(profile, data_dictionary=data_dictionary)
        analysis_intent = infer_analysis_intent(goal, profile, semantic_roles)
        time_series = build_time_series_summaries(df, profile, semantic_roles)
        trace_spans.append(build_span("business-context", "识别业务语义和分析意图", "completed", started, "rules"))
        check_cancelled(is_cancelled)
        started = time.monotonic()
        if approved_plan is not None:
            if approved_plan.user_goal.strip() != goal.strip():
                raise ValueError("Approved plan goal does not match the analysis request.")
            validate_plan(approved_plan, profile, self.policy)
            plan = approved_plan
        else:
            plan = self.planner.create_plan(goal, profile, semantic_roles=semantic_roles)
        trace_spans.append(build_span("plan", "生成分析计划", "completed", started, "planner"))
        check_cancelled(is_cancelled)
        started = time.monotonic()
        router = self.router
        if is_cancelled is not None or getattr(router, "timeout_seconds", None) != tool_timeout_seconds:
            router = ToolRouter(self.policy, timeout_seconds=tool_timeout_seconds, is_cancelled=is_cancelled)
        tool_results = router.run_plan(df, plan)
        trace_spans.append(build_span("tools", "执行分析工具", "completed", started, "router"))
        check_cancelled(is_cancelled)
        started = time.monotonic()
        tool_results, execution_review = verify_execution(
            tool_results,
            profile=profile,
            semantic_roles=semantic_roles,
            router=router,
            df=df,
        )
        trace_spans.append(
            build_span(
                "execution-review",
                "验证执行结果",
                execution_review["status"],
                started,
                "verifier",
                "; ".join(execution_review["warnings"][:2]) or None,
            )
        )
        check_cancelled(is_cancelled)
        started = time.monotonic()
        report_inputs = build_report_inputs(profile, tool_results, semantic_roles, analysis_intent, time_series, analysis_context)
        chart_specs = report_inputs["chart_specs"]
        insights = report_inputs["insights"]
        suggested_questions = report_inputs["suggested_questions"]
        action_items = report_inputs["action_items"]
        metric_definitions = report_inputs["metric_definitions"]
        quality_gates = report_inputs["quality_gates"]
        executive_summary = report_inputs["executive_summary"]
        trace_spans.append(build_span("report-context", "生成图表和专业结论", "completed", started, "rules"))
        check_cancelled(is_cancelled)
        partial_result = self._build_result(
            profile=profile,
            plan=plan,
            tool_results=tool_results,
            report_markdown="",
            chart_specs=chart_specs,
            insights=insights,
            semantic_roles=semantic_roles,
            analysis_intent=analysis_intent,
            time_series=time_series,
            trace_spans=trace_spans,
            table_summaries=table_summaries,
            table_relationships=table_relationships,
            suggested_questions=suggested_questions,
            action_items=action_items,
            metric_definitions=metric_definitions,
            analysis_context=analysis_context,
            executive_summary=executive_summary,
            quality_gates=quality_gates,
            execution_review=execution_review,
            input_security_findings=input_security_findings or [],
        )
        report_markdown = self.reporter.generate(partial_result)
        check_cancelled(is_cancelled)
        return self._build_result(
            profile=profile,
            plan=plan,
            tool_results=tool_results,
            report_markdown=report_markdown,
            chart_specs=chart_specs,
            insights=insights,
            semantic_roles=semantic_roles,
            analysis_intent=analysis_intent,
            time_series=time_series,
            trace_spans=trace_spans,
            table_summaries=table_summaries,
            table_relationships=table_relationships,
            suggested_questions=suggested_questions,
            action_items=action_items,
            metric_definitions=metric_definitions,
            analysis_context=analysis_context,
            executive_summary=executive_summary,
            quality_gates=quality_gates,
            execution_review=execution_review,
            input_security_findings=input_security_findings or [],
        )

    def _resolve_options(
        self,
        *,
        analysis_options: AnalysisOptions | dict[str, str] | None,
        business_scenario: str | None,
        report_audience: str | None,
        analysis_depth: str | None,
        delivery_format: str | None,
    ) -> AnalysisOptions:
        if isinstance(analysis_options, AnalysisOptions):
            return analysis_options
        option_values = {
            "business_scenario": business_scenario,
            "report_audience": report_audience,
            "analysis_depth": analysis_depth,
            "delivery_format": delivery_format,
        }
        if analysis_options:
            option_values.update(analysis_options)
        return AnalysisOptions.from_mapping(option_values)

    def _build_result(self, **values) -> AgentResult:
        return AgentResult(**values)


def build_span(step_id: str, label: str, status: str, started: float, tool: str | None = None, detail: str | None = None) -> TraceSpan:
    duration_ms = round((time.monotonic() - started) * 1000, 2)
    now = datetime.now(timezone.utc).isoformat()
    return TraceSpan(
        step_id=step_id,
        label=label,
        status=status,
        started_at=now,
        ended_at=now,
        duration_ms=duration_ms,
        tool=tool,
        detail=detail,
    )


def build_report_inputs(profile, tool_results, semantic_roles, analysis_intent, time_series, analysis_context) -> dict[str, Any]:
    chart_specs = build_chart_specs(profile, tool_results)
    insights = link_evidence_to_insights(build_insights(profile, tool_results, semantic_roles, analysis_intent, time_series))
    suggested_questions = build_suggested_questions(profile, insights, semantic_roles, time_series)
    action_items = link_evidence_to_actions(build_action_items(profile, insights, semantic_roles))
    metric_definitions = build_metric_definitions(profile, semantic_roles)
    quality_gates = build_quality_gates(profile, semantic_roles, analysis_context)
    executive_summary = build_executive_summary(profile, insights, action_items, quality_gates, analysis_context)
    return {
        "chart_specs": chart_specs,
        "insights": insights,
        "suggested_questions": suggested_questions,
        "action_items": action_items,
        "metric_definitions": metric_definitions,
        "quality_gates": quality_gates,
        "executive_summary": executive_summary,
    }


def link_evidence_to_insights(insights):
    return [replace(insight, source_step_ids=infer_source_steps(insight.evidence)) for insight in insights]


def link_evidence_to_actions(actions):
    return [replace(action, source_step_ids=infer_source_steps(action.evidence)) for action in actions]


def infer_source_steps(evidence: list[str]) -> list[str]:
    text = " ".join(str(item) for item in evidence)
    source_steps = ["profile"]
    evidence_sources = {
        "top_region=": "revenue-by-region",
        "top_product=": "revenue-by-product",
        "top_units_product=": "units-by-product",
        "std_to_mean=": "numeric-summary",
        "correlation=": "correlations",
        "outliers=": "numeric-anomalies",
        "date_column=": "time-trend",
        "discount_field=": "business-context",
        "revenue/profit/units": "business-context",
        "date ": "business-context",
    }
    for marker, step_id in evidence_sources.items():
        if marker in text and step_id not in source_steps:
            source_steps.append(step_id)
    return source_steps


def check_cancelled(is_cancelled: Callable[[], bool] | None) -> None:
    if is_cancelled and is_cancelled():
        raise TimeoutError("Analysis job was cancelled.")
