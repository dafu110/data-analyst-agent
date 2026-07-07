from __future__ import annotations

import pandas as pd

from data_analyst_agent.models import TableRelationship, TableSummary


def summarize_tables(tables: dict[str, pd.DataFrame]) -> list[TableSummary]:
    return [
        TableSummary(
            name=name,
            rows=len(df),
            columns=len(df.columns),
            column_names=[str(column) for column in df.columns],
        )
        for name, df in tables.items()
    ]


def infer_table_relationships(tables: dict[str, pd.DataFrame], max_relationships: int = 12) -> list[TableRelationship]:
    relationships: list[TableRelationship] = []
    items = list(tables.items())
    for left_index, (left_name, left_df) in enumerate(items):
        for right_name, right_df in items[left_index + 1 :]:
            for left_column in left_df.columns:
                for right_column in right_df.columns:
                    score, reason = relationship_score(left_df, str(left_column), right_df, str(right_column))
                    if score >= 0.65:
                        relationships.append(
                            TableRelationship(
                                left_table=left_name,
                                left_column=str(left_column),
                                right_table=right_name,
                                right_column=str(right_column),
                                confidence=round(score, 2),
                                reason=reason,
                            )
                        )
    relationships.sort(key=lambda item: item.confidence, reverse=True)
    return relationships[:max_relationships]


def relationship_score(left_df: pd.DataFrame, left_column: str, right_df: pd.DataFrame, right_column: str) -> tuple[float, str]:
    left_norm = normalize(left_column)
    right_norm = normalize(right_column)
    name_score = 0.0
    if left_norm == right_norm:
        name_score = 0.45
    elif left_norm.endswith("id") and right_norm.endswith("id") and (left_norm in right_norm or right_norm in left_norm):
        name_score = 0.35
    elif left_norm in right_norm or right_norm in left_norm:
        name_score = 0.25

    if name_score == 0:
        return 0.0, "字段名不相似"

    left_values = set(left_df[left_column].dropna().astype(str).head(5000))
    right_values = set(right_df[right_column].dropna().astype(str).head(5000))
    if not left_values or not right_values:
        return name_score, "字段名相似，但有效取值不足"
    overlap = len(left_values.intersection(right_values)) / max(1, min(len(left_values), len(right_values)))
    uniqueness = max(
        left_df[left_column].nunique(dropna=True) / max(len(left_df), 1),
        right_df[right_column].nunique(dropna=True) / max(len(right_df), 1),
    )
    score = min(0.98, name_score + overlap * 0.35 + min(uniqueness, 1.0) * 0.2)
    reason = f"字段名相似，取值重叠 {overlap:.0%}，唯一性 {uniqueness:.0%}"
    return score, reason


def normalize(value: str) -> str:
    return value.strip().lower().replace("_", "").replace("-", "").replace(" ", "")
