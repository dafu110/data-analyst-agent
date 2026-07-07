from __future__ import annotations

import json
import os
from typing import Protocol

from data_analyst_agent.guardrails import GuardrailPolicy
from data_analyst_agent.models import AnalysisPlan, AnalysisStep, DatasetProfile, SemanticRole
from data_analyst_agent.plan_validator import build_planner_contract, plan_from_dict, validate_plan
from data_analyst_agent.semantics import semantic_map


class Planner:
    """Creates a guarded analysis plan from the profile and user goal."""

    def __init__(self, llm_client: "PlannerLLMClient | None" = None, policy: GuardrailPolicy | None = None) -> None:
        self.llm_client = llm_client
        self.policy = policy or GuardrailPolicy()

    def create_plan(
        self,
        user_goal: str,
        profile: DatasetProfile,
        semantic_roles: list[SemanticRole] | None = None,
    ) -> AnalysisPlan:
        if self.llm_client is not None:
            payload = self.llm_client.create_plan_json(user_goal, build_planner_contract(profile))
            return plan_from_dict(payload, profile, self.policy)

        env_plan = os.getenv("DATA_ANALYST_AGENT_PLAN_JSON")
        if env_plan:
            return plan_from_dict(json.loads(env_plan), profile, self.policy)

        return self.create_rule_based_plan(user_goal, profile, semantic_roles or [])

    def create_rule_based_plan(
        self,
        user_goal: str,
        profile: DatasetProfile,
        semantic_roles: list[SemanticRole] | None = None,
    ) -> AnalysisPlan:
        semantics = semantic_map(semantic_roles or [])
        steps = [
            AnalysisStep(
                id="shape",
                title="数据规模与字段结构",
                tool="python",
                objective="汇总行数、列数和可用字段。",
                code="result = {'rows': len(df), 'columns': len(df.columns), 'column_names': list(df.columns)}",
            ),
            AnalysisStep(
                id="missingness",
                title="数据质量扫描",
                tool="python",
                objective="在分析前检查缺失值和重复行。",
                code="result = {'missing_values': df.isna().sum().to_dict(), 'duplicate_rows': int(df.duplicated().sum())}",
            ),
        ]

        if profile.numeric_summary:
            steps.append(
                AnalysisStep(
                    id="numeric-summary",
                    title="数值字段摘要",
                    tool="python",
                    objective="描述数值字段的集中趋势和离散程度。",
                    code="result = df.select_dtypes(include='number').describe().round(3).to_dict()",
                )
            )

        if profile.categorical_summary:
            first_category = next(iter(profile.categorical_summary))
            steps.append(
                AnalysisStep(
                    id="category-breakdown",
                    title=f"{first_category} 的高频取值",
                    tool="sql",
                    objective="找出代表性分类字段中出现最频繁的取值。",
                    query=f"select {quote_identifier(first_category)}, count(*) as row_count from data group by {quote_identifier(first_category)} order by row_count desc limit 10",
                )
            )

        if "region" in semantics and "revenue" in semantics:
            region = quote_identifier(semantics["region"])
            revenue = quote_identifier(semantics["revenue"])
            steps.append(
                AnalysisStep(
                    id="revenue-by-region",
                    title="区域收入贡献",
                    tool="sql",
                    objective="按区域汇总收入，识别主要贡献区域。",
                    query=f"select {region} as region, round(sum({revenue}), 2) as total_revenue from data group by {region} order by total_revenue desc limit 10",
                )
            )

        if "product" in semantics and "revenue" in semantics:
            product = quote_identifier(semantics["product"])
            revenue = quote_identifier(semantics["revenue"])
            steps.append(
                AnalysisStep(
                    id="revenue-by-product",
                    title="产品收入贡献",
                    tool="sql",
                    objective="按产品汇总收入，识别高贡献产品。",
                    query=f"select {product} as product, round(sum({revenue}), 2) as total_revenue from data group by {product} order by total_revenue desc limit 10",
                )
            )

        if "product" in semantics and "units" in semantics:
            product = quote_identifier(semantics["product"])
            units = quote_identifier(semantics["units"])
            steps.append(
                AnalysisStep(
                    id="units-by-product",
                    title="产品销量贡献",
                    tool="sql",
                    objective="按产品汇总销量，识别主力销售产品。",
                    query=f"select {product} as product, round(sum({units}), 2) as total_units from data group by {product} order by total_units desc limit 10",
                )
            )

        date_column = semantics.get("date") or next(iter(profile.date_columns), None)
        primary_metric = semantics.get("revenue") or semantics.get("profit") or semantics.get("units")
        if date_column and primary_metric:
            date_identifier = quote_identifier(date_column)
            metric_identifier = quote_identifier(primary_metric)
            steps.append(
                AnalysisStep(
                    id="time-trend",
                    title="核心指标时间趋势",
                    tool="python",
                    objective="按时间汇总核心指标，识别趋势变化、峰值和低谷。",
                    code=(
                        f"series_df = pd.DataFrame({{'period': pd.to_datetime(df[{date_column!r}], errors='coerce'), 'value': df[{primary_metric!r}]}}).dropna()\n"
                        "monthly = series_df.groupby(pd.Grouper(key='period', freq='ME'))['value'].sum().reset_index()\n"
                        "if len(monthly) < 2:\n"
                        "    monthly = series_df.groupby(series_df['period'].dt.date)['value'].sum().reset_index(name='value')\n"
                        "monthly['period'] = monthly['period'].astype(str)\n"
                        "result = monthly.tail(12).to_dict(orient='records')"
                    ),
                )
            )

        if "region" in semantics and "product" in semantics and primary_metric:
            region = quote_identifier(semantics["region"])
            product = quote_identifier(semantics["product"])
            metric = quote_identifier(primary_metric)
            steps.append(
                AnalysisStep(
                    id="segment-contribution",
                    title="区域与产品分群贡献",
                    tool="sql",
                    objective="按区域和产品组合汇总核心指标，找到主要贡献分群。",
                    query=f"select {region} as region, {product} as product, round(sum({metric}), 2) as total_metric from data group by {region}, {product} order by total_metric desc limit 12",
                )
            )

        numeric_columns = list(profile.numeric_summary)
        if numeric_columns:
            steps.append(
                AnalysisStep(
                    id="numeric-anomalies",
                    title="数值异常点扫描",
                    tool="python",
                    objective="使用 IQR 方法扫描数值字段异常点数量，辅助识别极端值风险。",
                    code=(
                        "rows = []\n"
                        "for column in df.select_dtypes(include='number').columns:\n"
                        "    series = df[column].dropna()\n"
                        "    if len(series) < 4:\n"
                        "        continue\n"
                        "    q1 = series.quantile(0.25)\n"
                        "    q3 = series.quantile(0.75)\n"
                        "    iqr = q3 - q1\n"
                        "    lower = q1 - 1.5 * iqr\n"
                        "    upper = q3 + 1.5 * iqr\n"
                        "    count = int(((series < lower) | (series > upper)).sum())\n"
                        "    if count:\n"
                        "        rows.append({'column': str(column), 'outliers': count, 'lower': round(float(lower), 4), 'upper': round(float(upper), 4)})\n"
                        "result = rows"
                    ),
                )
            )
        if len(numeric_columns) >= 2:
            steps.append(
                AnalysisStep(
                    id="correlations",
                    title="数值字段相关性",
                    tool="python",
                    objective="识别数值字段之间最强的相关关系。",
                    code=(
                        "corr = df.select_dtypes(include='number').corr(numeric_only=True).round(3)\n"
                        "mask = pd.DataFrame(False, index=corr.index, columns=corr.columns)\n"
                        "for row_index in range(len(corr.columns)):\n"
                        "    for column_index in range(row_index + 1, len(corr.columns)):\n"
                        "        mask.iloc[row_index, column_index] = True\n"
                        "pairs = corr.where(mask).stack().dropna().reset_index()\n"
                        "pairs.columns = ['left', 'right', 'correlation']\n"
                        "pairs['abs_correlation'] = pairs['correlation'].abs()\n"
                        "result = pairs.sort_values('abs_correlation', ascending=False).head(5).drop(columns='abs_correlation').to_dict(orient='records')"
                    ),
                )
            )

        plan = AnalysisPlan(user_goal=user_goal, steps=steps)
        validate_plan(plan, profile, self.policy)
        return plan


class PlannerLLMClient(Protocol):
    def create_plan_json(self, user_goal: str, contract: dict[str, object]) -> dict[str, object]:
        """Return an AnalysisPlan-shaped JSON object that will be validated before use."""


def quote_identifier(identifier: str) -> str:
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'
