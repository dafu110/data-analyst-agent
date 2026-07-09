from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError, ParserError


CSV_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030")
SNIFFED_DELIMITERS = (";", "\t", "|")


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
        df = read_csv_dataset(dataset_path)
        return LoadedDataset(primary=df, tables={"data": df}, source_type="csv", source_name=dataset_path.name)
    if suffix in {".xlsx", ".xls"}:
        try:
            sheets = pd.read_excel(dataset_path, sheet_name=None)
        except ImportError as exc:
            raise RuntimeError("读取 Excel 需要安装 openpyxl 或 xlrd。当前环境可继续使用 CSV。") from exc
        if not sheets:
            raise ValueError("Excel 文件没有可读取的工作表。")
        primary_name = select_primary_sheet(sheets)
        return LoadedDataset(primary=sheets[primary_name], tables={str(name): df for name, df in sheets.items()}, source_type="excel", source_name=dataset_path.name)
    raise ValueError(f"Unsupported dataset type: {suffix or 'unknown'}")


def read_csv_dataset(path: Path) -> pd.DataFrame:
    last_decode_error: UnicodeDecodeError | None = None
    for encoding in CSV_ENCODINGS:
        try:
            df = pd.read_csv(path, encoding=encoding)
            return sniff_delimiter_if_needed(path, df, encoding)
        except UnicodeDecodeError as exc:
            last_decode_error = exc
        except EmptyDataError as exc:
            raise ValueError("CSV 文件没有可读取的数据。") from exc
        except ParserError as exc:
            raise ValueError(f"CSV 文件格式无法解析：{exc}") from exc
    raise ValueError("CSV 文件编码无法识别，请使用 UTF-8 或 GB18030 编码。") from last_decode_error


def sniff_delimiter_if_needed(path: Path, df: pd.DataFrame, encoding: str) -> pd.DataFrame:
    if len(df.columns) != 1:
        return df
    header = str(df.columns[0])
    if not any(delimiter in header for delimiter in SNIFFED_DELIMITERS):
        return df
    try:
        sniffed = pd.read_csv(path, encoding=encoding, sep=None, engine="python")
    except (EmptyDataError, ParserError, UnicodeDecodeError):
        return df
    return sniffed if len(sniffed.columns) > len(df.columns) else df


def select_primary_sheet(sheets: dict[object, pd.DataFrame]) -> object:
    return max(sheets, key=lambda name: sheet_score(sheets[name]))


def sheet_score(df: pd.DataFrame) -> tuple[int, int, int, int]:
    non_empty = df.dropna(how="all")
    effective_rows = len(non_empty)
    effective_columns = int((df.notna().sum(axis=0) > 0).sum())
    non_empty_cells = int(df.notna().sum().sum())
    return (non_empty_cells, effective_rows, effective_columns, len(df))
