from __future__ import annotations

import json
import sys

import pandas as pd


def normalize(value):
    if isinstance(value, pd.DataFrame):
        return value.head(20).to_dict(orient="records")
    if isinstance(value, pd.Series):
        return value.to_dict()
    if isinstance(value, dict):
        return {str(key): normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, tuple):
        return [normalize(item) for item in value]
    if hasattr(value, "item"):
        return value.item()
    return value


def main() -> None:
    input_path, code_path, output_path = sys.argv[1:4]
    df = pd.read_json(input_path)
    code = open(code_path, encoding="utf-8").read()
    scope = {
        "df": df,
        "pd": pd,
        "len": len,
        "list": list,
        "dict": dict,
        "int": int,
        "float": float,
        "str": str,
        "abs": abs,
        "sorted": sorted,
        "round": round,
        "max": max,
        "min": min,
        "sum": sum,
        "range": range,
    }
    exec(code, {"__builtins__": {}}, scope)
    if "result" not in scope:
        raise ValueError("Python step must assign result.")
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(normalize(scope["result"]), handle, ensure_ascii=False)


if __name__ == "__main__":
    main()
