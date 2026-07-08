from __future__ import annotations

import argparse
import csv
import html
import json
import mimetypes
import re
import sys
import tempfile
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from io import StringIO
from urllib.parse import parse_qs, unquote, urlparse

from backend.audit import AuditContext, audit
from backend.authz import Principal, can_access_job_scope, has_permission, normalize_principal_value, normalize_workspace, token_is_valid
from backend.config import AppConfig, load_config, require_valid_runtime_config
from backend.exporters import markdown_to_pdf, markdown_to_pptx
from backend.job_store import JobStore, job_to_dict
from backend.observability import log_event
from backend.rate_limiter import InMemoryRateLimiter
from backend.metrics_exporter import metrics_to_prometheus
from backend.security_headers import SECURITY_HEADERS
from backend.usage import build_account_usage, build_usage_alerts, usage_summary_for_metrics
from data_analyst_agent.agent import DataAnalystAgent
from data_analyst_agent.followup import answer_followup
from data_analyst_agent.options import parse_analysis_options as parse_agent_analysis_options
from data_analyst_agent.serialization import agent_result_to_dict


CONFIG = load_config()
JOB_STORE = JobStore(CONFIG.database_path)
JOB_SEMAPHORE = threading.BoundedSemaphore(CONFIG.max_concurrent_jobs)
RATE_LIMITER = InMemoryRateLimiter(CONFIG.rate_limit_per_minute, 60)


