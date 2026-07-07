from __future__ import annotations

from data_analyst_agent.models import ChartSpec, DatasetProfile, ToolResult


def build_chart_specs(profile: DatasetProfile, tool_results: list[ToolResult]) -> list[ChartSpec]:
    specs: list[ChartSpec] = []

    missing_data = [
        {"column": column, "missing": count}
        for column, count in profile.missing_values.items()
        if count > 0
    ]
    if missing_data:
        specs.append(
            ChartSpec(
                id="missing-values",
                title="缺失值分布",
                chart_type="bar",
                description="按字段统计缺失值数量，优先定位需要清洗的数据列。",
                data=missing_data,
                x="column",
                y="missing",
            )
        )

    if profile.numeric_summary:
        specs.append(
            ChartSpec(
                id="numeric-means",
                title="数值字段均值",
                chart_type="bar",
                description="展示每个数值字段的平均值，用于快速识别主要指标量级。",
                data=[
                    {"column": column, "mean": summary["mean"]}
                    for column, summary in profile.numeric_summary.items()
                    if "mean" in summary
                ],
                x="column",
                y="mean",
            )
        )
        specs.append(
            ChartSpec(
                id="numeric-ranges",
                title="数值字段范围",
                chart_type="range",
                description="展示数值字段的最小值、均值和最大值，用于发现波动较大的指标。",
                data=[
                    {
                        "column": column,
                        "min": summary.get("min"),
                        "mean": summary.get("mean"),
                        "max": summary.get("max"),
                    }
                    for column, summary in profile.numeric_summary.items()
                    if {"min", "mean", "max"}.issubset(summary)
                ],
                x="column",
                y="mean",
                series="range",
            )
        )

    category_result = find_tool_result(tool_results, "category-breakdown")
    if category_result and isinstance(category_result.output, list) and category_result.output:
        keys = list(category_result.output[0])
        if len(keys) >= 2:
            specs.append(
                ChartSpec(
                    id="category-breakdown",
                    title=category_result.title,
                    chart_type="bar",
                    description="按记录数量展示分类字段的高频取值。",
                    data=category_result.output,
                    x=keys[0],
                    y=keys[1],
                )
            )

    correlation_result = find_tool_result(tool_results, "correlations")
    if correlation_result and isinstance(correlation_result.output, list):
        specs.append(
            ChartSpec(
                id="correlations",
                title="最强数值相关性",
                chart_type="bar",
                description="展示数值字段组合的相关性强度，辅助发现联动关系。",
                data=[
                    {
                        "pair": f"{item.get('left')} / {item.get('right')}",
                        "correlation": item.get("correlation"),
                    }
                    for item in correlation_result.output
                    if isinstance(item, dict)
                ],
                x="pair",
                y="correlation",
            )
        )

    trend_result = find_tool_result(tool_results, "time-trend")
    if trend_result and isinstance(trend_result.output, list) and trend_result.output:
        specs.append(
            ChartSpec(
                id="time-trend",
                title="核心指标时间趋势",
                chart_type="line",
                description="按时间展示核心指标变化，用于发现峰值、低谷和趋势拐点。",
                data=trend_result.output,
                x="period",
                y="value",
            )
        )

    segment_result = find_tool_result(tool_results, "segment-contribution")
    if segment_result and isinstance(segment_result.output, list) and segment_result.output:
        specs.append(
            ChartSpec(
                id="segment-contribution",
                title="区域与产品分群贡献",
                chart_type="bar",
                description="展示区域和产品组合的核心指标贡献。",
                data=[
                    {
                        "segment": f"{item.get('region')} / {item.get('product')}",
                        "total_metric": item.get("total_metric"),
                    }
                    for item in segment_result.output
                    if isinstance(item, dict)
                ],
                x="segment",
                y="total_metric",
            )
        )

    return [spec for spec in specs if spec.data]


def find_tool_result(tool_results: list[ToolResult], step_id: str) -> ToolResult | None:
    return next((result for result in tool_results if result.step_id == step_id), None)
