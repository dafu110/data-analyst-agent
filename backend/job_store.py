from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


JOB_STATUSES = {"queued", "running", "completed", "failed", "cancelled"}


@dataclass
class JobEvent:
    label: str
    status: str
    detail: str
    timestamp: str = field(default_factory=lambda: utc_now())


@dataclass
class JobRecord:
    id: str
    filename: str
    goal: str
    status: str
    created_at: str
    updated_at: str
    events: list[JobEvent] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    report_path: str | None = None
    owner: str = "local"
    organization: str = "default"
    workspace: str = "default"
    cancelled_at: str | None = None
    duration_ms: float | None = None


class JobStore:
    def __init__(self, root: str | Path) -> None:
        root_path = Path(root)
        if root_path.suffix:
            self.database_path = root_path
        else:
            self.database_path = root_path / "agent.sqlite3"
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def close(self) -> None:
        # Connections are short-lived; this method exists for tests and future pooled stores.
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
            events=[
                JobEvent(
                    label="Queued",
                    status="completed",
                    detail="Dataset accepted and waiting for analysis.",
                    timestamp=now,
                )
            ],
        )
        self.save(record)
        return record

    def get(self, job_id: str) -> JobRecord | None:
        with self._connection() as connection:
            row = connection.execute("select * from jobs where id = ?", (sanitize_id(job_id),)).fetchone()
        return record_from_row(row) if row else None

    def list_jobs(
        self,
        *,
        owner: str | None = None,
        organization: str | None = None,
        workspace: str | None = None,
        limit: int = 50,
    ) -> list[JobRecord]:
        safe_limit = max(1, min(limit, 200))
        clauses: list[str] = []
        params: list[str | int] = []
        if owner is not None:
            clauses.append("owner = ?")
            params.append(owner)
        if organization is not None:
            clauses.append("organization = ?")
            params.append(organization)
        if workspace is not None:
            clauses.append("workspace = ?")
            params.append(workspace)
        where = f" where {' and '.join(clauses)}" if clauses else ""
        params.append(safe_limit)
        with self._connection() as connection:
            rows = connection.execute(
                f"select * from jobs{where} order by created_at desc limit ?",
                tuple(params),
            ).fetchall()
        return [record_from_row(row) for row in rows]

    def metrics(self, *, owner: str | None = None, organization: str | None = None, workspace: str | None = None) -> dict[str, Any]:
        clauses: list[str] = []
        params_list: list[str] = []
        if owner is not None:
            clauses.append("owner = ?")
            params_list.append(owner)
        if organization is not None:
            clauses.append("organization = ?")
            params_list.append(organization)
        if workspace is not None:
            clauses.append("workspace = ?")
            params_list.append(workspace)
        where_clause = f" where {' and '.join(clauses)}" if clauses else ""
        params = tuple(params_list)

        with self._connection() as connection:
            total_row = connection.execute(f"select count(*) as total from jobs{where_clause}", params).fetchone()
            status_rows = connection.execute(
                f"select status, count(*) as total from jobs{where_clause} group by status",
                params,
            ).fetchall()
            error_rows = connection.execute(
                f"select count(*) as total from jobs{where_clause + (' and' if where_clause else ' where')} status = 'failed'",
                params,
            ).fetchone()
            report_rows = connection.execute(
                f"select count(*) as total from jobs{where_clause + (' and' if where_clause else ' where')} report_path is not null",
                params,
            ).fetchone()
            latency_row = connection.execute(
                f"select avg(duration_ms) as avg_duration_ms from jobs{where_clause + (' and' if where_clause else ' where')} duration_ms is not null",
                params,
            ).fetchone()
            duration_rows = connection.execute(
                f"select duration_ms from jobs{where_clause + (' and' if where_clause else ' where')} duration_ms is not null",
                params,
            ).fetchall()

        by_status = {status: 0 for status in sorted(JOB_STATUSES)}
        by_status.update({row["status"]: int(row["total"]) for row in status_rows})
        active = by_status.get("queued", 0) + by_status.get("running", 0)
        durations = [float(row["duration_ms"]) for row in duration_rows]
        return {
            "total_jobs": int(total_row["total"]),
            "active_jobs": active,
            "completed_jobs": by_status.get("completed", 0),
            "failed_jobs": int(error_rows["total"]),
            "generated_reports": int(report_rows["total"]),
            "avg_duration_ms": round(float(latency_row["avg_duration_ms"] or 0), 2),
            "p95_duration_ms": percentile(durations, 95),
            "by_status": by_status,
        }

    def set_running(self, job_id: str, detail: str) -> JobRecord:
        return self.update(job_id, status="running", event=JobEvent("Running", "running", detail))

    def add_event(self, job_id: str, label: str, status: str, detail: str) -> JobRecord:
        return self.update(job_id, event=JobEvent(label, status, detail))

    def complete(self, job_id: str, result: dict[str, Any], report_path: Path) -> JobRecord:
        record = self.get(job_id)
        duration_ms = elapsed_ms(record.created_at) if record else None
        return self.update(
            job_id,
            status="completed",
            result=result,
            error=None,
            report_path=str(report_path),
            duration_ms=duration_ms,
            event=JobEvent("Completed", "completed", "Report generated and stored."),
        )

    def fail(self, job_id: str, error: str) -> JobRecord:
        return self.update(
            job_id,
            status="failed",
            error=error,
            event=JobEvent("Failed", "failed", error),
        )

    def cancel(self, job_id: str, detail: str = "Cancellation requested.") -> JobRecord:
        return self.update(
            job_id,
            status="cancelled",
            cancelled_at=utc_now(),
            event=JobEvent("Cancelled", "cancelled", detail),
        )

    def is_cancelled(self, job_id: str) -> bool:
        record = self.get(job_id)
        return record is not None and record.status == "cancelled"

    def active_count(self) -> int:
        with self._connection() as connection:
            row = connection.execute("select count(*) as total from jobs where status in ('queued', 'running')").fetchone()
        return int(row["total"])

    def active_count_for_actor(self, owner: str, organization: str | None = None) -> int:
        if organization is None:
            with self._connection() as connection:
                row = connection.execute(
                    "select count(*) as total from jobs where owner = ? and status in ('queued', 'running')",
                    (owner,),
                ).fetchone()
        else:
            with self._connection() as connection:
                row = connection.execute(
                    "select count(*) as total from jobs where owner = ? and organization = ? and status in ('queued', 'running')",
                    (owner, organization),
                ).fetchone()
        return int(row["total"])

    def cleanup_terminal_jobs(self, *, older_than_days: int) -> int:
        cutoff = datetime.now(timezone.utc).timestamp() - older_than_days * 24 * 60 * 60
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "select id, updated_at from jobs where status in ('completed', 'failed', 'cancelled')"
            ).fetchall()
            expired_ids = [
                row["id"]
                for row in rows
                if datetime.fromisoformat(row["updated_at"]).timestamp() < cutoff
            ]
            if expired_ids:
                connection.executemany("delete from jobs where id = ?", [(job_id,) for job_id in expired_ids])
                connection.commit()
        return len(expired_ids)

    def add_audit_event(
        self,
        *,
        actor: str,
        action: str,
        target: str,
        trace_id: str,
        ip_address: str,
        detail: dict[str, Any],
        timestamp: str,
    ) -> None:
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                insert into audit_log (id, timestamp, actor, action, target, trace_id, ip_address, detail_json)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    timestamp,
                    actor,
                    action,
                    target,
                    trace_id,
                    ip_address,
                    json.dumps(detail, ensure_ascii=False),
                ),
            )
            connection.commit()

    def list_audit_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "select * from audit_log order by timestamp desc limit ?",
                (limit,),
            ).fetchall()
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

    def update(
        self,
        job_id: str,
        *,
        status: str | None = None,
        event: JobEvent | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        report_path: str | None = None,
        cancelled_at: str | None = None,
        duration_ms: float | None = None,
    ) -> JobRecord:
        with self._lock:
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
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                insert into jobs (
                    id, filename, goal, status, created_at, updated_at, events_json,
                    result_json, error, report_path, owner, organization, workspace, cancelled_at, duration_ms
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("pragma journal_mode=delete")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    def _init_db(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                create table if not exists jobs (
                    id text primary key,
                    filename text not null,
                    goal text not null,
                    status text not null,
                    created_at text not null,
                    updated_at text not null,
                    events_json text not null,
                    result_json text,
                    error text,
                    report_path text,
                    owner text not null default 'local',
                    organization text not null default 'default',
                    workspace text not null default 'default',
                    cancelled_at text,
                    duration_ms real
                )
                """
            )
            ensure_column(connection, "jobs", "duration_ms", "real")
            ensure_column(connection, "jobs", "organization", "text not null default 'default'")
            ensure_column(connection, "jobs", "workspace", "text not null default 'default'")
            connection.execute(
                """
                create table if not exists audit_log (
                    id text primary key,
                    timestamp text not null,
                    actor text not null,
                    action text not null,
                    target text not null,
                    trace_id text not null,
                    ip_address text not null,
                    detail_json text not null
                )
                """
            )
            connection.execute("create index if not exists idx_jobs_status on jobs(status)")
            connection.execute("create index if not exists idx_jobs_owner on jobs(owner)")
            connection.execute("create index if not exists idx_jobs_org_workspace on jobs(organization, workspace)")
            connection.execute("create index if not exists idx_jobs_created_at on jobs(created_at)")
            connection.execute("create index if not exists idx_audit_trace on audit_log(trace_id)")
            connection.commit()


def record_from_row(row: sqlite3.Row) -> JobRecord:
    return record_from_mapping(row)


def record_from_mapping(row) -> JobRecord:
    raw_events = row["events_json"] or []
    events_payload = json.loads(raw_events) if isinstance(raw_events, str) else raw_events
    events = [JobEvent(**event) for event in events_payload]
    raw_result = row["result_json"]
    result = json.loads(raw_result) if isinstance(raw_result, str) and raw_result else raw_result
    return JobRecord(
        id=row["id"],
        filename=row["filename"],
        goal=row["goal"],
        status=row["status"],
        created_at=timestamp_to_iso(row["created_at"]),
        updated_at=timestamp_to_iso(row["updated_at"]),
        events=events,
        result=result,
        error=row["error"],
        report_path=row["report_path"],
        owner=row["owner"],
        organization=row["organization"] if "organization" in row.keys() else "default",
        workspace=row["workspace"] if "workspace" in row.keys() else "default",
        cancelled_at=timestamp_to_iso(row["cancelled_at"]),
        duration_ms=row["duration_ms"] if "duration_ms" in row.keys() else None,
    )


def timestamp_to_iso(value: str | datetime | None) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else value


def job_to_dict(record: JobRecord, *, include_result: bool = True) -> dict[str, Any]:
    payload = asdict(record)
    if not include_result:
        payload["result"] = None
        payload["has_result"] = record.result is not None
        payload["has_report"] = record.report_path is not None
    return payload


def sanitize_id(job_id: str) -> str:
    return "".join(character for character in job_id if character.isalnum() or character in {"-", "_"})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def elapsed_ms(started_at: str) -> float:
    started = datetime.fromisoformat(started_at)
    return round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 2)


def percentile(values: list[float], percent: int) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((percent / 100) * (len(ordered) - 1))))
    return round(float(ordered[index]), 2)


def ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {row["name"] for row in connection.execute(f"pragma table_info({table})").fetchall()}
    if column not in existing:
        connection.execute(f"alter table {table} add column {column} {definition}")
