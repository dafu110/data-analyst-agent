from __future__ import annotations

import argparse
from pathlib import Path

from backend.config import load_config, require_valid_runtime_config
from backend.service import run_analysis_job
from backend.store_factory import build_job_store


CONFIG = load_config()


def enqueue_job(
    job_id: str,
    upload_path: str,
    filename: str,
    goal: str,
    workspace: str,
    data_dictionary: dict[str, str] | None,
    analysis_options: dict[str, str] | None = None,
) -> None:
    queue = get_queue()
    queue.enqueue(
        "backend.worker.run_queued_job",
        job_id,
        upload_path,
        filename,
        goal,
        workspace,
        data_dictionary,
        analysis_options,
        job_timeout=CONFIG.job_timeout_seconds + 30,
    )


def run_queued_job(
    job_id: str,
    upload_path: str,
    filename: str,
    goal: str,
    workspace: str,
    data_dictionary: dict[str, str] | None,
    analysis_options: dict[str, str] | None = None,
) -> None:
    store = build_job_store(CONFIG)
    run_analysis_job(
        store,
        None,
        job_id,
        Path(upload_path),
        filename,
        goal,
        CONFIG,
        workspace=workspace,
        data_dictionary=data_dictionary,
        analysis_options=analysis_options,
    )


def get_queue():
    if not CONFIG.redis_url:
        raise RuntimeError("队列模式需要 DATA_ANALYST_AGENT_REDIS_URL。")
    try:
        from redis import Redis
        from rq import Queue
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("队列模式需要安装 redis 和 rq：pip install -e .[prod]") from exc
    return Queue(CONFIG.queue_name, connection=Redis.from_url(CONFIG.redis_url))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Data Analyst Agent RQ worker.")
    parser.add_argument("--queue", default=CONFIG.queue_name)
    args = parser.parse_args()
    require_valid_runtime_config(CONFIG)
    if not CONFIG.redis_url:
        raise RuntimeError("Worker 需要 DATA_ANALYST_AGENT_REDIS_URL。")
    try:
        from redis import Redis
        from rq import Worker
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Worker 需要安装 redis 和 rq：pip install -e .[prod]") from exc
    worker = Worker([args.queue], connection=Redis.from_url(CONFIG.redis_url))
    worker.work()


if __name__ == "__main__":
    main()
