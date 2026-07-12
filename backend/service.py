from __future__ import annotations

import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from backend.audit import AuditContext, audit
from backend.config import AppConfig
from backend.job_store import JobStore, job_to_dict
from data_analyst_agent.agent import DataAnalystAgent
from data_analyst_agent.models import AnalysisPlan
from data_analyst_agent.options import AnalysisOptions, parse_analysis_options
from data_analyst_agent.serialization import agent_result_to_dict


def save_upload(filename: str, content: bytes, config: AppConfig) -> Path:
    config.upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix or ".csv"
    with tempfile.NamedTemporaryFile(delete=False, dir=config.upload_dir, suffix=suffix) as handle:
        handle.write(content)
        return Path(handle.name)


def is_supported_dataset(filename: str) -> bool:
    return Path(filename).suffix.lower() in {".csv", ".xlsx", ".xls"}


def create_analysis_job(
    *,
    store: JobStore,
    config: AppConfig,
    semaphore: threading.BoundedSemaphore | None,
    filename: str,
    dataset_bytes: bytes,
    goal: str,
    owner: str,
    organization: str,
    workspace: str,
    data_dictionary: dict[str, str] | None,
    analysis_options: AnalysisOptions | dict[str, str] | None,
    context: AuditContext,
    approved_plan: AnalysisPlan | None = None,
    preflight_contract: dict[str, Any] | None = None,
    enqueue: bool = False,
) -> dict[str, Any]:
    upload_path = save_upload(filename, dataset_bytes, config)
    job = store.create(filename, goal, owner=owner, organization=organization, workspace=workspace)
    options = normalize_analysis_options(analysis_options)
    audit(
        store,
        context,
        "job.create",
        job.id,
        {
            "filename": filename,
            "bytes": len(dataset_bytes),
            "owner": owner,
            "organization": organization,
            "workspace": workspace,
            "queued": enqueue,
            "analysis_options": options.to_dict(),
            "preflight_contract": preflight_contract or {},
        },
    )
    if enqueue:
        enqueue_analysis_job(job.id, str(upload_path), filename, goal, workspace, data_dictionary, options, approved_plan, preflight_contract)
    else:
        thread = threading.Thread(
            target=run_analysis_job,
            args=(store, semaphore, job.id, upload_path, filename, goal, config, workspace, data_dictionary, options, approved_plan, preflight_contract),
            daemon=True,
        )
        thread.start()
    return job_to_dict(job)


def enqueue_analysis_job(
    job_id: str,
    upload_path: str,
    filename: str,
    goal: str,
    workspace: str,
    data_dictionary: dict[str, str] | None,
    analysis_options: AnalysisOptions | dict[str, str] | None,
    approved_plan: AnalysisPlan | None = None,
    preflight_contract: dict[str, Any] | None = None,
) -> None:
    try:
        from backend.worker import enqueue_job
    except ImportError as exc:
        raise RuntimeError("队列模式需要安装 redis 和 rq。") from exc
    enqueue_job(job_id, upload_path, filename, goal, workspace, data_dictionary, normalize_analysis_options(analysis_options).to_dict(), approved_plan, preflight_contract)


def run_analysis_job(
    store: JobStore,
    semaphore: threading.BoundedSemaphore | None,
    job_id: str,
    upload_path: Path,
    filename: str,
    goal: str,
    config: AppConfig,
    workspace: str = "default",
    data_dictionary: dict[str, str] | None = None,
    analysis_options: AnalysisOptions | dict[str, str] | None = None,
    approved_plan: AnalysisPlan | None = None,
    preflight_contract: dict[str, Any] | None = None,
) -> None:
    acquired = True
    if semaphore is not None:
        acquired = semaphore.acquire(timeout=1)
    if not acquired:
        store.fail(job_id, "当前没有可用的执行容量。")
        upload_path.unlink(missing_ok=True)
        return

    started = time.monotonic()
    try:
        if store.is_cancelled(job_id):
            return
        store.set_running(job_id, "正在读取数据并生成数据画像。")

        if time.monotonic() - started > config.job_timeout_seconds:
            raise TimeoutError("任务在开始分析前超时。")
        if store.is_cancelled(job_id):
            return

        store.add_event(job_id, "Planning", "completed", "已根据字段结构和目标生成分析计划。")
        options = normalize_analysis_options(analysis_options)
        result = DataAnalystAgent().analyze_csv(
            upload_path,
            goal,
            source_name=filename,
            data_dictionary=data_dictionary,
            input_security_findings=(preflight_contract or {}).get("security_findings", []),
            analysis_options=options,
            approved_plan=approved_plan,
            is_cancelled=lambda: store.is_cancelled(job_id),
            tool_timeout_seconds=max(1, min(config.job_timeout_seconds, 30)),
        )

        if time.monotonic() - started > config.job_timeout_seconds:
            raise TimeoutError("任务超过配置的执行超时时间。")
        if store.is_cancelled(job_id):
            return

        payload = agent_result_to_dict(result)
        payload["source_filename"] = filename
        payload["job_id"] = job_id
        payload["workspace"] = workspace
        if preflight_contract:
            payload["preflight_contract"] = preflight_contract
            payload["approved_plan"] = {
                "id": preflight_contract.get("plan_id"),
                "fingerprint": preflight_contract.get("fingerprint"),
                "plan": agent_result_to_dict(result).get("plan"),
            }
        store.add_event(job_id, "Executing tools", "completed", "Python 和 SQL 分析步骤已完成。")
        config.report_dir.mkdir(parents=True, exist_ok=True)
        report_path = config.report_dir / f"{job_id}.md"
        report_path.write_text(result.report_markdown, encoding="utf-8")
        store.complete(job_id, payload, report_path)
    except Exception as exc:
        if not store.is_cancelled(job_id):
            store.fail(job_id, str(exc))
    finally:
        upload_path.unlink(missing_ok=True)
        if semaphore is not None:
            semaphore.release()


def normalize_analysis_options(analysis_options: AnalysisOptions | dict[str, str] | None) -> AnalysisOptions:
    if isinstance(analysis_options, AnalysisOptions):
        return analysis_options
    return parse_analysis_options(analysis_options)
