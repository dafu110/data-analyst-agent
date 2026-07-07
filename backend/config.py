from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class AppConfig:
    env: str
    host: str
    port: int
    max_upload_bytes: int
    max_concurrent_jobs: int
    job_timeout_seconds: int
    api_token: str | None
    admin_actors: set[str]
    storage_dir: Path
    upload_dir: Path
    report_dir: Path
    database_path: Path
    frontend_dir: Path
    llm_provider: str
    llm_model: str
    openai_api_key: str | None
    database_url: str | None
    redis_url: str | None
    queue_name: str
    executor_mode: str
    allowed_database_hosts: set[str]
    rate_limit_per_minute: int
    max_active_jobs_per_actor: int


def load_config() -> AppConfig:
    storage_dir = Path(os.getenv("DATA_ANALYST_AGENT_STORAGE_DIR", ROOT / "storage"))
    max_upload_mb = int(os.getenv("DATA_ANALYST_AGENT_MAX_UPLOAD_MB", "10"))
    return AppConfig(
        env=os.getenv("DATA_ANALYST_AGENT_ENV", "local"),
        host=os.getenv("DATA_ANALYST_AGENT_HOST", "127.0.0.1"),
        port=int(os.getenv("DATA_ANALYST_AGENT_PORT", "8000")),
        max_upload_bytes=max_upload_mb * 1024 * 1024,
        max_concurrent_jobs=int(os.getenv("DATA_ANALYST_AGENT_MAX_CONCURRENT_JOBS", "2")),
        job_timeout_seconds=int(os.getenv("DATA_ANALYST_AGENT_JOB_TIMEOUT_SECONDS", "60")),
        api_token=os.getenv("DATA_ANALYST_AGENT_API_TOKEN") or None,
        admin_actors={
            actor.strip()
            for actor in os.getenv("DATA_ANALYST_AGENT_ADMIN_ACTORS", "admin,local").split(",")
            if actor.strip()
        },
        storage_dir=storage_dir,
        upload_dir=Path(os.getenv("DATA_ANALYST_AGENT_UPLOAD_DIR", ROOT / "backend" / "uploads")),
        report_dir=Path(os.getenv("DATA_ANALYST_AGENT_REPORT_DIR", storage_dir / "reports")),
        database_path=Path(os.getenv("DATA_ANALYST_AGENT_DB", storage_dir / "agent.sqlite3")),
        frontend_dir=Path(os.getenv("DATA_ANALYST_AGENT_FRONTEND_DIR", ROOT / "frontend")),
        llm_provider=os.getenv("DATA_ANALYST_AGENT_LLM_PROVIDER", "rules"),
        llm_model=os.getenv("DATA_ANALYST_AGENT_LLM_MODEL", "none"),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        database_url=os.getenv("DATA_ANALYST_AGENT_DATABASE_URL") or os.getenv("DATABASE_URL") or None,
        redis_url=os.getenv("DATA_ANALYST_AGENT_REDIS_URL") or os.getenv("REDIS_URL") or None,
        queue_name=os.getenv("DATA_ANALYST_AGENT_QUEUE", "analysis"),
        executor_mode=os.getenv("DATA_ANALYST_AGENT_EXECUTOR_MODE", "in_process"),
        allowed_database_hosts={
            host.strip()
            for host in os.getenv("DATA_ANALYST_AGENT_ALLOWED_DB_HOSTS", "localhost,127.0.0.1,postgres").split(",")
            if host.strip()
        },
        rate_limit_per_minute=int(os.getenv("DATA_ANALYST_AGENT_RATE_LIMIT_PER_MINUTE", "60")),
        max_active_jobs_per_actor=int(os.getenv("DATA_ANALYST_AGENT_MAX_ACTIVE_JOBS_PER_ACTOR", "3")),
    )


def validate_runtime_config(config: AppConfig) -> list[str]:
    """Return blocking configuration errors for the selected runtime profile."""
    if config.env.lower() not in {"prod", "production"}:
        return []

    errors: list[str] = []
    if not config.api_token:
        errors.append("生产环境必须设置 DATA_ANALYST_AGENT_API_TOKEN。")
    if config.executor_mode != "docker":
        errors.append("生产环境必须设置 DATA_ANALYST_AGENT_EXECUTOR_MODE=docker。")
    if not config.database_url:
        errors.append("生产环境必须设置 DATA_ANALYST_AGENT_DATABASE_URL 或 DATABASE_URL。")
    if not config.redis_url:
        errors.append("生产环境必须设置 DATA_ANALYST_AGENT_REDIS_URL 或 REDIS_URL。")
    if "local" in config.admin_actors:
        errors.append("生产环境 DATA_ANALYST_AGENT_ADMIN_ACTORS 不能包含 local。")
    return errors


def require_valid_runtime_config(config: AppConfig) -> None:
    errors = validate_runtime_config(config)
    if errors:
        raise RuntimeError("生产配置不完整：" + " ".join(errors))
