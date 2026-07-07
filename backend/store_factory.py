from __future__ import annotations

from backend.config import AppConfig
from backend.job_store import JobStore


def build_job_store(config: AppConfig):
    if config.database_url:
        from backend.postgres_store import PostgresJobStore

        return PostgresJobStore(config.database_url)
    return JobStore(config.database_path)
