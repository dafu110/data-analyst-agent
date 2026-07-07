from __future__ import annotations

from data_analyst_agent.models import (
    ActionItem,
    AnalysisContext,
    DatasetProfile,
    ExecutiveSummary,
    Insight,
    MetricDefinition,
    QualityGate,
    SemanticRole,
    TimeSeriesSummary,
)
from data_analyst_agent.options import AnalysisOptions
from data_analyst_agent.semantics import semantic_map


SCENARIO_LABELS = {
    "general": "通用经营分析",
    "sales": "销售经营分析",
    "content": "内容运营分析",
    "ecommerce": "电商经营分析",
    "finance": "财务经营分析",
    "customer": "客户运营分析",
    "marketing": "投放与增长分析",
}

AUDIENCE_LABELS = {
    "operator": "运营执行者",
    "manager": "业务负责人",
    "executive": "管理层",
    "client": "客户汇报",
}


def build_analysis_context(
    goal: str,
    business_scenario: str | None = None,
    report_audience: str | None = None,
    analysis_depth: str | None = None,
    delivery_format: str | None = None,
    options: AnalysisOptions | None = None,
) -> AnalysisContext:
    options = options or AnalysisOptions.from_mapping(
        {
            "business_scenario": business_scenario,
            "report_audience": report_audience,
            "analysis_depth": analysis_depth,
            "delivery_format": delivery_format,
        },
        inferred_scenario=infer_scenario(goal),
    )
    return AnalysisContext(
        business_scenario=options.business_scenario,
        report_audience=options.report_audience,
        analysis_depth=options.analysis_depth,
        delivery_format=options.delivery_format,
    )


def build_executive_summary(
    profile: DatasetProfile,
    insights: list[Insight],
    action_items: list[ActionItem],
    quality_gates: list[QualityGate],
    context: AnalysisContext,
) -> ExecutiveSummary:
    scenario_label = SCENARIO_LABELS.get(context.business_scenario, "通用经营分析")
    audience_label = AUDIENCE_LABELS.get(context.report_audience, "运营执行者")
    high_value = [insight for insight in insights if insight.insight_type in {"finding", "inference"}][:3]
    risks = [gate.detail for gate in quality_gates if gate.status != "pass"][:3]
    if not risks:
        risks = ["当前未发现阻断分析的质量风险，但仍建议结合业务口径复核关键结论。"]
    takeaways = [f"{insight.title}：{insight.detail}" for insight in high_value]
    if not takeaways:
        takeaways = [f"已完成 {profile.rows} 行、{profile.columns} 个字段的数据画像和基础分析。"]
    focus = [item.next_step or item.title for item in action_items[:3]]
    confidence = min(0.95, max(0.45, profile.quality_score * 0.7 + (0.2 if insights else 0.0)))
    headline = f"{scenario_label}已生成，适合面向{audience_label}进行复盘和决策。"
    current_state = (
        f"数据规模为 {profile.rows} 行 x {profile.columns} 列，质量评分 {profile.quality_score:.0%}，"
        f"已识别 {len(insights)} 条结构化结论。"
    )
    return ExecutiveSummary(
        headline=headline,
        current_state=current_state,
        key_takeaways=takeaways[:4],
        business_risks=risks,
        recommended_focus=focus[:4],
        confidence=round(confidence, 2),
    )


def build_quality_gates(profile: DatasetProfile, semantic_roles: list[SemanticRole], context: AnalysisContext) -> list[QualityGate]:
    roles = semantic_map(semantic_roles)
    gates = [
        QualityGate(
            name="数据完整性",
            status="pass" if profile.quality_dimensions.get("completeness", profile.quality_score) >= 0.9 else "review",
            detail="缺失值水平可接受。" if profile.quality_dimensions.get("completeness", profile.quality_score) >= 0.9 else "存在较明显缺失值，关键指标解释前需要先复核。",
            severity="high" if profile.quality_dimensions.get("completeness", profile.quality_score) < 0.75 else "medium",
        ),
        QualityGate(
            name="业务口径",
            status="pass" if roles else "review",
            detail="已识别可用于分析的业务字段。" if roles else "尚未识别稳定业务字段，建议补充数据字典。",
            severity="medium",
        ),
        QualityGate(
            name="趋势分析条件",
            status="pass" if ("date" in roles or profile.date_columns) else "review",
            detail="具备日期字段，可进行趋势和周期分析。" if ("date" in roles or profile.date_columns) else "缺少日期字段，无法进行趋势、同比、环比判断。",
            severity="medium",
        ),
    ]
    if context.business_scenario in {"sales", "ecommerce", "finance"}:
        has_metric = any(role in roles for role in ("revenue", "profit", "cost", "units"))
        gates.append(
            QualityGate(
                name="核心经营指标",
                status="pass" if has_metric else "review",
                detail="已识别收入、利润、成本或销量等核心指标。" if has_metric else "缺少收入、利润、成本或销量字段，经营判断会受限。",
                severity="high",
            )
        )
    return gates


def build_suggested_questions(
    profile: DatasetProfile,
    insights: list[Insight],
    semantic_roles: list[SemanticRole],
    time_series: list[TimeSeriesSummary],
) -> list[str]:
    roles = semantic_map(semantic_roles)
    questions = [
        "这份数据最值得关注的 3 个结论是什么？",
        "数据质量有什么风险，是否需要人工复核？",
        "下一步应该优先做哪些业务动作？",
    ]
    if "date" in roles or profile.date_columns or time_series:
        questions.insert(1, "核心指标随时间是增长还是下降？")
    if "region" in roles or "channel" in roles or "product" in roles:
        questions.append("按关键维度拆分后，哪一组表现最好？")
    if "revenue" in roles and "units" in roles:
        questions.append("收入最高和销量最高的对象是否一致？")
    if any(insight.needs_review for insight in insights):
        questions.append("哪些结论需要人工复核，为什么？")
    return _dedupe(questions)[:6]