class DataAnalystRequestHandler(BaseHTTPRequestHandler):
    server_version = "DataAnalystAgent/0.2"

    def end_headers(self) -> None:
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        super().end_headers()

    def do_GET(self) -> None:
        request = urlparse(self.path)
        requested_path = unquote(request.path)
        context = self.audit_context()

        if requested_path == "/api/health":
            self.handle_health()
            return

        if requested_path == "/api/jobs":
            if not self.require_auth():
                return
            if not self.require_permission("job.list"):
                return
            self.handle_list_jobs(parse_qs(request.query))
            audit(JOB_STORE, context, "job.list", "jobs")
            return

        if requested_path == "/api/account":
            if not self.require_auth():
                return
            if not self.require_permission("account.read"):
                return
            self.handle_account()
            audit(JOB_STORE, context, "account.read", "account")
            return

        if requested_path.startswith("/api/jobs/"):
            if not self.require_auth():
                return
            if not self.require_permission("job.read"):
                return
            self.handle_get_job(requested_path)
            audit(JOB_STORE, context, "job.read", requested_path.rsplit("/", 1)[-1])
            return

        if requested_path.startswith("/api/reports/"):
            if not self.require_auth():
                return
            if not self.require_permission("report.read"):
                return
            self.handle_get_report(requested_path, parse_qs(request.query))
            audit(JOB_STORE, context, "report.read", requested_path.rsplit("/", 1)[-1])
            return

        if requested_path == "/api/audit":
            if not self.require_auth():
                return
            if not self.require_permission("audit.read"):
                return
            self.send_json({"events": JOB_STORE.list_audit_events(limit=100)})
            audit(JOB_STORE, context, "audit.read", "audit_log")
            return

        if requested_path == "/api/metrics":
            if not self.require_auth():
                return
            if not self.require_permission("metrics.read"):
                return
            self.handle_metrics()
            audit(JOB_STORE, context, "metrics.read", "metrics")
            return

        if requested_path == "/api/alerts":
            if not self.require_auth():
                return
            if not self.require_permission("metrics.read"):
                return
            self.handle_alerts()
            audit(JOB_STORE, context, "metrics.read", "alerts")
            return

        if requested_path == "/api/metrics.prometheus":
            if not self.require_auth():
                return
            if not self.require_permission("metrics.read"):
                return
            self.handle_prometheus_metrics()
            audit(JOB_STORE, context, "metrics.read", "metrics.prometheus")
            return

        if requested_path == "/":
            requested_path = "/index.html"
        self.serve_static(requested_path)

    def do_POST(self) -> None:
        request = urlparse(self.path)
        requested_path = unquote(request.path)
        if requested_path.startswith("/api/jobs/") and requested_path.endswith("/ask"):
            if not self.require_auth():
                return
            if not self.require_permission("job.read"):
                return
            self.handle_followup_question(requested_path)
            return
        if request.path != "/api/analyze":
            self.send_json({"error": "接口不存在，请确认服务已重启到最新版本。"}, status=HTTPStatus.NOT_FOUND)
            return
        if not self.require_auth():
            return
        if not self.require_permission("job.create"):
            return
        if not self.require_rate_limit():
            return
        self.handle_create_job(self.audit_context())

    def do_DELETE(self) -> None:
        request = urlparse(self.path)
        requested_path = unquote(request.path)
        if requested_path == "/api/jobs":
            if not self.require_auth():
                return
            if not self.require_permission("job.cleanup"):
                return
            self.handle_cleanup_jobs(parse_qs(request.query))
            audit(JOB_STORE, self.audit_context(), "job.cleanup", "jobs")
            return
        if not requested_path.startswith("/api/jobs/"):
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        if not self.require_auth():
            return
        if not self.require_permission("job.cancel"):
            return
        job_id = requested_path.rsplit("/", 1)[-1]
        job = JOB_STORE.get(job_id)
        if job is None:
            self.send_json({"error": "任务不存在。"}, status=HTTPStatus.NOT_FOUND)
            return
        if not self.can_access_job(job):
            self.send_json({"error": "无权访问该任务。"}, status=HTTPStatus.FORBIDDEN)
            return
        if job.status in {"completed", "failed", "cancelled"}:
            self.send_json({"error": f"任务已处于 {job.status} 状态。"}, status=HTTPStatus.CONFLICT)
            return
        cancelled = JOB_STORE.cancel(job_id)
        audit(JOB_STORE, self.audit_context(), "job.cancel", job_id)
        self.send_json(job_to_dict(cancelled))

    def handle_create_job(self, context: AuditContext) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid Content-Length")
            return

        if length <= 0 or length > CONFIG.max_upload_bytes:
            self.send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "CSV 文件大小超出配置限制。")
            return

        content_type = self.headers.get("Content-Type", "")
        body = self.rfile.read(length)

        try:
            fields, files = parse_multipart_form(content_type, body)
            goal = fields.get("goal", "生成数据画像并找出关键模式。").strip()
            filename, dataset_bytes = files["dataset"]
            workspace = self.resolve_workspace(fields.get("workspace"))
            data_dictionary = parse_data_dictionary(fields.get("data_dictionary", ""))
            analysis_options = parse_analysis_options(fields)
        except PermissionError as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.FORBIDDEN)
            return
        except (KeyError, ValueError) as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        if not is_supported_dataset(filename):
            self.send_json({"error": "请上传 .csv、.xlsx 或 .xls 文件。"}, status=HTTPStatus.BAD_REQUEST)
            return

        if JOB_STORE.active_count() >= CONFIG.max_concurrent_jobs:
            self.send_json({"error": "当前运行中的任务过多，请稍后再试。"}, status=HTTPStatus.TOO_MANY_REQUESTS)
            return
        owner = self.actor()
        if JOB_STORE.active_count_for_actor(owner=self.actor(), organization=self.organization()) >= CONFIG.max_active_jobs_per_actor:
            self.send_json({"error": "当前用户运行中的任务已达到配额限制。"}, status=HTTPStatus.TOO_MANY_REQUESTS)
            return

        upload_path = save_upload(filename, dataset_bytes, CONFIG)
        organization = self.organization()
        job = JOB_STORE.create(filename, goal, owner=owner, organization=organization, workspace=workspace)
        audit(
            JOB_STORE,
            context,
            "job.create",
            job.id,
            {
                "filename": filename,
                "bytes": len(dataset_bytes),
                "owner": owner,
                "organization": organization,
                "workspace": workspace,
                "analysis_options": analysis_options,
            },
        )
        thread = threading.Thread(
            target=run_analysis_job,
            args=(job.id, upload_path, filename, goal, CONFIG, workspace, data_dictionary, analysis_options),
            daemon=True,
        )
        thread.start()
        log_event("job.created", actor=owner, organization=organization, workspace=workspace, job_id=job.id, filename=filename)
        self.send_json(job_to_dict(job), status=HTTPStatus.ACCEPTED)

    def handle_health(self) -> None:
        try:
            metrics = JOB_STORE.metrics()
            storage_ok = CONFIG.storage_dir.exists() or CONFIG.storage_dir.parent.exists()
            payload = {
                "status": "ok",
                "env": CONFIG.env,
                "storage": "ok" if storage_ok else "missing",
                "database": "ok",
                "active_jobs": metrics["active_jobs"],
                "max_concurrent_jobs": CONFIG.max_concurrent_jobs,
                "available_capacity": max(0, CONFIG.max_concurrent_jobs - int(metrics["active_jobs"])),
            }
            self.send_json(payload)
        except Exception as exc:
            self.send_json({"status": "degraded", "env": CONFIG.env, "error": str(exc)}, status=HTTPStatus.SERVICE_UNAVAILABLE)

    def handle_list_jobs(self, query: dict[str, list[str]]) -> None:
        try:
            limit = int((query.get("limit") or ["50"])[0])
        except ValueError:
            limit = 50
        all_scope = self.is_admin_actor() and (query.get("scope") or [""])[0] == "all"
        owner = None if all_scope else self.actor()
        organization = None if all_scope else self.organization()
        workspace = None if all_scope else self.workspace()
        jobs = JOB_STORE.list_jobs(owner=owner, organization=organization, workspace=workspace, limit=limit)
        self.send_json({"jobs": [job_to_dict(job, include_result=False) for job in jobs]})

    def handle_get_job(self, requested_path: str) -> None:
        job_id = requested_path.rsplit("/", 1)[-1]
        job = JOB_STORE.get(job_id)
        if job is None:
            self.send_json({"error": "任务不存在。"}, status=HTTPStatus.NOT_FOUND)
            return
        if not self.can_access_job(job):
            self.send_json({"error": "无权访问该任务。"}, status=HTTPStatus.FORBIDDEN)
            return
        self.send_json(job_to_dict(job))

    def handle_get_report(self, requested_path: str, query: dict[str, list[str]]) -> None:
        job_id = requested_path.rsplit("/", 1)[-1]
        job = JOB_STORE.get(job_id)
        if job is None:
            self.send_json({"error": "任务不存在。"}, status=HTTPStatus.NOT_FOUND)
            return
        if not self.can_access_job(job):
            self.send_json({"error": "无权访问该报告。"}, status=HTTPStatus.FORBIDDEN)
            return
        if job.report_path is None:
            self.send_json({"error": "报告尚未生成。"}, status=HTTPStatus.CONFLICT)
            return

        report_path = Path(job.report_path)
        report_root = CONFIG.report_dir.resolve()
        if not report_path.exists() or not str(report_path.resolve()).startswith(str(report_root)):
            self.send_json({"error": "报告文件不可用。"}, status=HTTPStatus.NOT_FOUND)
            return

        report_format = (query.get("format") or ["md"])[0].lower()
        markdown = report_path.read_text(encoding="utf-8")
        if report_format == "html":
            data = markdown_to_html(markdown).encode("utf-8")
            content_type = "text/html; charset=utf-8"
            filename = f"{job_id}.html"
        elif report_format == "csv":
            data = result_to_csv_summary(job.result or {}).encode("utf-8-sig")
            content_type = "text/csv; charset=utf-8"
            filename = f"{job_id}.csv"
        elif report_format == "pdf":
            try:
                data = markdown_to_pdf(markdown)
            except RuntimeError as exc:
                self.send_json({"error": str(exc)}, status=HTTPStatus.NOT_IMPLEMENTED)
                return
            content_type = "application/pdf"
            filename = f"{job_id}.pdf"
        elif report_format == "pptx":
            try:
                data = markdown_to_pptx(markdown)
            except RuntimeError as exc:
                self.send_json({"error": str(exc)}, status=HTTPStatus.NOT_IMPLEMENTED)
                return
            content_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            filename = f"{job_id}.pptx"
        else:
            data = markdown.encode("utf-8")
            content_type = "text/markdown; charset=utf-8"
            filename = f"{job_id}.md"

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_followup_question(self, requested_path: str) -> None:
        job_id = requested_path.removeprefix("/api/jobs/").removesuffix("/ask").strip("/")
        job = JOB_STORE.get(job_id)
        if job is None:
            self.send_json({"error": "任务不存在。"}, status=HTTPStatus.NOT_FOUND)
            return
        if not self.can_access_job(job):
            self.send_json({"error": "无权访问该任务。"}, status=HTTPStatus.FORBIDDEN)
            return
        if job.status != "completed" or not job.result:
            self.send_json({"error": "任务尚未完成，暂时不能追问。"}, status=HTTPStatus.CONFLICT)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            payload = json.loads(body.decode("utf-8") or "{}")
            question = str(payload.get("question", ""))
            report_markdown = Path(job.report_path).read_text(encoding="utf-8") if job.report_path else ""
            answer = answer_followup(job.result, report_markdown, question)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except json.JSONDecodeError:
            self.send_json({"error": "请求体必须是 JSON。"}, status=HTTPStatus.BAD_REQUEST)
            return

        audit(JOB_STORE, self.audit_context(), "job.ask", job.id, {"question": question[:200]})
        self.send_json(answer)

    def handle_cleanup_jobs(self, query: dict[str, list[str]]) -> None:
        try:
            older_than_days = int((query.get("older_than_days") or ["30"])[0])
        except ValueError:
            older_than_days = 30
        if older_than_days < 1:
            self.send_json({"error": "older_than_days 必须大于等于 1。"}, status=HTTPStatus.BAD_REQUEST)
            return
        deleted = JOB_STORE.cleanup_terminal_jobs(older_than_days=older_than_days)
        self.send_json({"deleted_jobs": deleted, "older_than_days": older_than_days})

    def handle_metrics(self) -> None:
        owner = None if self.is_admin_actor() else self.actor()
        organization = None if self.is_admin_actor() else self.organization()
        workspace = None if self.is_admin_actor() else self.workspace()
        payload = JOB_STORE.metrics(owner=owner, organization=organization, workspace=workspace)
        payload.update(usage_summary_for_metrics(payload, self.headers.get("X-Plan")))
        payload.update(
            {
                "env": CONFIG.env,
                "scope": "all" if owner is None else "actor",
                "actor": self.actor(),
                "max_concurrent_jobs": CONFIG.max_concurrent_jobs,
                "max_upload_mb": round(CONFIG.max_upload_bytes / 1024 / 1024, 2),
                "job_timeout_seconds": CONFIG.job_timeout_seconds,
                "llm_provider": CONFIG.llm_provider,
                "llm_model": CONFIG.llm_model,
                "trace_enabled": True,
            }
        )
        self.send_json(payload)

    def handle_alerts(self) -> None:
        owner = None if self.is_admin_actor() else self.actor()
        organization = None if self.is_admin_actor() else self.organization()
        workspace = None if self.is_admin_actor() else self.workspace()
        metrics = JOB_STORE.metrics(owner=owner, organization=organization, workspace=workspace)
        metrics.update({"max_concurrent_jobs": CONFIG.max_concurrent_jobs})
        self.send_json(build_usage_alerts(metrics, self.headers.get("X-Plan")))

    def handle_prometheus_metrics(self) -> None:
        owner = None if self.is_admin_actor() else self.actor()
        organization = None if self.is_admin_actor() else self.organization()
        workspace = None if self.is_admin_actor() else self.workspace()
        metrics = JOB_STORE.metrics(owner=owner, organization=organization, workspace=workspace)
        metrics.update(usage_summary_for_metrics(metrics, self.headers.get("X-Plan")))
        data = metrics_to_prometheus(metrics).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_account(self) -> None:
        metrics = JOB_STORE.metrics(owner=self.actor(), organization=self.organization(), workspace=self.workspace())
        payload = build_account_usage(
            principal=self.principal(),
            metrics=metrics,
            configured_max_active_jobs=CONFIG.max_active_jobs_per_actor,
            configured_max_upload_bytes=CONFIG.max_upload_bytes,
            plan_name=self.headers.get("X-Plan"),
        )
        self.send_json(payload)

    def serve_static(self, requested_path: str) -> None:
        candidate = (CONFIG.frontend_dir / requested_path.lstrip("/")).resolve()
        if not str(candidate).startswith(str(CONFIG.frontend_dir.resolve())) or not candidate.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        data = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def require_auth(self) -> bool:
        if token_is_valid(CONFIG.api_token, self.headers.get("X-API-Token"), self.headers.get("Authorization")):
            return True
        self.send_json({"error": "未授权。"}, status=HTTPStatus.UNAUTHORIZED)
        return False

    def actor(self) -> str:
        return normalize_principal_value(self.headers.get("X-Actor"), "local")

    def role(self) -> str:
        return normalize_principal_value((self.headers.get("X-Role") or "analyst").strip().lower(), "analyst")

    def organization(self) -> str:
        return normalize_principal_value(self.headers.get("X-Org"), "default")

    def workspace(self) -> str:
        return normalize_workspace(self.headers.get("X-Workspace"))

    def resolve_workspace(self, requested_workspace: str | None) -> str:
        workspace = normalize_workspace(requested_workspace, self.workspace())
        if not self.is_admin_actor() and workspace != self.workspace():
            raise PermissionError("不能在当前工作区之外创建任务。")
        return workspace

    def principal(self) -> Principal:
        return Principal(
            actor=self.actor(),
            role=self.role(),
            organization=self.organization(),
            workspace=self.workspace(),
            is_admin_actor=self.is_admin_actor(),
        )

    def is_admin_actor(self) -> bool:
        return self.actor() in CONFIG.admin_actors

    def require_permission(self, permission: str) -> bool:
        if has_permission(self.principal(), permission):
            return True
        self.send_json({"error": f"当前角色无权执行：{permission}。"}, status=HTTPStatus.FORBIDDEN)
        return False

    def require_rate_limit(self) -> bool:
        key = f"{self.organization()}:{self.actor()}:{self.client_address[0] if self.client_address else 'unknown'}"
        if RATE_LIMITER.allow(key):
            return True
        self.send_json({"error": "请求过于频繁，请稍后再试。"}, status=HTTPStatus.TOO_MANY_REQUESTS)
        return False

    def can_access_job(self, job) -> bool:
        workspace = self.workspace() if hasattr(self, "workspace") else "default"
        return can_access_job_scope(
            Principal(
                actor=self.actor(),
                role=self.role() if hasattr(self, "role") else "analyst",
                organization=self.organization(),
                workspace=workspace,
                is_admin_actor=self.is_admin_actor(),
            ),
            job,
        )

    def audit_context(self) -> AuditContext:
        return AuditContext(
            actor=self.actor(),
            ip_address=self.client_address[0] if self.client_address else "unknown",
            trace_id=self.headers.get("X-Trace-ID") or uuid.uuid4().hex,
        )

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))


