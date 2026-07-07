from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from backend.job_store import JOB_STATUSES, JobEvent, JobRecord, elapsed_ms, record_from_mapping, utc_now


class PostgresJobStore:
    """PostgreSQL-backed JobStore with the same public methods used by the API.

    This adapter is intentionally small and optional. SQLite remains the default
    for local tests; production can enable this with DATA_ANALYST_AGENT_DATABASE_URL.
    """

    def __init__(self, dsn: str) -> None:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("PostgreSQL 存储需要安装 psycopg：pip install -e .[prod]") from exc
        self._psycopg = psycopg
        self._dict_row = dict_row
        self.dsn = dsn
        self._init_db()

    def close(self) -> None:
        pass

    def create(self, filename: str, goal: str, owner: str = "local", organization: str = "default", workspace: str = "default") -> JobRecord:
        now = utc_now()
        record = JobRecord(
            id=uuid.uuid4().hex,
            filename=filename,
            goal=goal,
            status="queued",
            created_at=now,
            updated_at=now,
            owner=owner,
            organization=organization,
            workspace=workspace,
            events=[JobEvent("Queued", "completed", "Dataset accepted and waiting for analysis.", now)],
        )
        self.save(record)
        return record

    def get(self, job_id: str) -> JobRecord | None:
        with self._connect() as connection:
            row = connection.execute("select * from jobs where id = %s", (job_id,)).fetchone()
        return record_from_mapping(row) if row else None

    def list_jobs(self, *, owner: str | None = None, organization: str | None = None, workspace: str | None = None, limit: int = 50) -> list[JobRecord]:
        safe_limit = max(1, min(limit, 200))
        clauses: list[str] = []
        params: list[str | int] = []
        if owner is not None:
            clauses.append("owner = %s")
            params.append(owner)
        if organization is not None:
            clauses.append("organization = %s")
            params.append(organization)
        if workspace is not None:
            clauses.append("workspace = %s")
            params.append(workspace)
        where = f" where {' and '.join(clauses)}" if clauses else ""
        params.append(safe_limit)
        with self._connect() as connection:
            rows = connection.execute(f"select * from jobs{where} order by created_at desc limit %s", tuple(params)).fetchall()
        return [record_from_mapping(row) for row in rows]

    def metrics(self, *, owner: str | None = None, organization: str | None = None, workspace: str | None = None) -> dict[str, Any]:
        clauses: list[str] = []
        params_list: list[str] = []
        if owner is not None:
            clauses.append("owner = %s")
            params_list.append(owner)
        if organization is not None:
            clauses.append("organization = %s")
            params_list.append(organization)
        if workspace is not None:
            clauses.append("workspace = %s")
            params_list.append(workspace)
        where = f" where {' and '.join(clauses)}" if clauses else ""
        params = tuple(params_list)
        with self._connect() as connection:
            total = connection.execute(f"select count(*) as total from jobs{where}", params).fetchone()["total"]
            statuses = connection.execute(f"select status, count(*) as total from jobs{where} group by status", params).fetchall()
            failed = connection.execute(f"select count(*) as total from jobs{where + (' and' if where else ' where')} status = 'failed'", params).fetchone()["total"]
            reports = connection.execute(f"select count(*) as total from jobs{where + (' and' if where else ' where')} report_path is not null", params).fetchone()["total"]
            latency = connection.execute(f"select avg(duration_ms) as avg_duration_ms from jobs{where + (' and' if where else ' where')} duration_ms is not null", params).fetchone()["avg_duration_ms"]
            p95 = connection.execute(f"select percentile_cont(0.95) within group (order by duration_ms) as p95_duration_ms from jobs{where + (' and' if where else ' where')} duration_ms is not null", params).fetchone()["p95_duration_ms"]
        by_status = {status: 0 for status in sorted(JOB_STATUSES)}
        by_status.update({row["status"]: int(row["total"]) for row in statuses})
        return {
            "total_jobs": int(total),
            "active_jobs": by_status["queued"] + by_status["running"],
            "completed_jobs": by_status["completed"],
            "failed_jobs": int(failed),
            "generated_reports": int(reports),
            "avg_duration_ms": round(float(latency or 0), 2),
            "p95_duration_ms": round(float(p95 or 0), 2),
            "by_status": by_status,
        }

    def set_running(self, job_id: str, detail: str) -> JobRecord:
        return self.update(job_id, status="running", event=JobEvent("Running", "running", detail))

    def add_event(self, job_id: str, label: str, status: str, detail: str) -> JobRecord:
        return self.update(job_id, event=JobEvent(label, status, detail))

    def complete(self, job_id: str, result: dict[str, Any], report_path: Path) -> JobRecord:
        record = self.get(job_id)
        return self.update(
            job_id,
            status="completed",
            result=result,
            error=None,
            report_path=str(report_path),
            duration_ms=elapsed_ms(record.created_at) if record else None,
            event=JobEvent("Completed", "completed", "Report generated and stored."),
        )

    def fail(self, job_id: str, error: str) -> JobRecord:
        return self.update(job_id, status="failed", error=error, event=JobEvent("Failed", "failed", error))

    def cancel(self, job_id: str, detail: str = "Cancellation requested.") -> JobRecord:
        return self.update(job_id, status="cancelled", cancelled_at=utc_now(), event=JobEvent("Cancelled", "cancelled", detail))

    def is_cancelled(self, job_id: str) -> bool:
        record = self.get(job_id)
        return record is not None and record.status == "cancelled"

    def active_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("select count(*) as total from jobs where status in ('queued', 'running')").fetchone()
        return int(row["total"])

    def active_count_for_actor(self, owner: str, organization: str | None = None) -> int:
        if organization is None:
            with self._connect() as connection:
                row = connection.execute(
                    "select count(*) as total from jobs where owner = %s and status in ('queued', 'running')",
                    (owner,),
                ).fetchone()
        else:
            with self._connect() as connection:
                row = connection.execute(
                    "select count(*) as total from jobs where owner = %s and organization = %s and status in ('queued', 'running')",
                    (owner, organization),
                ).fetchone()
        return int(row["total"])

    def cleanup_terminal_jobs(self, *, older_than_days: int) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "delete from jobs where status in ('completed','failed','cancelled') and updated_at < (now() at time zone 'utc' - (%s || ' days')::interval)",
                (older_than_days,),
            )
            return cursor.rowcount or 0

    def add_audit_event(self, *, actor: str, action: str, target: str, trace_id: str, ip_address: str, detail: dict[str, Any], timestamp: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                insert into audit_log (id, timestamp, actor, action, target, trace_id, ip_address, detail_json)
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (uuid.uuid4().hex, timestamp, actor, action, target, trace_id, ip_address, json.dumps(detail, ensure_ascii=False)),
            )

    def list_audit_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("select * from audit_log order by timestamp desc limit %s", (limit,)).fetchall()
        return [
            {
                "id": row["id"],
                "timestamp": row["timestamp"],
                "actor": row["actor"],
                "action": row["action"],
                "target": row["target"],
                "trace_id": row["trace_id"],
                "ip_address": row["ip_address"],
                "detail": json.loads(row["detail_json"] or "{}"),
            }
            for row in rows
        ]

    def update(self, job_id: str, *, status: str | None = None, event: JobEvent | None = None, result: dict[str, Any] | None = None, error: str | None = None, report_path: str | None = None, cancelled_at: str | None = None, duration_ms: float | None = None) -> JobRecord:
        record = self.get(job_id)
        if record is None:
            raise KeyError(f"Unknown job id: {job_id}")
        if status is not None:
            if status not in JOB_STATUSES:
                raise ValueError(f"Invalid job status: {status}")
            record.status = status
        if event is not None:
            record.events.append(event)
        if result is not None:
            record.result = result
        if error is not None:
            record.error = error
        if report_path is not None:
            record.report_path = report_path
        if cancelled_at is not None:
            record.cancelled_at = cancelled_at
        if duration_ms is not None:
            record.duration_ms = duration_ms
        record.updated_at = utc_now()
        self.save(record)
        return record

    def save(self, record: JobRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                insert into jobs (
                    id, filename, goal, status, created_at, updated_at, events_json,
                    result_json, error, report_path, owner, organization, workspace, cancelled_at, duration_ms
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict(id) do update set
                    filename=excluded.filename,
                    goal=excluded.goal,
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    events_json=excluded.events_json,
                    result_json=excluded.result_json,
                    error=excluded.error,
                    report_path=excluded.report_path,
                    owner=excluded.owner,
                    organization=excluded.organization,
                    workspace=excluded.workspace,
                    cancelled_at=excluded.cancelled_at,
                    duration_ms=excluded.duration_ms
                """,
                (
                    record.id,
                    record.filename,
                    record.goal,
                    record.status,
                    record.created_at,
                    record.updated_at,
                    json.dumps([asdict(event) for event in record.events], ensure_ascii=False),
                    json.dumps(record.result, ensure_ascii=False) if record.result is not None else None,
                    record.error,
                    record.report_path,
                    record.owner,
                    record.organization,
                    record.workspace,
                    record.cancelled_at,
                    record.duration_ms,
                ),
            )

    def _connect(self):
        return self._psycopg.connect(self.dsn, row_factory=self._dict_row)

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                create table if not exists jobs (
                    id text primary key,
                    filename text not null,
                    goal text not null,
                    status text not null,
                    created_at timestamptz not null,
                    updated_at timestamptz not null,
                    events_json jsonb not null,
                    result_json jsonb,
                    error text,
                    report_path text,
                    owner text not null default 'local',
                    organization text not null default 'default',
                    workspace text not null default 'default',
                    cancelled_at timestamptz,
                    duration_ms double precision
                )
                """
            )
            connection.execute("alter table jobs add column if not exists organization text not null default 'default'")
            connection.execute("alter table jobs add column if not exists workspace text not null default 'default'")
            connection.execute(
                """
                create table if not exists audit_log (
                    id text primary key,
                    timestamp timestamptz not null,
                    actor text not null,
                    action text not null,
                    target text not null,
                    trace_id text not null,
                    ip_address text not null,
                    detail_json jsonb not null
                )
                """
            )
            connection.execute("create index if not exists idx_jobs_status on jobs(status)")
            connection.execute("create index if not exists idx_jobs_owner on jobs(owner)")
            connection.execute("create index if not exists idx_jobs_org_workspace on jobs(organization, workspace)")
            connection.execute("create index if not exists idx_audit_trace on audit_log(trace_id)")
