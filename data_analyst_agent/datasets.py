from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class LoadedDataset:
    primary: pd.DataFrame
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    source_type: str = "csv"
    source_name: str = ""


def load_dataset_bundle(path: str | Path) -> LoadedDataset:
    dataset_path = Path(path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")
    suffix = dataset_path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(dataset_path)
        return LoadedDataset(primary=df, tables={"data": df}, source_type="csv", source_name=dataset_path.name)
    if suffix in {".xlsx", ".xls"}:
        try:
            sheets = pd.read_excel(dataset_path, sheet_name=None)
        except ImportError as exc:
            raise RuntimeError("读取 Excel 需要安装 openpyxl 或 xlrd。当前环境可继续使用 CSV。") from exc
        if not sheets:
            raise ValueError("Excel 文件没有可读取的工作表。")
        primary_name = max(sheets, key=lambda name: len(sheets[name]))
        return LoadedDataset(primary=sheets[primary_name], tables={str(name): df for name, df in sheets.items()}, source_type="excel", source_name=dataset_path.name)
    raise ValueError(f"Unsupported dataset type: {suffix or 'unknown'}")
