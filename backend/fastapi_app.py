from __future__ import annotations

import argparse
import hashlib
import json
import threading
import uuid
from http import HTTPStatus
from pathlib import Path
from typing import Annotated, Literal

from backend.audit import AuditContext, audit
from backend.authz import Principal, can_access_job_scope, has_permission, normalize_principal_value, normalize_workspace, token_is_valid
from backend.config import load_config, require_valid_runtime_config
from backend.exporters import markdown_to_pdf, markdown_to_pptx
from backend.job_store import job_to_dict
from backend.observability import log_event
from backend.rate_limiter import InMemoryRateLimiter
from backend.schemas import AccountUsageResponse, AlertsResponse, AuditLogResponse, CleanupResponse, FollowupRequest, FollowupResponse, HealthResponse, JobListResponse, JobResponse, MetricsResponse, PreflightPlanRequest, PreflightPlanResponse, PreflightResponse
from backend.security_headers import apply_security_headers
from backend.server import markdown_to_html, result_to_csv_summary
from backend.metrics_exporter import metrics_to_prometheus
from backend.service import create_analysis_job, is_supported_dataset
from backend.preflight import (
    PreflightRegistry,
    analysis_plan_from_dict,
    create_execution_contract,
    normalize_data_dictionary,
    plan_to_dict,
    preflight_to_dict,
    verify_execution_contract,
)
from backend.store_factory import build_job_store
from backend.usage import build_account_usage, build_usage_alerts, usage_summary_for_metrics
from data_analyst_agent.followup import answer_followup
from data_analyst_agent.options import parse_analysis_options
from data_analyst_agent.serialization import to_jsonable

try:
    from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
    from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
    from fastapi.staticfiles import StaticFiles
except ImportError as exc:  # pragma: no cover - exercised only without optional deps
    FastAPI = None  # type: ignore[assignment]
    FASTAPI_IMPORT_ERROR = exc
else:
    FASTAPI_IMPORT_ERROR = None


CONFIG = load_config()
JOB_STORE = build_job_store(CONFIG)
JOB_SEMAPHORE = threading.BoundedSemaphore(CONFIG.max_concurrent_jobs)
RATE_LIMITER = InMemoryRateLimiter(CONFIG.rate_limit_per_minute, 60)
PREFLIGHTS = PreflightRegistry(redis_url=CONFIG.redis_url)