def parse_multipart_form(content_type: str, body: bytes) -> tuple[dict[str, str], dict[str, tuple[str, bytes]]]:
    boundary_match = re.search(r"boundary=(?P<boundary>[^;]+)", content_type)
    if not boundary_match:
        raise ValueError("请求必须是 multipart/form-data 上传。")

    boundary = boundary_match.group("boundary").strip().strip('"').encode("utf-8")
    delimiter = b"--" + boundary
    fields: dict[str, str] = {}
    files: dict[str, tuple[str, bytes]] = {}

    for raw_part in body.split(delimiter):
        part = raw_part.strip()
        if not part or part == b"--":
            continue
        if part.endswith(b"--"):
            part = part[:-2].strip()
        if b"\r\n\r\n" not in part:
            continue

        header_blob, content = part.split(b"\r\n\r\n", 1)
        headers = parse_headers(header_blob.decode("utf-8", errors="replace"))
        disposition = headers.get("content-disposition", "")
        name = extract_disposition_value(disposition, "name")
        if not name:
            continue

        filename = extract_disposition_value(disposition, "filename")
        content = content.rstrip(b"\r\n")
        if filename:
            files[name] = (Path(filename).name, content)
        else:
            fields[name] = content.decode("utf-8", errors="replace")

    if "dataset" not in files:
        raise ValueError("缺少名为 dataset 的 CSV 文件字段。")
    return fields, files


