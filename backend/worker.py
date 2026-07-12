from __future__ import annotations

import argparse
from pathlib import Path

from backend.config import load_config, require_valid_runtime_config
from backend.service import run_analysis_job
from backend.store_factory import build_job_store
from data_analyst_agent.models import AnalysisPlan, AnalysisStep
from data_analyst_agent.serialization import to_jsonable


CONFIG = load_config()


def enqueue_job(
    job_id: str,
    upload_path: str,
    filename: str,
    goal: str,
    workspace: str,
    data_dictionary: dict[str, str] | None,
    analysis_options: dict[str, str] | None = None,
    approved_plan: dict | None = None,
    preflight_contract: dict | None = None,
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
        serialize_approved_plan(approved_plan),
        preflight_contract,
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
    approved_plan: dict | None = None,
    preflight_contract: dict | None = None,
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
        approved_plan=deserialize_approved_plan(approved_plan),
        preflight_contract=preflight_contract,
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


def serialize_approved_plan(plan: AnalysisPlan | dict | None) -> dict | None:
    """Use JSON-compatible queue arguments instead of pickling application dataclasses."""
    if plan is None:
        return None
    if isinstance(plan, dict):
        return plan
    return to_jsonable(plan)


def deserialize_approved_plan(payload: dict | None) -> AnalysisPlan | None:
    if payload is None:
        return None
    if isinstance(payload, AnalysisPlan):  # Compatibility with jobs enqueued by earlier releases.
        return payload
    if not isinstance(payload, dict):
        raise ValueError("Queued approved plan must be an object.")
    steps = payload.get("steps")
    goal = str(payload.get("user_goal") or "").strip()
    if not goal or not isinstance(steps, list):
        raise ValueError("Queued approved plan is incomplete.")
    return AnalysisPlan(
        user_goal=goal,
        steps=[
            AnalysisStep(
                id=str(step.get("id") or ""),
                title=str(step.get("title") or ""),
                tool=str(step.get("tool") or ""),
                objective=str(step.get("objective") or ""),
                query=step.get("query"),
                code=step.get("code"),
            )
            for step in steps
            if isinstance(step, dict)
        ],
    )


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