def create_app():
    if FastAPI is None:
        raise RuntimeError("FastAPI 服务需要安装生产依赖：pip install -e .[prod]") from FASTAPI_IMPORT_ERROR
    require_valid_runtime_config(CONFIG)

    app = FastAPI(
        title="Data Analyst Agent API",
        version="0.4.0",
        description="中文数据分析 Agent 的生产 API，包含任务、报告、指标、审计和 OpenAPI Schema。",
    )

    @app.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        apply_security_headers(response.headers)
        return response

    @app.get("/api/health", response_model=HealthResponse, tags=["ops"])
    def health() -> dict[str, object]:
        metrics = JOB_STORE.metrics()
        return {
            "status": "ok",
            "env": CONFIG.env,
            "database": "postgresql" if CONFIG.database_url else "sqlite",
            "queue": "redis-rq" if CONFIG.redis_url else "in-process",
            "executor_mode": CONFIG.executor_mode,
            "active_jobs": metrics["active_jobs"],
            "max_concurrent_jobs": CONFIG.max_concurrent_jobs,
        }

    @app.get("/api/account", response_model=AccountUsageResponse, tags=["account"])
    def account_usage(
        principal: Annotated[Principal, Depends(current_principal)],
        x_plan: Annotated[str | None, Header(alias="X-Plan")] = None,
    ) -> dict[str, object]:
        require(principal, "account.read")
        metrics = JOB_STORE.metrics(owner=principal.actor, organization=principal.organization, workspace=principal.workspace)
        return build_account_usage(
            principal=principal,
            metrics=metrics,
            configured_max_active_jobs=CONFIG.max_active_jobs_per_actor,
            configured_max_upload_bytes=CONFIG.max_upload_bytes,
            plan_name=x_plan,
        )

    @app.get("/api/examples/sales.csv", tags=["examples"])
    def example_sales_dataset() -> FileResponse:
        path = CONFIG.frontend_dir.parent / "examples" / "sales.csv"
        if not path.exists():
            raise HTTPException(status_code=404, detail="示例数据不可用。")
        return FileResponse(path, media_type="text/csv; charset=utf-8", filename="sales.csv")

    @app.post("/api/preflights", status_code=HTTPStatus.CREATED, response_model=PreflightResponse, tags=["analysis"])
    async def create_preflight(
        principal: Annotated[Principal, Depends(current_principal)],
        dataset: Annotated[UploadFile, File()],
        workspace: Annotated[str | None, Form()] = None,
        x_trace_id: Annotated[str | None, Header(alias="X-Trace-ID")] = None,
    ) -> dict[str, object]:
        require(principal, "job.create")
        resolved_workspace = resolve_workspace(principal, workspace)
        if not dataset.filename or not is_supported_dataset(dataset.filename):
            raise HTTPException(status_code=400, detail="Please upload a .csv, .xlsx, or .xls file.")
        content = await dataset.read()
        if not content or len(content) > CONFIG.max_upload_bytes:
            raise HTTPException(status_code=413, detail="Dataset file exceeds the configured size limit.")
        try:
            record = PREFLIGHTS.create(
                filename=Path(dataset.filename).name,
                content=content,
                owner=principal.actor,
                organization=principal.organization,
                workspace=resolved_workspace,
            )
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        audit(
            JOB_STORE,
            AuditContext(principal.actor, "fastapi", x_trace_id or uuid.uuid4().hex),
            "dataset.preflight",
            record.id,
            {"filename": record.filename, "bytes": record.size_bytes, "fingerprint": record.fingerprint},
        )
        return preflight_to_dict(record)

    @app.post("/api/preflights/{preflight_id}/plans", status_code=HTTPStatus.CREATED, response_model=PreflightPlanResponse, tags=["analysis"])
    def create_preflight_plan(
        preflight_id: str,
        payload: PreflightPlanRequest,
        principal: Annotated[Principal, Depends(current_principal)],
        x_trace_id: Annotated[str | None, Header(alias="X-Trace-ID")] = None,
    ) -> dict[str, object]:
        require(principal, "job.create")
        record = PREFLIGHTS.get(preflight_id, owner=principal.actor, organization=principal.organization, workspace=principal.workspace)
        if record is None:
            raise HTTPException(status_code=404, detail="Preflight is unavailable, expired, or outside the current workspace.")
        try:
            dictionary = normalize_data_dictionary(payload.data_dictionary)
            options = parse_analysis_options(payload.model_dump())
            plan_id, plan = PREFLIGHTS.create_plan(record, goal=payload.goal.strip(), data_dictionary=dictionary)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        audit(
            JOB_STORE,
            AuditContext(principal.actor, "fastapi", x_trace_id or uuid.uuid4().hex),
            "analysis.plan_created",
            plan_id,
            {"preflight_id": record.id, "fingerprint": record.fingerprint, "steps": len(plan.steps)},
        )
        return {
            "id": plan_id,
            "preflight_id": record.id,
            "fingerprint": record.fingerprint,
            "execution_contract": create_execution_contract(record, plan_id, plan, data_dictionary=dictionary, analysis_options=options, signing_secret=CONFIG.preflight_signing_secret),
            "plan": plan_to_dict(plan),
        }

    @app.post("/api/analyze", status_code=HTTPStatus.ACCEPTED, response_model=JobResponse, tags=["analysis"])
    async def analyze(
        principal: Annotated[Principal, Depends(current_principal)],
        dataset: Annotated[UploadFile, File()],
        goal: Annotated[str, Form()] = "生成数据画像并找出关键模式。",
        workspace: Annotated[str | None, Form()] = None,
        data_dictionary: Annotated[str, Form()] = "",
        business_scenario: Annotated[str, Form()] = "sales",
        report_audience: Annotated[str, Form()] = "manager",
        analysis_depth: Annotated[str, Form()] = "quick",
        delivery_format: Annotated[str, Form()] = "business_report",
        preflight_id: Annotated[str | None, Form()] = None,
        plan_id: Annotated[str | None, Form()] = None,
        preflight_fingerprint: Annotated[str | None, Form()] = None,
        preflight_contract: Annotated[str | None, Form()] = None,
        x_trace_id: Annotated[str | None, Header(alias="X-Trace-ID")] = None,
    ) -> dict[str, object]:
        require(principal, "job.create")
        resolved_workspace = resolve_workspace(principal, workspace)
        if not RATE_LIMITER.allow(f"{principal.organization}:{principal.actor}"):
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试。")
        if JOB_STORE.active_count_for_actor(principal.actor, principal.organization) >= CONFIG.max_active_jobs_per_actor:
            raise HTTPException(status_code=429, detail="当前用户运行中的任务已达到配额限制。")
        if not dataset.filename or not is_supported_dataset(dataset.filename):
            raise HTTPException(status_code=400, detail="请上传 .csv、.xlsx 或 .xls 文件。")
        content = await dataset.read()
        if not content or len(content) > CONFIG.max_upload_bytes:
            raise HTTPException(status_code=413, detail="数据文件大小超出配置限制。")
        dictionary = normalize_data_dictionary(parse_data_dictionary(data_dictionary))
        options = parse_analysis_options({"business_scenario": business_scenario, "report_audience": report_audience, "analysis_depth": analysis_depth, "delivery_format": delivery_format})
        approved_plan = None
        submitted_contract = preflight_contract
        verified_contract = None
        if any((preflight_id, plan_id, preflight_fingerprint, submitted_contract)):
            if not all((preflight_id, plan_id, preflight_fingerprint, submitted_contract)):
                raise HTTPException(status_code=400, detail="Preflight id, plan id, fingerprint, and signed approval contract must be submitted together.")
            fingerprint = hashlib.sha256(content).hexdigest()
            if submitted_contract:
                try:
                    contract_payload = verify_execution_contract(
                        submitted_contract,
                        signing_secret=CONFIG.preflight_signing_secret,
                        owner=principal.actor,
                        organization=principal.organization,
                        workspace=resolved_workspace,
                        fingerprint=fingerprint,
                        goal=goal.strip(),
                        data_dictionary=dictionary,
                        analysis_options=options,
                    )
                    if contract_payload["preflight_id"] != preflight_id or contract_payload["plan_id"] != plan_id or contract_payload["fingerprint"] != preflight_fingerprint:
                        raise ValueError("Preflight approval contract does not match the submitted identifiers.")
                    approved_plan = analysis_plan_from_dict(contract_payload["plan"])
                    dictionary = contract_payload["data_dictionary"]
                    options = parse_analysis_options(contract_payload["analysis_options"])
                    verified_contract = {
                        "preflight_id": preflight_id,
                        "plan_id": plan_id,
                        "fingerprint": fingerprint,
                        "verified": True,
                        "security_findings": contract_payload.get("security_findings", []),
                    }
                except ValueError as exc:
                    raise HTTPException(status_code=409, detail=str(exc)) from exc
        context = AuditContext(principal.actor, "fastapi", x_trace_id or uuid.uuid4().hex)
        payload = create_analysis_job(
            store=JOB_STORE,
            config=CONFIG,
            semaphore=None if CONFIG.redis_url else JOB_SEMAPHORE,
            filename=Path(dataset.filename).name,
            dataset_bytes=content,
            goal=goal.strip() or "生成数据画像并找出关键模式。",
            owner=principal.actor,
            organization=principal.organization,
            workspace=resolved_workspace,
            data_dictionary=dictionary,
            analysis_options=options,
            context=context,
            approved_plan=approved_plan,
            preflight_contract=verified_contract,
            enqueue=bool(CONFIG.redis_url),
        )
        log_event("job.created", actor=principal.actor, organization=principal.organization, workspace=resolved_workspace, job_id=payload["id"])
        return payload

    @app.get("/api/jobs", response_model=JobListResponse, tags=["jobs"])
    def list_jobs(
        principal: Annotated[Principal, Depends(current_principal)],
        limit: int = Query(50, ge=1, le=200),
        scope: str = "mine",
    ) -> dict[str, object]:
        require(principal, "job.list")
        owner = None if principal.effective_role == "admin" and scope == "all" else principal.actor
        organization = None if principal.effective_role == "admin" and scope == "all" else principal.organization
        workspace_filter = None if principal.effective_role == "admin" and scope == "all" else principal.workspace
        return {
            "jobs": [
                job_to_dict(job, include_result=False)
                for job in JOB_STORE.list_jobs(owner=owner, organization=organization, workspace=workspace_filter, limit=limit)
            ]
        }

    @app.get("/api/jobs/{job_id}", response_model=JobResponse, tags=["jobs"])
    def get_job(job_id: str, principal: Annotated[Principal, Depends(current_principal)]) -> dict[str, object]:
        require(principal, "job.read")
        job = require_job(job_id, principal)
        return job_to_dict(job)

    @app.delete("/api/jobs/{job_id}", response_model=JobResponse, tags=["jobs"])
    def cancel_job(job_id: str, principal: Annotated[Principal, Depends(current_principal)]) -> dict[str, object]:
        require(principal, "job.cancel")
        job = require_job(job_id, principal)
        if job.status in {"completed", "failed", "cancelled"}:
            raise HTTPException(status_code=409, detail=f"任务已处于 {job.status} 状态。")
        return job_to_dict(JOB_STORE.cancel(job.id))

    @app.delete("/api/jobs", response_model=CleanupResponse, tags=["jobs"])
    def cleanup_jobs(principal: Annotated[Principal, Depends(current_principal)], older_than_days: int = Query(30, ge=1)) -> dict[str, object]:
        require(principal, "job.cleanup")
        deleted = JOB_STORE.cleanup_terminal_jobs(older_than_days=older_than_days)
        return {"deleted_jobs": deleted, "older_than_days": older_than_days}

    @app.get("/api/reports/{job_id}", tags=["reports"])
    def get_report(
        job_id: str,
        principal: Annotated[Principal, Depends(current_principal)],
        format: Literal["md", "html", "csv", "pdf", "pptx"] = Query("md"),
    ) -> Response:
        require(principal, "report.read")
        job = require_job(job_id, principal)
        if not job.report_path:
            raise HTTPException(status_code=409, detail="报告尚未生成。")
        report_path = Path(job.report_path)
        report_root = CONFIG.report_dir.resolve()
        try:
            resolved_report_path = report_path.resolve()
            resolved_report_path.relative_to(report_root)
        except ValueError:
            raise HTTPException(status_code=404, detail="报告文件不可用。") from None
        if not resolved_report_path.exists():
            raise HTTPException(status_code=404, detail="报告文件不可用。")
        markdown = resolved_report_path.read_text(encoding="utf-8")
        if format == "html":
            return HTMLResponse(markdown_to_html(markdown), headers={"Content-Disposition": f'attachment; filename="{job_id}.html"'})
        if format == "csv":
            return Response(
                result_to_csv_summary(job.result or {}),
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{job_id}.csv"'},
            )
        if format == "pdf":
            try:
                return Response(
                    markdown_to_pdf(markdown),
                    media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{job_id}.pdf"'},
                )
            except RuntimeError as exc:
                raise HTTPException(status_code=501, detail=str(exc)) from exc
        if format == "pptx":
            try:
                return Response(
                    markdown_to_pptx(markdown),
                    media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    headers={"Content-Disposition": f'attachment; filename="{job_id}.pptx"'},
                )
            except RuntimeError as exc:
                raise HTTPException(status_code=501, detail=str(exc)) from exc
        return PlainTextResponse(markdown, media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{job_id}.md"'})

    @app.post("/api/jobs/{job_id}/ask", response_model=FollowupResponse, tags=["jobs"])
    def ask_job(job_id: str, payload: FollowupRequest, principal: Annotated[Principal, Depends(current_principal)]) -> dict[str, object]:
        require(principal, "job.read")
        job = require_job(job_id, principal)
        if job.status != "completed" or not job.result:
            raise HTTPException(status_code=409, detail="任务尚未完成，暂时不能追问。")
        report_markdown = Path(job.report_path).read_text(encoding="utf-8") if job.report_path else ""
        try:
            answer = answer_followup(job.result, report_markdown, payload.question)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        audit(JOB_STORE, AuditContext(principal.actor, "fastapi", uuid.uuid4().hex), "job.ask", job.id, {"question": answer["question"][:200]})
        return answer

    @app.get("/api/metrics", response_model=MetricsResponse, tags=["ops"])
    def metrics(
        principal: Annotated[Principal, Depends(current_principal)],
        x_plan: Annotated[str | None, Header(alias="X-Plan")] = None,
    ) -> dict[str, object]:
        require(principal, "metrics.read")
        owner = None if principal.effective_role == "admin" else principal.actor
        organization = None if principal.effective_role == "admin" else principal.organization
        workspace = None if principal.effective_role == "admin" else principal.workspace
        payload = JOB_STORE.metrics(owner=owner, organization=organization, workspace=workspace)
        payload.update(usage_summary_for_metrics(payload, x_plan))
        payload.update({"scope": "all" if owner is None else "actor", "queue": "redis-rq" if CONFIG.redis_url else "in-process"})
        return payload

    @app.get("/api/alerts", response_model=AlertsResponse, tags=["ops"])
    def alerts(
        principal: Annotated[Principal, Depends(current_principal)],
        x_plan: Annotated[str | None, Header(alias="X-Plan")] = None,
    ) -> dict[str, object]:
        require(principal, "metrics.read")
        owner = None if principal.effective_role == "admin" else principal.actor
        organization = None if principal.effective_role == "admin" else principal.organization
        workspace = None if principal.effective_role == "admin" else principal.workspace
        payload = JOB_STORE.metrics(owner=owner, organization=organization, workspace=workspace)
        payload.update({"max_concurrent_jobs": CONFIG.max_concurrent_jobs})
        return build_usage_alerts(payload, x_plan)

    @app.get("/api/metrics.prometheus", tags=["ops"])
    def prometheus_metrics(
        principal: Annotated[Principal, Depends(current_principal)],
        x_plan: Annotated[str | None, Header(alias="X-Plan")] = None,
    ) -> PlainTextResponse:
        require(principal, "metrics.read")
        owner = None if principal.effective_role == "admin" else principal.actor
        organization = None if principal.effective_role == "admin" else principal.organization
        workspace = None if principal.effective_role == "admin" else principal.workspace
        payload = JOB_STORE.metrics(owner=owner, organization=organization, workspace=workspace)
        payload.update(usage_summary_for_metrics(payload, x_plan))
        payload.update({"queue": "redis-rq" if CONFIG.redis_url else "in-process"})
        return PlainTextResponse(metrics_to_prometheus(payload), media_type="text/plain; version=0.0.4; charset=utf-8")

    @app.get("/api/audit", response_model=AuditLogResponse, tags=["ops"])
    def audit_log(principal: Annotated[Principal, Depends(current_principal)]) -> dict[str, object]:
        require(principal, "audit.read")
        return {"events": JOB_STORE.list_audit_events(limit=100)}

    app.mount("/", StaticFiles(directory=CONFIG.frontend_dir, html=True), name="frontend")
    return app


def current_principal(
    x_actor: Annotated[str | None, Header(alias="X-Actor")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
    x_org: Annotated[str | None, Header(alias="X-Org")] = None,
    x_workspace: Annotated[str | None, Header(alias="X-Workspace")] = None,
    x_api_token: Annotated[str | None, Header(alias="X-API-Token")] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> Principal:
    if not token_is_valid(CONFIG.api_token, x_api_token, authorization):
        raise HTTPException(status_code=401, detail="未授权。")
    try:
        actor = normalize_principal_value(x_actor, "local", strict=True)
        organization = normalize_principal_value(x_org, "default", strict=True)
        workspace = normalize_workspace(x_workspace, strict=True)
        role = normalize_principal_value((x_role or "analyst").lower(), "analyst", strict=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Principal(actor=actor, role=role, organization=organization, workspace=workspace, is_admin_actor=actor in CONFIG.admin_actors)


def require(principal: Principal, permission: str) -> None:
    if not has_permission(principal, permission):
        raise HTTPException(status_code=403, detail=f"当前角色无权执行：{permission}。")


def require_job(job_id: str, principal: Principal):
    job = JOB_STORE.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在。")
    if not can_access_job_scope(principal, job):
        raise HTTPException(status_code=403, detail="无权访问该任务。")
    return job


def parse_data_dictionary(raw_value: str) -> dict[str, str]:
    if not raw_value.strip():
        return {}
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail='数据字典必须是 JSON 对象，例如 {"收入":"revenue"}。') from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="数据字典必须是 JSON 对象。")
    return {str(column): str(role) for column, role in payload.items()}


def resolve_workspace(principal: Principal, requested_workspace: str | None) -> str:
    try:
        workspace = normalize_workspace(requested_workspace, principal.workspace, strict=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if principal.effective_role != "admin" and workspace != principal.workspace:
        raise HTTPException(status_code=403, detail="不能在当前工作区之外创建任务。")
    return workspace


app = create_app() if FastAPI is not None else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the FastAPI Data Analyst Agent service.")
    parser.add_argument("--host", default=CONFIG.host)
    parser.add_argument("--port", default=CONFIG.port, type=int)
    args = parser.parse_args()
    if FastAPI is None:
        raise RuntimeError("FastAPI 服务需要安装生产依赖：pip install -e .[prod]") from FASTAPI_IMPORT_ERROR
    import uvicorn

    uvicorn.run("backend.fastapi_app:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
