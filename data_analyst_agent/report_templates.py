from __future__ import annotations

import json
from typing import Any

from data_analyst_agent.models import AgentResult, ToolResult


class ReportGenerator:
    def generate(self, result: AgentResult) -> str:
        profile = result.profile
        context = result.analysis_context
        depth = context.analysis_depth
        delivery = context.delivery_format
        quick = depth == "quick"
        deep = depth == "deep"
        executive_brief = delivery == "executive_brief"
        client_brief = delivery == "client_brief"
        department_brief = delivery == "department_brief"
        ppt_brief = delivery == "ppt_brief"
        diagnostic = delivery == "diagnostic"
        compact_delivery = executive_brief or client_brief or ppt_brief

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

        if result.executive_summary:
            summary = result.executive_summary
            lines.extend(
                [
                    "## 管理摘要",
                    "",
                    f"- 结论概览：{summary.headline}",
                    f"- 当前状态：{summary.current_state}",
                    f"- 综合置信度：{summary.confidence:.0%}",
                    "",
                    "### 核心发现",
                    "",
                ]
            )
            lines.extend(f"- {item}" for item in limit_items(summary.key_takeaways, quick, executive_brief))
            lines.extend(["", "### 主要风险", ""])
            lines.extend(f"- {item}" for item in limit_items(summary.business_risks, quick, executive_brief))
            lines.extend(["", "### 建议聚焦", ""])
            lines.extend(f"- {item}" for item in limit_items(summary.recommended_focus, quick, executive_brief))
            lines.append("")

        if result.quality_gates:
            lines.extend(["## 分析质量门禁", ""])
            for gate in result.quality_gates:
                lines.append(f"- **{gate.name}**：{gate.status} / {gate.severity}。{gate.detail}")
            lines.append("")

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

        lines.extend(self._delivery_template_sections(result, delivery))

        if result.analysis_intent and not compact_delivery:
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

        if result.semantic_roles and not quick and not compact_delivery:
            lines.extend(["## 业务字段识别", ""])
            for role in result.semantic_roles:
                lines.append(f"- {role.role}: `{role.column}`（置信度 {role.confidence:.0%}，{role.reason}）")
            lines.append("")

        if result.table_summaries and not quick and not compact_delivery:
            lines.extend(["## 数据表结构", ""])
            for table in result.table_summaries:
                fields = ", ".join(table.column_names[:12])
                lines.append(f"- `{table.name}`：{table.rows} 行 x {table.columns} 列；字段：{fields}")
            lines.append("")

        if result.table_relationships and deep and not compact_delivery:
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
            dimensions = "，".join(f"{key} {value:.0%}" for key, value in profile.quality_dimensions.items())
            lines.append(f"- 质量维度：{dimensions}")
        if profile.date_columns:
            lines.append(f"- 日期字段：{', '.join(profile.date_columns)}")
        if profile.warnings:
            lines.extend(f"- {warning}" for warning in profile.warnings)
        else:
            lines.append("- 未发现明显重复行、缺失值或常量字段问题。")
        lines.append("")

        lines.extend(["### 数据质量扫描", ""])
        missing_total = sum(profile.missing_values.values())
        lines.append(f"- missing_values：{missing_total}")
        for column, missing_count in profile.missing_values.items():
            if missing_count:
                lines.append(f"- `{column}` 缺失值：{missing_count}")
        if missing_total == 0:
            lines.append("- missing_values 明细：所有字段缺失值为 0。")
        lines.append("")

        lines.extend(render_safety_evidence(result.tool_results, result.input_security_findings))

        if profile.numeric_summary and not compact_delivery:
            lines.extend(["## 数值字段摘要", ""])
            for column, summary in profile.numeric_summary.items():
                mean = summary.get("mean", 0)
                minimum = summary.get("min", 0)
                maximum = summary.get("max", 0)
                lines.append(f"- `{column}`：均值 {mean:.2f}，最小值 {minimum:.2f}，最大值 {maximum:.2f}")
            lines.append("")

        if diagnostic:
            lines.extend(self._diagnostic_only(result))
        else:
            lines.extend(self._business_sections(result, quick=quick, deep=deep, executive_brief=compact_delivery))

        if result.chart_specs:
            lines.extend(["", "## 推荐图表", ""])
            for chart in result.chart_specs[:3 if quick or compact_delivery else None]:
                lines.append(f"- {chart.title}: {chart.description}")

        if deep and not compact_delivery and not diagnostic:
            lines.extend(["", "## 分析发现原始结果", ""])
            for tool_result in result.tool_results:
                lines.extend(render_tool_result(tool_result))

        if deep and not compact_delivery and result.trace_spans:
            lines.extend(["", "## 执行 Trace", ""])
            for span in result.trace_spans:
                lines.append(f"- {span.label}：{span.status}，{span.duration_ms:.2f} ms，工具 `{span.tool or 'n/a'}`")

        return "\n".join(lines)

    def _delivery_template_sections(self, result: AgentResult, delivery: str) -> list[str]:
        if delivery == "client_brief":
            return [
                "## 客户汇报版结构",
                "",
                "- 开场：先给出可确认的结论，再说明数据范围和口径边界。",
                "- 证据：每个关键结论保留指标值、样本范围和建议复核点。",
                "- 行动：把建议拆成客户可决策、可执行、需补充数据三类。",
                "",
            ]
        if delivery == "department_brief":
            return [
                "## 部门复盘版结构",
                "",
                "- 部门指标：优先呈现与本部门目标相关的趋势、贡献和异常。",
                "- 责任动作：下一步建议按负责人、优先级和依赖条件拆解。",
                "- 协作风险：标注需要其他部门确认的数据口径或业务假设。",
                "",
            ]
        if delivery == "ppt_brief":
            chart_count = len(result.chart_specs or [])
            return [
                "## PPT 模板大纲",
                "",
                "- 第 1 页：结论标题、数据范围、综合置信度。",
                "- 第 2 页：核心发现三点，配套指标证据。",
                f"- 第 3 页：推荐图表（当前可用 {chart_count} 个），优先选择趋势、贡献或异常图。",
                "- 第 4 页：风险与复核点。",
                "- 第 5 页：下一步行动和需要决策的问题。",
                "",
            ]
        if delivery == "executive_brief":
            return [
                "## 老板版摘要结构",
                "",
                "- 先看结论、风险和建议，不展开工具细节。",
                "- 只保留最能支持决策的图表和行动项。",
                "",
            ]
        return []

    def _business_sections(self, result: AgentResult, *, quick: bool, deep: bool, executive_brief: bool) -> list[str]:
        lines: list[str] = []
        if result.insights:
            lines.extend(["## 关键结论", ""])
            grouped = group_insights(result.insights)
            allowed_types = ["finding", "inference", "recommendation", "limitation"] if quick or executive_brief else [
                "fact",
                "finding",
                "inference",
                "recommendation",
                "limitation",
            ]
            for insight_type, title in [
                ("fact", "事实"),
                ("finding", "发现"),
                ("inference", "推断"),
                ("recommendation", "建议"),
                ("limitation", "边界"),
            ]:
                if insight_type not in allowed_types:
                    continue
                items = grouped.get(insight_type, [])
                if not items:
                    continue
                lines.extend([f"### {title}", ""])
                for insight in items[:3 if quick or executive_brief else None]:
                    lines.append(f"- **{insight.title}：** {insight.detail}")
                    lines.append(f"  - 置信度：{insight.confidence:.0%}")
                    if insight.metric_value:
                        lines.append(f"  - 指标值：{insight.metric_value}")
                    if insight.evidence:
                        lines.append(f"  - 证据：{'，'.join(insight.evidence[:4])}")
                    if insight.source_step_ids:
                        lines.append(f"  - 计算步骤：{', '.join(insight.source_step_ids)}")
                    if insight.recommendation:
                        lines.append(f"  - 建议：{insight.recommendation}")
                    if insight.needs_review:
                        lines.append("  - 局限与复核：该结论需要人工复核后再用于业务决策")
                lines.append("")

        if result.action_items:
            lines.extend(["## 下一步行动清单", ""])
            for item in result.action_items[:3 if quick or executive_brief else None]:
                lines.append(f"- **[{item.priority}] {item.title}：** {item.detail}")
                if item.next_step:
                    lines.append(f"  - 下一步：{item.next_step}")
                lines.append(f"  - 建议负责人：{item.owner_hint}；完成时限：{item.deadline_hint}；预期影响：{item.expected_impact}")
                if item.evidence:
                    lines.append(f"  - 证据：{'，'.join(item.evidence[:4])}")
            lines.append("")

        if result.suggested_questions and not executive_brief:
            lines.extend(["## 推荐分析问题", ""])
            for question in result.suggested_questions:
                lines.append(f"- {question}")
            lines.append("")

        if result.metric_definitions and deep:
            lines.extend(["## 指标口径", ""])
            for metric in result.metric_definitions:
                status = "可计算" if metric.available else "需补充字段"
                columns = f"；字段：{', '.join(metric.columns)}" if metric.columns else ""
                lines.append(f"- **{metric.name}**（{status}）：`{metric.formula}`{columns}。{metric.reason}")
            lines.append("")

        if result.time_series and not quick and not executive_brief:
            lines.extend(["## 时间序列摘要", ""])
            for item in result.time_series:
                change = f"{item.percent_change:.1%}" if item.percent_change is not None else "无法计算"
                lines.append(
                    f"- `{item.metric_column}` 基于 `{item.date_column}` 覆盖 {item.periods} 个周期，"
                    f"从 {item.first_period} 到 {item.last_period} 变化 {change}，峰值 {item.peak_period}={item.peak_value}。"
                )
            lines.append("")

        lines.extend(
            [
                "## 下一步建议",
                "",
                "- 结合业务知识复核异常或强相关发现。",
                "- 明确业务问题后，补充更具体的目标指标。",
                "- 将重复使用的分析步骤沉淀为可测试的专用工具。",
            ]
        )
        return lines

    def _diagnostic_only(self, result: AgentResult) -> list[str]:
        lines = ["## 诊断清单", ""]
        if result.quality_gates:
            for gate in result.quality_gates:
                lines.append(f"- [{gate.status}] {gate.name}：{gate.detail}")
        if result.metric_definitions:
            unavailable = [metric for metric in result.metric_definitions if not metric.available]
            if unavailable:
                lines.extend(["", "### 缺失口径", ""])
                for metric in unavailable:
                    lines.append(f"- {metric.name}：{metric.reason}")
        if result.action_items:
            lines.extend(["", "### 修复动作", ""])
            for item in result.action_items:
                lines.append(f"- [{item.priority}] {item.title}：{item.next_step or item.detail}")
                lines.append(f"  - 负责人：{item.owner_hint}；时限：{item.deadline_hint}；预期：{item.expected_impact}")
        return lines


