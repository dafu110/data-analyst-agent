from __future__ import annotations

import re


BLOCKED_SQL_TERMS = {
    "alter",
    "attach",
    "create",
    "delete",
    "detach",
    "drop",
    "grant",
    "insert",
    "pragma",
    "replace",
    "revoke",
    "truncate",
    "update",
    "vacuum",
}


def validate_readonly_select(query: str, *, required_table: str | None = None) -> str:
    sql = query.strip()
    if not sql:
        raise ValueError("SQL query must not be empty.")
    if any(token in sql for token in ("--", "/*", "*/")):
        raise ValueError("SQL query must not contain comments.")
    if sql.endswith(";"):
        sql = sql[:-1].strip()
    if ";" in sql:
        raise ValueError("SQL query must contain exactly one statement.")

    lowered = sql.lower()
    if not lowered.startswith("select"):
        raise ValueError("SQL query must be SELECT-only.")
    if re.search(r"\b(" + "|".join(sorted(BLOCKED_SQL_TERMS)) + r")\b", lowered):
        raise ValueError("SQL query contains a blocked operation.")
    if required_table and not re.search(rf"\bfrom\s+{re.escape(required_table.lower())}\b", lowered):
        raise ValueError(f"SQL query must read from the in-memory table named {required_table}.")
    return sql
