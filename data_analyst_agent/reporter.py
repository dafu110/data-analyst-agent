from __future__ import annotations

import json
from typing import Any

from data_analyst_agent.models import AgentResult, ToolResult


class ReportGenerator:
    def generate(self, result: AgentResult) -> str:
        profile = result.profile
        lines = [
            "# 数据分析智能体报告",
            "",
            f"**分析目标：** {result.plan.user_goal}",
            "",
            "## 数据集画像",
            "",
            f"- 来源：`{profile.path}`",
            f"- 规模：{profile.rows} 行 x {profile.columns} 列",
            f"- 字段：{', '.join(profile.column_names)}",
            f"- 数据质量评分：{profile.quality_score:.0%}",
            "",
        ]

        if result.analysis_intent:
            lines.extend(
                [
                    "## 分析意图",
                    "",
                    f"- 类型：{result.analysis_intent.label}",
                    f"- 置信度：{result.analysis_intent.confidence:.0%}",
                    f"- 依据：{result.analysis_intent.reason}",
                    "",
                ]
            )

        if result.executive_summary:
            summary = result.executive_summary
            lines.extend(
                [
                    "## 管理层摘要",
                    "",
                    f"- 结论概览：{summary.headline}",
                    f"- 当前状态：{summary.current_state}",
                    f"- 综合置信度：{summary.confidence:.0%}",
                    "",
                    "### 核心发现",
                    "",
                ]
            )
            lines.extend(f"- {item}" for item in summary.key_takeaways)
            lines.extend(["", "### 主要风险", ""])
            lines.extend(f"- {item}" for item in summary.business_risks)
            lines.extend(["", "### 建议聚焦", ""])
            lines.extend(f"- {item}" for item in summary.recommended_focus)
            lines.append("")

        if result.quality_gates:
            lines.extend(["## 分析质量门禁", ""])
            for gate in result.quality_gates:
                lines.append(f"- **{gate.name}**：{gate.status} / {gate.severity}。{gate.detail}")
            lines.append("")

        if result.execution_review:
            review = result.execution_review
            lines.extend(["## Execution Review", ""])
            lines.append(f"- Status: {review.get('status', 'unknown')}")
            for warning in review.get("warnings", [])[:3]:
                lines.append(f"- Review: {warning}")
            for step in review.get("supplemental_steps", [])[:3]:
                lines.append(f"- Supplemental step: {step.get('title', step.get('step_id', 'unknown'))}")
            lines.append("")

        if result.analysis_context:
            context = result.analysis_context
            lines.extend(
                [
                    "## SaaS 分析配置",
                    "",
                    f"- 业务场景：{context.business_scenario}",
                    f"- 报告受众：{context.report_audience}",
                    f"- 分析深度：{context.analysis_depth}",
                    f"- 交付格式：{context.delivery_format}",
                    "",
                ]
            )

        if result.semantic_roles:
            lines.extend(["## 业务字段识别", ""])
            for role in result.semantic_roles:
                lines.append(f"- {role.role}: `{role.column}`（置信度 {role.confidence:.0%}，{role.reason}）")
            lines.append("")

        if result.table_summaries:
            lines.extend(["## 数据表结构", ""])
            for table in result.table_summaries:
                lines.append(f"- `{table.name}`：{table.rows} 行 x {table.columns} 列；字段：{', '.join(table.column_names[:12])}")
            lines.append("")

        if result.table_relationships:
            lines.extend(["## 多表关系推断", ""])
            for relationship in result.table_relationships:
                lines.append(
                    f"- `{relationship.left_table}.{relationship.left_column}` -> "
                    f"`{relationship.right_table}.{relationship.right_column}`"
                    f"（置信度 {relationship.confidence:.0%}，{relationship.reason}）"
                )
            lines.append("")

        lines.extend(["## 数据质量", ""])
        if profile.quality_dimensions:
            lines.append(
                "- 质量维度："
                + "；".join(f"{key} {value:.0%}" for key, value in profile.quality_dimensions.items())
            )
        if profile.date_columns:
            lines.append(f"- 日期字段：{', '.join(profile.date_columns)}")

        if profile.warnings:
            lines.extend(f"- {warning}" for warning in profile.warnings)
        else:
            lines.append("- 未发现明显重复行、缺失值或常量字段问题。")

        if result.insights:
            lines.extend(["", "## 关键结论", ""])
            grouped = group_insights(result.insights)
            for insight_type, title in [
                ("fact", "事实"),
                ("finding", "发现"),
                ("inference", "推断"),
                ("recommendation", "建议"),
                ("limitation", "边界"),
            ]:
                items = grouped.get(insight_type, [])
                if not items:
                    continue
                lines.extend([f"### {title}", ""])
                for insight in items:
                    lines.append(f"- **{insight.title}：** {insight.detail}")
                    lines.append(f"  - 置信度：{insight.confidence:.0%}")
                    if insight.metric_value:
                        lines.append(f"  - 指标值：{insight.metric_value}")
                    if insight.evidence:
                        lines.append(f"  - 证据：{'；'.join(insight.evidence[:4])}")
                    if insight.source_step_ids:
                        lines.append(f"  - 计算步骤：{', '.join(insight.source_step_ids)}")
                    if insight.recommendation:
                        lines.append(f"  - 建议：{insight.recommendation}")
                    if insight.needs_review:
                        lines.append("  - 局限与复核：该结论需要人工复核后再用于业务决策")
                lines.append("")

        if result.suggested_questions:
            lines.extend(["## 推荐分析问题", ""])
            for question in result.suggested_questions:
                lines.append(f"- {question}")
            lines.append("")

        if result.action_items:
            lines.extend(["## 下一步行动清单", ""])
            for item in result.action_items:
                lines.append(f"- **[{item.priority}] {item.title}：** {item.detail}")
                if item.next_step:
                    lines.append(f"  - 下一步：{item.next_step}")
                lines.append(f"  - 建议负责人：{item.owner_hint}；完成时限：{item.deadline_hint}；预期影响：{item.expected_impact}")
                if item.evidence:
                    lines.append(f"  - 证据：{'；'.join(item.evidence[:4])}")
            lines.append("")

        if result.metric_definitions:
            lines.extend(["## 指标口径", ""])
            for metric in result.metric_definitions:
                status = "可计算" if metric.available else "需补充字段"
                columns = f"；字段：{', '.join(metric.columns)}" if metric.columns else ""
                lines.append(f"- **{metric.name}**（{status}）：`{metric.formula}`{columns}。{metric.reason}")
            lines.append("")

        if result.time_series:
            lines.extend(["## 时间序列摘要", ""])
            for item in result.time_series:
                change = f"{item.percent_change:.1%}" if item.percent_change is not None else "无法计算"
                lines.append(
                    f"- `{item.metric_column}` 基于 `{item.date_column}` 覆盖 {item.periods} 个周期，"
                    f"从 {item.first_period} 到 {item.last_period} 变化 {change}，峰值 {item.peak_period}={item.peak_value}。"
                )

        lines.extend(["", "## 分析发现", ""])
        for tool_result in result.tool_results:
            lines.extend(render_tool_result(tool_result))

        if result.chart_specs:
            lines.extend(["", "## 推荐图表", ""])
            for chart in result.chart_specs:
                lines.append(f"- {chart.title}: {chart.description}")

        lines.extend(
            [
                "",
                "## 下一步建议",
                "",
                "- 结合业务知识复核异常或强相关发现。",
                "- 明确业务问题后，补充更具体的目标指标。",
                "- 将重复使用的分析步骤沉淀为可测试的专用工具。",
            ]
        )

        if result.trace_spans:
            lines.extend(["", "## 执行 Trace", ""])
            for span in result.trace_spans:
                lines.append(f"- {span.label}：{span.status}，{span.duration_ms:.2f} ms，工具 `{span.tool or 'n/a'}`")
        return "\n".join(lines)


def render_tool_result(tool_result: ToolResult) -> list[str]:
    return [
        f"### {tool_result.title}",
        "",
        "```json",
        json.dumps(to_jsonable(tool_result.output), indent=2, ensure_ascii=False),
        "```",
        "",
    ]


def to_jsonable(value: Any) -> Any:
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    return value


def group_insights(insights) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for insight in insights:
        grouped.setdefault(insight.insight_type, []).append(insight)
    return grouped