def render_tool_result(tool_result: ToolResult) -> list[str]:
    return [
        f"### {tool_result.title}",
        "",
        "```json",
        json.dumps(to_jsonable(tool_result.output), indent=2, ensure_ascii=False),
        "```",
        "",
    ]


def render_safety_evidence(tool_results: list[ToolResult], input_findings: list[dict[str, Any]] | None = None) -> list[str]:
    entries: list[str] = []
    seen: set[str] = set()
    for tool_result in tool_results:
        safety = tool_result.safety or {}
        executor = str(safety.get("executor") or "unknown")
        if executor in seen:
            continue
        seen.add(executor)
        controls = [
            f"执行器：{executor}",
            f"网络：{safety.get('network', '未声明')}",
            f"文件系统：{safety.get('filesystem', '未声明')}",
        ]
        if safety.get("resources"):
            controls.append(f"资源：{safety['resources']}")
        if safety.get("query_policy"):
            controls.append(f"查询：{safety['query_policy']}")
        entries.append("；".join(controls))
    for finding in input_findings or []:
        if not isinstance(finding, dict):
            continue
        entries.append(f"输入预检：{finding.get('kind', 'risk')}；{finding.get('detail', '需要人工复核')}")
    if not entries:
        return []
    lines = ["## 安全执行证据", ""]
    lines.extend(f"- {entry}" for entry in entries)
    lines.append("")
    return lines


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


def limit_items(items: list[str], quick: bool, executive_brief: bool) -> list[str]:
    return items[:3] if quick or executive_brief else items
