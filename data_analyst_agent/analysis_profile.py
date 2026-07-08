from __future__ import annotations

from typing import Iterable

import pandas as pd

from data_analyst_agent.models import AnalysisIntent, DatasetProfile, SemanticRole, TimeSeriesSummary
from data_analyst_agent.semantics import semantic_map


INTENT_KEYWORDS = {
    "sales": ("销售分析", ["销售", "收入", "营收", "销量", "订单", "产品", "区域", "revenue", "sales", "units"]),
    "finance": ("财务分析", ["利润", "成本", "毛利", "预算", "费用", "profit", "cost", "margin"]),
    "operations": ("运营分析", ["运营", "渠道", "转化", "活跃", "留存", "漏斗", "channel", "conversion"]),
    "quality": ("数据质量分析", ["质量", "缺失", "重复", "异常", "清洗", "quality", "missing", "duplicate"]),
    "forecast": ("趋势预测准备", ["预测", "趋势", "未来", "forecast", "trend", "同比", "环比"]),
    "general": ("通用探索分析", []),
}


def infer_analysis_intent(goal: str, profile: DatasetProfile, semantic_roles: list[SemanticRole]) -> AnalysisIntent:
    text = " ".join([goal, *profile.column_names, *(role.role for role in semantic_roles)]).lower()
    scores: dict[str, int] = {}
    for intent, (_, keywords) in INTENT_KEYWORDS.items():
        scores[intent] = sum(1 for keyword in keywords if keyword.lower() in text)

    best_intent = max(scores, key=scores.get)
    if scores[best_intent] == 0:
        best_intent = "general"
    label = INTENT_KEYWORDS[best_intent][0]
    confidence = min(0.95, 0.55 + scores[best_intent] * 0.12) if best_intent != "general" else 0.5
    reason = "根据用户目标、字段名和业务语义字段匹配得到。"
    return AnalysisIntent(best_intent, label, round(confidence, 2), reason)


def compute_quality_score(profile: DatasetProfile, duplicate_rows: int = 0) -> tuple[float, dict[str, float]]:
    total_cells = max(profile.rows * profile.columns, 1)
    missing_total = sum(profile.missing_values.values())
    completeness = 1 - missing_total / total_cells
    uniqueness = 1 - duplicate_rows / max(profile.rows, 1)
    constant_columns = sum(1 for warning in profile.warnings if warning.startswith("Constant columns detected"))
    variability = 1 - constant_columns / max(profile.columns, 1)
    schema = 1.0 if profile.columns > 0 and profile.rows > 0 else 0.0
    dimensions = {
        "completeness": round(max(0.0, min(1.0, completeness)), 4),
        "uniqueness": round(max(0.0, min(1.0, uniqueness)), 4),
        "variability": round(max(0.0, min(1.0, variability)), 4),
        "schema": round(schema, 4),
    }
    score = 0.4 * dimensions["completeness"] + 0.25 * dimensions["uniqueness"] + 0.2 * dimensions["variability"] + 0.15 * dimensions["schema"]
    return round(score, 4), dimensions


def detect_date_columns(df: pd.DataFrame) -> list[str]:
    date_columns: list[str] = []
    for column in df.columns:
        series = df[column]
        column_text = str(column).lower()
        name_hint = any(token in column_text for token in ["date", "time", "day", "month", "year", "日期", "时间", "月份", "年度"])
        if pd.api.types.is_datetime64_any_dtype(series):
            date_columns.append(str(column))
            continue
        if not name_hint and not pd.api.types.is_object_dtype(series):
            continue
        parsed = pd.to_datetime(series, errors="coerce")
        if parsed.notna().mean() < 0.7 and "month" in column_text:
            parsed = pd.to_datetime(series.astype(str) + "-01", errors="coerce")
        if parsed.notna().mean() >= 0.7:
            date_columns.append(str(column))
    return date_columns


def build_time_series_summaries(
    df: pd.DataFrame,
    profile: DatasetProfile,
    semantic_roles: list[SemanticRole],
    max_items: int = 2,
) -> list[TimeSeriesSummary]:
    semantics = semantic_map(semantic_roles)
    date_column = semantics.get("date") or next(iter(profile.date_columns), None)
    if not date_column or date_column not in df.columns:
        return []

    metric_candidates = [semantics.get(role) for role in ("revenue", "profit", "units", "cost")]
    metric_candidates.extend(profile.numeric_summary.keys())
    summaries: list[TimeSeriesSummary] = []
    for metric_column in unique_non_empty(metric_candidates):
        if metric_column not in df.columns or metric_column == date_column:
            continue
        if not pd.api.types.is_numeric_dtype(df[metric_column]):
            continue
        prepared = pd.DataFrame(
            {
                "period": pd.to_datetime(df[date_column], errors="coerce"),
                "value": pd.to_numeric(df[metric_column], errors="coerce"),
            }
        ).dropna()
        if prepared.empty:
            continue
        grouped = prepared.groupby(pd.Grouper(key="period", freq="ME"))["value"].sum().sort_index()
        if len(grouped) < 2:
            grouped = prepared.groupby(prepared["period"].dt.date)["value"].sum().sort_index()
        if len(grouped) < 2:
            continue
        first_period = str(grouped.index[0])[:10]
        last_period = str(grouped.index[-1])[:10]
        first_value = float(grouped.iloc[0])
        last_value = float(grouped.iloc[-1])
        absolute_change = last_value - first_value
        percent_change = absolute_change / abs(first_value) if first_value else None
        peak_idx = grouped.idxmax()
        trough_idx = grouped.idxmin()
        summaries.append(
            TimeSeriesSummary(
                date_column=str(date_column),
                metric_column=str(metric_column),
                periods=len(grouped),
                first_period=first_period,
                last_period=last_period,
                first_value=round(first_value, 4),
                last_value=round(last_value, 4),
                absolute_change=round(absolute_change, 4),
                percent_change=round(percent_change, 4) if percent_change is not None else None,
                peak_period=str(peak_idx)[:10],
                peak_value=round(float(grouped.max()), 4),
                trough_period=str(trough_idx)[:10],
                trough_value=round(float(grouped.min()), 4),
            )
        )
        if len(summaries) >= max_items:
            break
    return summaries


def unique_non_empty(values: Iterable[str | None]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
