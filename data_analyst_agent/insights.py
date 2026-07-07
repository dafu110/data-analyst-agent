from __future__ import annotations

from data_analyst_agent.models import AnalysisIntent, DatasetProfile, Insight, SemanticRole, TimeSeriesSummary, ToolResult
from data_analyst_agent.semantics import semantic_map


def build_insights(
    profile: DatasetProfile,
    tool_results: list[ToolResult],
    semantic_roles: list[SemanticRole] | None = None,
    analysis_intent: AnalysisIntent | None = None,
    time_series: list[TimeSeriesSummary] | None = None,
) -> list[Insight]:
    insights: list[Insight] = []
    semantics = semantic_map(semantic_roles or [])

    if profile.rows == 0:
        return [
            Insight(
                "数据集为空",
                "当前数据集没有可分析的记录，请检查文件内容。",
                "warning",
                insight_type="limitation",
                confidence=0.99,
                evidence=["rows = 0"],
                recommendation="重新上传包含有效记录的数据文件。",
                needs_review=True,
            )
        ]

    if analysis_intent:
        insights.append(
            Insight(
                "分析意图识别",
                f"当前任务更接近「{analysis_intent.label}」，后续结论会优先围绕该业务场景组织。",
                "success",
                insight_type="fact",
                confidence=analysis_intent.confidence,
                evidence=[analysis_intent.reason],
                metric_value=analysis_intent.intent,
                recommendation="如果目标不是这个方向，可以在分析目标中补充更具体的问题。",
            )
        )

    quality_severity = "success" if profile.quality_score >= 0.85 else "warning"
    insights.append(
        Insight(
            "数据质量评分",
            f"综合质量评分为 {profile.quality_score:.0%}，覆盖完整性、唯一性、字段可变性和基础结构可用性。",
            quality_severity,
            insight_type="fact",
            confidence=0.9,
            evidence=[f"{key}={value:.0%}" for key, value in profile.quality_dimensions.items()],
            metric_value=f"{profile.quality_score:.0%}",
            recommendation="评分低于 85% 时，建议先完成缺失值、重复行和常量字段处理。",
            needs_review=profile.quality_score < 0.85,
        )
    )

    missing_columns = [(column, count) for column, count in profile.missing_values.items() if count > 0]
    if missing_columns:
        column, count = max(missing_columns, key=lambda item: item[1])
        ratio = count / max(profile.rows, 1)
        insights.append(
            Insight(
                "存在缺失值风险",
                f"`{column}` 缺失 {count} 条，占比 {ratio:.1%}。建议先确认缺失是否有业务含义，再决定填补或剔除。",
                "warning",
                insight_type="fact",
                confidence=0.95,
                evidence=[f"{column}.missing={count}", f"rows={profile.rows}"],
                metric_value=f"{ratio:.1%}",
                recommendation="对关键指标字段先做缺失原因排查，再选择填补、剔除或单独分组分析。",
                needs_review=True,
            )
        )
    else:
        insights.append(
            Insight(
                "数据完整性较好",
                "未发现明显缺失值，适合继续做描述统计和趋势分析。",
                "success",
                insight_type="fact",
                confidence=0.92,
                evidence=["所有字段 missing_count = 0"],
                metric_value="0 missing values",
            )
        )

    if semantic_roles:
        role_text = "、".join(f"{role.role}={role.column}" for role in semantic_roles[:8])
        insights.append(
            Insight(
                "已识别业务字段",
                f"系统识别到以下业务语义：{role_text}。后续分析会优先围绕这些字段组织结论。",
                "success",
                insight_type="fact",
                confidence=min(role.confidence for role in semantic_roles),
                evidence=[f"{role.role} -> {role.column}: {role.reason}" for role in semantic_roles[:8]],
                recommendation="如果字段含义不符合业务定义，可在数据字典中覆盖自动识别结果。",
            )
        )

    revenue_region = next((result for result in tool_results if result.step_id == "revenue-by-region"), None)
    if revenue_region and isinstance(revenue_region.output, list) and revenue_region.output:
        top = revenue_region.output[0]
        total = sum(float(item.get("total_revenue", 0)) for item in revenue_region.output if isinstance(item, dict))
        share = float(top.get("total_revenue", 0)) / total if total else 0
        insights.append(
            Insight(
                "核心区域贡献",
                f"`{top.get('region')}` 的收入最高，为 {top.get('total_revenue')}，在 Top 区域中占比约 {share:.1%}。建议优先复盘该区域的渠道、产品和价格策略。",
                "success",
                insight_type="finding",
                confidence=0.88,
                evidence=[f"top_region={top.get('region')}", f"top_revenue={top.get('total_revenue')}", f"share={share:.1%}"],
                metric_value=f"{share:.1%}",
                recommendation="优先拆解该区域的产品结构、渠道结构和折扣水平。",
            )
        )

    revenue_product = next((result for result in tool_results if result.step_id == "revenue-by-product"), None)
    if revenue_product and isinstance(revenue_product.output, list) and revenue_product.output:
        top = revenue_product.output[0]
        insights.append(
            Insight(
                "高收入产品",
                f"`{top.get('product')}` 的收入贡献最高，为 {top.get('total_revenue')}。建议进一步查看其毛利、折扣和区域分布。",
                "success",
                insight_type="finding",
                confidence=0.88,
                evidence=[f"top_product={top.get('product')}", f"total_revenue={top.get('total_revenue')}"],
                metric_value=str(top.get("total_revenue")),
                recommendation="把该产品与低收入产品做价格、销量和区域分布对比。",
            )
        )

    units_product = next((result for result in tool_results if result.step_id == "units-by-product"), None)
    if units_product and isinstance(units_product.output, list) and units_product.output:
        top_units = units_product.output[0]
        insights.append(
            Insight(
                "高销量产品",
                f"`{top_units.get('product')}` 的销量最高，为 {top_units.get('total_units')}。如果它与高收入产品不同，说明存在价格或客单价差异。",
                "info",
                insight_type="finding",
                confidence=0.86,
                evidence=[f"top_units_product={top_units.get('product')}", f"total_units={top_units.get('total_units')}"],
                metric_value=str(top_units.get("total_units")),
                recommendation="检查高销量产品是否贡献足够收入和毛利。",
            )
        )

    if profile.numeric_summary:
        spread = []
        for column, summary in profile.numeric_summary.items():
            mean = abs(float(summary.get("mean", 0)))
            std = abs(float(summary.get("std", 0)))
            if mean:
                spread.append((column, std / mean))
        if spread:
            column, ratio = max(spread, key=lambda item: item[1])
            insights.append(
                Insight(
                    "数值波动重点字段",
                    f"`{column}` 的标准差/均值约为 {ratio:.2f}，波动相对更明显，建议优先拆分维度查看来源。",
                    "info",
                    insight_type="finding",
                    confidence=0.78,
                    evidence=[f"{column}.std_to_mean={ratio:.2f}"],
                    metric_value=f"{ratio:.2f}",
                    recommendation="按区域、产品或时间拆分该字段，定位波动来源。",
                    needs_review=ratio > 1.0,
                )
            )

    category_result = next((result for result in tool_results if result.step_id == "category-breakdown"), None)
    if category_result and isinstance(category_result.output, list) and category_result.output:
        first = category_result.output[0]
        keys = list(first)
        if len(keys) >= 2:
            insights.append(
                Insight(
                    "分类字段集中度",
                    f"`{keys[0]}` 中 `{first[keys[0]]}` 出现最多，共 {first[keys[1]]} 条记录。建议检查该类别是否代表主力业务场景。",
                    "info",
                    insight_type="finding",
                    confidence=0.8,
                    evidence=[f"{keys[0]}={first[keys[0]]}", f"{keys[1]}={first[keys[1]]}"],
                    metric_value=str(first[keys[1]]),
                    recommendation="如果该类别过度集中，建议检查样本是否偏向某个业务场景。",
                )
            )

    correlation_result = next((result for result in tool_results if result.step_id == "correlations"), None)
    if correlation_result and isinstance(correlation_result.output, list) and correlation_result.output:
        strongest = correlation_result.output[0]
        if isinstance(strongest, dict):
            value = float(strongest.get("correlation", 0))
            direction = "正相关" if value > 0 else "负相关"
            insights.append(
                Insight(
                    "最强相关关系",
                    f"`{strongest.get('left')}` 与 `{strongest.get('right')}` 的相关系数为 {value:.3f}，表现为{direction}。建议结合业务逻辑判断是否存在因果或分群影响。",
                    "info",
                    insight_type="inference",
                    confidence=0.72,
                    evidence=[f"left={strongest.get('left')}", f"right={strongest.get('right')}", f"correlation={value:.3f}"],
                    metric_value=f"{value:.3f}",
                    recommendation="相关关系不能直接解释为因果，建议进一步做分群或时间顺序验证。",
                    needs_review=True,
                )
            )

    anomaly_result = next((result for result in tool_results if result.step_id == "numeric-anomalies"), None)
    if anomaly_result and isinstance(anomaly_result.output, list) and anomaly_result.output:
        top_anomaly = anomaly_result.output[0]
        insights.append(
            Insight(
                "数值异常点风险",
                f"`{top_anomaly.get('column')}` 检测到 {top_anomaly.get('outliers')} 个 IQR 异常点，可能影响均值、相关性和趋势判断。",
                "warning",
                insight_type="finding",
                confidence=0.82,
                evidence=[
                    f"column={top_anomaly.get('column')}",
                    f"outliers={top_anomaly.get('outliers')}",
                    f"lower={top_anomaly.get('lower')}",
                    f"upper={top_anomaly.get('upper')}",
                ],
                metric_value=str(top_anomaly.get("outliers")),
                recommendation="建议复核异常值是否为真实业务峰值、录入错误或口径差异。",
                needs_review=True,
            )
        )

    for summary in time_series or []:
        direction = "上升" if summary.absolute_change > 0 else "下降"
        change_text = f"{summary.percent_change:.1%}" if summary.percent_change is not None else "无法计算"
        insights.append(
            Insight(
                "时间趋势变化",
                f"`{summary.metric_column}` 从 {summary.first_period} 到 {summary.last_period} 整体{direction}，变化幅度为 {change_text}；峰值出现在 {summary.peak_period}。",
                "success" if summary.absolute_change >= 0 else "warning",
                insight_type="finding",
                confidence=0.82,
                evidence=[
                    f"date_column={summary.date_column}",
                    f"metric_column={summary.metric_column}",
                    f"first={summary.first_value}",
                    f"last={summary.last_value}",
                    f"peak={summary.peak_period}:{summary.peak_value}",
                ],
                metric_value=change_text,
                recommendation="结合活动、渠道、价格或供给变化解释趋势拐点。",
                needs_review=summary.absolute_change < 0,
            )
        )

    if "discount" in semantics and "units" in semantics:
        insights.append(
            Insight(
                "折扣策略需复核",
                f"已识别 `{semantics['discount']}` 和 `{semantics['units']}` 字段，建议重点查看折扣与销量是否同向变化，避免促销没有带来增量。",
                "warning",
                insight_type="recommendation",
                confidence=0.7,
                evidence=[f"discount_field={semantics['discount']}", f"units_field={semantics['units']}"],
                recommendation="补充毛利、活动日期和渠道字段后，验证折扣是否真正拉动销量。",
                needs_review=True,
            )
        )

    limitations = build_limitations(profile, semantics)
    if limitations:
        insights.append(
            Insight(
                "当前分析边界",
                "；".join(limitations),
                "warning",
                insight_type="limitation",
                confidence=0.9,
                evidence=limitations,
                recommendation="补齐缺失字段或上传更长时间跨度的数据后，可生成更可靠的业务判断。",
                needs_review=True,
            )
        )

    insights.append(
        Insight(
            "建议下一步",
            "将关键发现与业务目标对齐后，可以继续做分组对比、时间趋势或异常点分析。",
            "success",
            insight_type="recommendation",
            confidence=0.78,
            evidence=["基于当前数据画像、工具执行结果和业务字段识别生成。"],
            recommendation="优先围绕最高贡献维度和质量风险字段安排下一轮分析。",
        )
    )
    return insights


def build_limitations(profile: DatasetProfile, semantics: dict[str, str]) -> list[str]:
    limitations: list[str] = []
    if profile.rows < 30:
        limitations.append("样本量少于 30 行，趋势和相关性结论需要谨慎解释")
    if "date" not in semantics and not profile.date_columns:
        limitations.append("未识别到日期字段，无法做可靠的同比、环比或趋势判断")
    if "revenue" not in semantics and "profit" not in semantics and "units" not in semantics:
        limitations.append("未识别核心业务指标字段，业务贡献分析会受限")
    return limitations
