from __future__ import annotations

from pathlib import Path

import pandas as pd

from data_analyst_agent.datasets import load_dataset_bundle
from data_analyst_agent.guardrails import GuardrailPolicy, validate_dataset_shape
from data_analyst_agent.analysis_profile import compute_quality_score, detect_date_columns
from data_analyst_agent.models import DatasetProfile


def load_dataset(path: str | Path) -> pd.DataFrame:
    return load_dataset_bundle(path).primary


def load_csv(path: str | Path) -> pd.DataFrame:
    return load_dataset(path)


def profile_dataframe(df: pd.DataFrame, path: str | Path, policy: GuardrailPolicy) -> DatasetProfile:
    validate_dataset_shape(len(df), len(df.columns), policy)

    numeric_summary: dict[str, dict[str, float]] = {}
    for column in df.select_dtypes(include="number").columns:
        series = df[column]
        numeric_summary[column] = {
            "mean": round(float(series.mean()), 4),
            "median": round(float(series.median()), 4),
            "min": round(float(series.min()), 4),
            "max": round(float(series.max()), 4),
            "std": round(float(series.std()), 4) if len(series.dropna()) > 1 else 0.0,
        }

    categorical_summary: dict[str, dict[str, int]] = {}
    for column in df.select_dtypes(exclude="number").columns:
        counts = df[column].fillna("<missing>").astype(str).value_counts().head(5)
        categorical_summary[column] = {str(key): int(value) for key, value in counts.items()}

    missing_values = {str(key): int(value) for key, value in df.isna().sum().items()}
    duplicate_rows = int(df.duplicated().sum())
    warnings = build_quality_warnings(df, missing_values, duplicate_rows)
    date_columns = detect_date_columns(df)
    quality_score, quality_dimensions = compute_quality_score(
        DatasetProfile(
            path=Path(path),
            rows=len(df),
            columns=len(df.columns),
            column_names=[str(column) for column in df.columns],
            dtypes={str(key): str(value) for key, value in df.dtypes.items()},
            missing_values=missing_values,
            numeric_summary=numeric_summary,
            categorical_summary=categorical_summary,
            warnings=warnings,
            date_columns=date_columns,
        ),
        duplicate_rows=duplicate_rows,
    )

    return DatasetProfile(
        path=Path(path),
        rows=len(df),
        columns=len(df.columns),
        column_names=[str(column) for column in df.columns],
        dtypes={str(key): str(value) for key, value in df.dtypes.items()},
        missing_values=missing_values,
        numeric_summary=numeric_summary,
        categorical_summary=categorical_summary,
        warnings=warnings,
        quality_score=quality_score,
        quality_dimensions=quality_dimensions,
        date_columns=date_columns,
    )


def build_quality_warnings(df: pd.DataFrame, missing_values: dict[str, int], duplicate_rows: int | None = None) -> list[str]:
    warnings: list[str] = []
    duplicate_rows = int(df.duplicated().sum()) if duplicate_rows is None else duplicate_rows
    if duplicate_rows:
        warnings.append(f"{duplicate_rows} duplicate rows detected.")

    for column, missing_count in missing_values.items():
        if missing_count:
            missing_pct = missing_count / max(len(df), 1)
            warnings.append(f"{column} has {missing_count} missing values ({missing_pct:.1%}).")

    constant_columns = [column for column in df.columns if df[column].nunique(dropna=False) <= 1]
    if constant_columns:
        warnings.append(f"Constant columns detected: {', '.join(map(str, constant_columns))}.")

    return warnings