def build_action_items(profile: DatasetProfile, insights: list[Insight], semantic_roles: list[SemanticRole]) -> list[ActionItem]:
    roles = semantic_map(semantic_roles)
    actions: list[ActionItem] = []

    if profile.quality_score < 0.85 or profile.warnings:
        actions.append(
            ActionItem(
                priority="high",
                title="先修复数据质量风险",
                detail="当前数据存在质量风险，建议先处理缺失值、重复行、常量字段或字段类型问题，再做业务判断。",
                owner_hint="数据负责人",
                evidence=[f"quality_score={profile.quality_score:.0%}", *profile.warnings[:3]],
                next_step="打开数据质量部分，逐字段确认缺失和异常原因。",
            )
        )
    else:
        actions.append(
            ActionItem(
                priority="medium",
                title="保持当前数据质量监控",
                detail="当前质量评分较好，可以继续分析；建议在后续数据更新时持续检查缺失值、重复行和异常值。",
                owner_hint="数据负责人",
                evidence=[f"quality_score={profile.quality_score:.0%}"],
                next_step="将质量检查保存为每次上传后的固定校验。",
            )
        )

    high_value = [insight for insight in insights if insight.insight_type in {"finding", "inference"}][:3]
    for insight in high_value:
        actions.append(
            ActionItem(
                priority="high" if insight.severity in {"warning", "success"} else "medium",
                title=f"复核：{insight.title}",
                detail=insight.detail,
                owner_hint="业务负责人",
                evidence=insight.evidence[:4],
                next_step=insight.recommendation or "围绕该结论继续做分组对比或异常点复核。",
            )
        )

    if "date" not in roles and not profile.date_columns:
        actions.append(
            ActionItem(
                priority="medium",
                title="补充日期字段以支持趋势分析",
                detail="当前没有可靠日期字段，无法做同比、环比、趋势拐点和周期性判断。",
                owner_hint="数据提供方",
                evidence=["未识别到 date 语义字段"],
                next_step="补充发布时间、订单日期、活动日期或统计周期字段。",
            )
        )

    if "revenue" not in roles and "profit" not in roles and "units" not in roles:
        actions.append(
            ActionItem(
                priority="medium",
                title="明确核心业务指标",
                detail="当前没有识别到收入、利润或销量等核心指标，业务贡献分析会受限。",
                owner_hint="业务负责人",
                evidence=["未识别到 revenue/profit/units 语义字段"],
                next_step="在数据字典中标注核心指标字段，或补充业务指标列。",
            )
        )

    return actions[:6]


def build_metric_definitions(profile: DatasetProfile, semantic_roles: list[SemanticRole]) -> list[MetricDefinition]:
    roles = semantic_map(semantic_roles)
    columns = set(profile.column_names)

    definitions = [
        MetricDefinition(
            name="记录数",
            formula="COUNT(*)",
            columns=[],
            available=True,
            reason="所有数据集都可以计算记录数。",
        )
    ]
    definitions.extend(
        [
            metric("总收入", "SUM(revenue)", [roles.get("revenue")], "revenue" in roles),
            metric("总销量", "SUM(units)", [roles.get("units")], "units" in roles),
            metric("平均价格", "SUM(revenue) / SUM(units)", [roles.get("revenue"), roles.get("units")], "revenue" in roles and "units" in roles),
            metric("平均折扣", "AVG(discount)", [roles.get("discount")], "discount" in roles),
            metric("客单价", "SUM(revenue) / COUNT(DISTINCT order)", [roles.get("revenue"), roles.get("order")], "revenue" in roles and "order" in roles),
            metric("时间趋势", "metric GROUP BY date", [roles.get("date") or (profile.date_columns[0] if profile.date_columns else None)], bool(roles.get("date") or profile.date_columns)),
        ]
    )

    for column in profile.numeric_summary:
        if column in columns and all(column not in definition.columns for definition in definitions):
            definitions.append(
                MetricDefinition(
                    name=f"{column} 均值",
                    formula=f"AVG({column})",
                    columns=[column],
                    available=True,
                    reason="数值字段可直接生成均值指标。",
                )
            )
    return definitions[:10]


def metric(name: str, formula: str, raw_columns: list[str | None], available: bool) -> MetricDefinition:
    columns = [column for column in raw_columns if column]
    reason = "字段已识别，可直接计算。" if available else "缺少必要业务字段，需补充数据字典或上传包含该字段的数据。"
    return MetricDefinition(name=name, formula=formula, columns=columns, available=available, reason=reason)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output


def normalize_choice(value: str | None, allowed: dict[str, str], default: str) -> str:
    normalized = (value or "").strip().lower()
    return normalized if normalized in allowed else default


def infer_scenario(goal: str) -> str:
    text = (goal or "").lower()
    if any(keyword in text for keyword in ["销售", "收入", "销量", "sales", "revenue"]):
        return "sales"
    if any(keyword in text for keyword in ["电商", "订单", "商品", "gmv", "ecommerce"]):
        return "ecommerce"
    if any(keyword in text for keyword in ["内容", "小红书", "抖音", "阅读", "点赞", "content"]):
        return "content"
    if any(keyword in text for keyword in ["财务", "利润", "成本", "费用", "finance", "profit", "cost"]):
        return "finance"
    if any(keyword in text for keyword in ["客户", "会员", "留存", "复购", "customer"]):
        return "customer"
    if any(keyword in text for keyword in ["投放", "广告", "转化", "获客", "marketing", "campaign"]):
        return "marketing"
    return "general"
