from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


SENSITIVE_COLUMN_TOKENS = (
    "phone",
    "mobile",
    "email",
    "address",
    "password",
    "token",
    "secret",
    "id_card",
    "身份证",
    "手机号",
    "电话",
    "邮箱",
    "地址",
    "密码",
    "密钥",
)
FORMULA_PREFIXES = ("=", "+", "-", "@")


@dataclass(frozen=True)
class InputSafetyFinding:
    kind: str
    severity: str
    detail: str
    columns: list[str]
    count: int = 0


def sensitive_columns(df: pd.DataFrame) -> set[str]:
    return {
        str(column)
        for column in df.columns
        if any(token in str(column).lower() for token in SENSITIVE_COLUMN_TOKENS)
    }


def scan_dataframe(df: pd.DataFrame) -> list[InputSafetyFinding]:
    findings: list[InputSafetyFinding] = []
    if df.empty:
        findings.append(InputSafetyFinding("empty_dataset", "high", "数据表没有可分析的记录。", [], 0))

    sensitive = sensitive_columns(df)
    if sensitive:
        findings.append(
            InputSafetyFinding(
                "sensitive_column",
                "high",
                "检测到可能包含个人或凭据数据的列，预览样例已脱敏。",
                sorted(sensitive),
                len(sensitive),
            )
        )

    formula_columns: set[str] = set()
    formula_count = 0
    for column in df.columns:
        series = df[column]
        if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
            continue
        values = series.dropna().astype(str).str.strip()
        matches = values.str.startswith(FORMULA_PREFIXES)
        count = int(matches.sum())
        if count:
            formula_columns.add(str(column))
            formula_count += count
    if formula_columns:
        findings.append(
            InputSafetyFinding(
                "spreadsheet_formula",
                "high",
                "检测到可能被电子表格软件解释为公式的文本；导出前必须转义。",
                sorted(formula_columns),
                formula_count,
            )
        )
    return findings


def redact_samples(df: pd.DataFrame, sensitive: set[str] | None = None, limit: int = 3) -> dict[str, list[str]]:
    sensitive = sensitive if sensitive is not None else sensitive_columns(df)
    samples: dict[str, list[str]] = {}
    for column in df.columns:
        name = str(column)
        values = df[column].dropna().head(limit).tolist()
        samples[name] = ["[REDACTED]" for _ in values] if name in sensitive else [str(value) for value in values]
    return samples
