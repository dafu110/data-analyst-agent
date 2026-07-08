from __future__ import annotations

from typing import Any

try:
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover
    BaseModel = object  # type: ignore[misc,assignment]
    Field = None  # type: ignore[assignment]


if Field is not None:

    class ErrorResponse(BaseModel):
        detail: str


    class HealthResponse(BaseModel):
        status: str
        env: str
        database: str
        queue: str
        executor_mode: str
        active_jobs: int
        max_concurrent_jobs: int


    class JobEventResponse(BaseModel):
        label: str
        status: str
        detail: str
        timestamp: str


    class JobResponse(BaseModel):
        id: str
        filename: str
        goal: str
        status: str
        created_at: str
        updated_at: str
        events: list[JobEventResponse] = Field(default_factory=list)
        result: dict[str, Any] | None = None
        error: str | None = None
        report_path: str | None = None
        owner: str = "local"
        organization: str = "default"
        workspace: str = "default"
        cancelled_at: str | None = None
        duration_ms: float | None = None
        has_result: bool | None = None
        has_report: bool | None = None


    class JobListResponse(BaseModel):
        jobs: list[JobResponse]


    class MetricsResponse(BaseModel):
        total_jobs: int
        active_jobs: int
        completed_jobs: int
        failed_jobs: int
        generated_reports: int
        avg_duration_ms: float
        p95_duration_ms: float = 0
        estimated_cost_usd: float = 0
        monthly_job_quota: int | None = None
        quota_used_ratio: float | None = None
        by_status: dict[str, int]
        scope: str | None = None
        queue: str | None = None


    class AccountUsageResponse(BaseModel):
        actor: str
        organization: str
        workspace: str
        role: str
        plan: str
        quota: dict[str, Any]
        usage: dict[str, Any]
        features: list[str]
        policy: dict[str, Any]


    class AlertItemResponse(BaseModel):
        key: str
        severity: str
        title: str
        detail: str
        recommendation: str
        value: float | int
        threshold: float | int


    class AlertsResponse(BaseModel):
        status: str
        severity: str
        alerts: list[AlertItemResponse]
        summary: dict[str, Any]


    class AuditEventResponse(BaseModel):
        id: str
        timestamp: str
        actor: str
        action: str
        target: str
        trace_id: str
        ip_address: str
        detail: dict[str, Any]


    class AuditLogResponse(BaseModel):
        events: list[AuditEventResponse]


    class CleanupResponse(BaseModel):
        deleted_jobs: int
        older_than_days: int


    class FollowupResponse(BaseModel):
        question: str
        answer: str
        citations: list[str] = Field(default_factory=list)
        confidence: float


    class FollowupRequest(BaseModel):
        question: str = Field(min_length=1, max_length=1000)

else:
    ErrorResponse = HealthResponse = JobResponse = JobListResponse = MetricsResponse = AccountUsageResponse = AlertsResponse = AuditLogResponse = CleanupResponse = FollowupResponse = FollowupRequest = None
