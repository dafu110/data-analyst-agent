from __future__ import annotations

from urllib.parse import urlparse

import pandas as pd


BLOCKED_SQL_TERMS = (" insert ", " update ", " delete ", " drop ", " alter ", " attach ", " pragma ", " grant ", " revoke ")


def validate_readonly_query(query: str) -> None:
    query_lower = query.strip().lower()
    if not query_lower.startswith("select"):
        raise ValueError("数据库连接只允许 SELECT 查询。")
    padded = f" {query_lower} "
    if any(term in padded for term in BLOCKED_SQL_TERMS):
        raise ValueError("SQL 包含被禁止的写入或管理操作。")


def validate_database_url(database_url: str, allowed_hosts: set[str]) -> None:
    parsed = urlparse(database_url)
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise ValueError("当前只支持 PostgreSQL 数据库连接。")
    if parsed.hostname not in allowed_hosts:
        raise ValueError(f"数据库主机不在允许列表中：{parsed.hostname}")


def load_database_query(database_url: str, query: str, allowed_hosts: set[str], limit: int = 100_000) -> pd.DataFrame:
    validate_database_url(database_url, allowed_hosts)
    validate_readonly_query(query)
    limited_query = f"select * from ({query.rstrip(';')}) as agent_source limit {int(limit)}"
    try:
        import sqlalchemy
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("数据库连接需要安装 sqlalchemy 和 psycopg：pip install -e .[prod]") from exc
    engine = sqlalchemy.create_engine(database_url)
    return pd.read_sql_query(limited_query, engine)