def parse_headers(header_blob: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in header_blob.split("\r\n"):
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers[name.strip().lower()] = value.strip()
    return headers


def extract_disposition_value(disposition: str, key: str) -> str | None:
    match = re.search(rf'{key}="(?P<value>[^"]*)"', disposition)
    return match.group("value") if match else None


def parse_data_dictionary(raw_value: str) -> dict[str, str]:
    if not raw_value.strip():
        return {}
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError("数据字典必须是 JSON 对象，例如 {\"收入\":\"revenue\"}。") from exc
    if not isinstance(payload, dict):
        raise ValueError("数据字典必须是 JSON 对象。")
    return {str(column): str(role) for column, role in payload.items()}


def parse_analysis_options(fields: dict[str, str]) -> dict[str, str]:
    return parse_agent_analysis_options(fields).to_dict()


def save_upload(filename: str, content: bytes, config: AppConfig) -> Path:
    config.upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix or ".csv"
    with tempfile.NamedTemporaryFile(delete=False, dir=config.upload_dir, suffix=suffix) as handle:
        handle.write(content)
        return Path(handle.name)


def is_supported_dataset(filename: str) -> bool:
    return Path(filename).suffix.lower() in {".csv", ".xlsx", ".xls"}


def run_analysis_job(
    job_id: str,
    upload_path: Path,
    filename: str,
    goal: str,
    config: AppConfig,
    workspace: str = "default",
    data_dictionary: dict[str, str] | None = None,
    analysis_options: dict[str, str] | None = None,
) -> None:
    acquired = JOB_SEMAPHORE.acquire(timeout=1)
    if not acquired:
        JOB_STORE.fail(job_id, "当前没有可用的执行容量。")
        upload_path.unlink(missing_ok=True)
        return

    started = time.monotonic()
    try:
        if JOB_STORE.is_cancelled(job_id):
            return
        JOB_STORE.set_running(job_id, "正在读取 CSV 并生成数据画像。")

        if time.monotonic() - started > config.job_timeout_seconds:
            raise TimeoutError("任务在开始分析前超时。")
        if JOB_STORE.is_cancelled(job_id):
            return

        JOB_STORE.add_event(job_id, "Planning", "completed", "已根据字段结构和目标生成分析计划。")
        result = DataAnalystAgent().analyze_csv(
            upload_path,
            goal,
            source_name=filename,
            data_dictionary=data_dictionary,
            analysis_options=analysis_options,
            is_cancelled=lambda: JOB_STORE.is_cancelled(job_id),
            tool_timeout_seconds=max(1, min(config.job_timeout_seconds, 30)),
        )

        if time.monotonic() - started > config.job_timeout_seconds:
            raise TimeoutError("任务超过配置的执行超时时间。")
        if JOB_STORE.is_cancelled(job_id):
            return

        payload = agent_result_to_dict(result)
        payload["source_filename"] = filename
        payload["job_id"] = job_id
        payload["workspace"] = workspace
        JOB_STORE.add_event(job_id, "Executing tools", "completed", "Python 和 SQL 分析步骤已完成。")
        config.report_dir.mkdir(parents=True, exist_ok=True)
        report_path = config.report_dir / f"{job_id}.md"
        report_path.write_text(result.report_markdown, encoding="utf-8")
        JOB_STORE.complete(job_id, payload, report_path)
    except Exception as exc:
        if not JOB_STORE.is_cancelled(job_id):
            JOB_STORE.fail(job_id, str(exc))
    finally:
        upload_path.unlink(missing_ok=True)
        JOB_SEMAPHORE.release()


def markdown_to_html(markdown: str) -> str:
    body_lines: list[str] = []
    in_code = False
    for line in markdown.splitlines():
        if line.startswith("```"):
            body_lines.append("</code></pre>" if in_code else "<pre><code>")
            in_code = not in_code
            continue
        escaped = html.escape(line)
        if in_code:
            body_lines.append(escaped)
        elif line.startswith("# "):
            body_lines.append(f"<h1>{escaped[2:]}</h1>")
        elif line.startswith("## "):
            body_lines.append(f"<h2>{escaped[3:]}</h2>")
        elif line.startswith("### "):
            body_lines.append(f"<h3>{escaped[4:]}</h3>")
        elif line.startswith("- "):
            body_lines.append(f"<p>• {escaped[2:]}</p>")
        elif not line.strip():
            body_lines.append("")
        else:
            body_lines.append(f"<p>{escaped}</p>")
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>数据分析报告</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:960px;margin:40px auto;line-height:1.55;color:#182026}"
        "pre{background:#111827;color:#d6e3f0;padding:14px;border-radius:8px;overflow:auto}"
        "h1,h2,h3{line-height:1.2}</style></head><body>"
        + "\n".join(body_lines)
        + "</body></html>"
    )


def result_to_csv_summary(result: dict[str, object]) -> str:
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["title", "type", "severity", "confidence", "metric_value", "detail", "recommendation", "needs_review"],
    )
    writer.writeheader()
    for insight in result.get("insights", []) if isinstance(result, dict) else []:
        if not isinstance(insight, dict):
            continue
        writer.writerow(
            {
                "title": insight.get("title", ""),
                "type": insight.get("insight_type", ""),
                "severity": insight.get("severity", ""),
                "confidence": insight.get("confidence", ""),
                "metric_value": insight.get("metric_value", ""),
                "detail": insight.get("detail", ""),
                "recommendation": insight.get("recommendation", ""),
                "needs_review": insight.get("needs_review", ""),
            }
        )
    return output.getvalue()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Data Analyst Agent web server.")
    parser.add_argument("--host", default=CONFIG.host)
    parser.add_argument("--port", default=CONFIG.port, type=int)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    require_valid_runtime_config(CONFIG)
    server = ThreadingHTTPServer((args.host, args.port), DataAnalystRequestHandler)
    print(f"Data Analyst Agent is running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
