from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from backend.authz import Principal


PLAN_ORDER = ("free", "team", "business")


@dataclass(frozen=True)
class PlanPolicy:
    name: str
    monthly_jobs: int
    max_active_jobs: int
    max_upload_mb: int
    features: tuple[str, ...]
    price_per_job_usd: float
    price_per_1k_ms_usd: float


PLAN_POLICIES: dict[str, PlanPolicy] = {
    "free": PlanPolicy(
        name="free",
        monthly_jobs=30,
        max_active_jobs=1,
        max_upload_mb=10,
        features=("csv_excel_upload", "basic_reports", "local_dashboard"),
        price_per_job_usd=0.002,
        price_per_1k_ms_usd=0.00001,
    ),
    "team": PlanPolicy(
        name="team",
        monthly_jobs=500,
        max_active_jobs=3,
        max_upload_mb=50,
        features=("csv_excel_upload", "dashboard_saved_views", "ppt_exports", "audit_log", "team_workspaces"),
        price_per_job_usd=0.004,
        price_per_1k_ms_usd=0.000015,
    ),
    "business": PlanPolicy(
        name="business",
        monthly_jobs=5000,
        max_active_jobs=10,
        max_upload_mb=200,
        features=(
            "csv_excel_upload",
            "dashboard_saved_views",
            "ppt_exports",
            "audit_log",
            "team_workspaces",
            "postgres",
            "redis_rq",
            "docker_sandbox",
            "usage_alerts",
        ),
        price_per_job_usd=0.006,
        price_per_1k_ms_usd=0.00002,
    ),
}


def normalize_plan(value: str | None) -> str:
    plan = (value or "free").strip().lower()
    return plan if plan in PLAN_POLICIES else "free"


def build_account_usage(
    *,
    principal: Principal,
    metrics: dict[str, Any],
    configured_max_active_jobs: int,
    configured_max_upload_bytes: int,
    plan_name: str | None = None,
) -> dict[str, Any]:
    policy = PLAN_POLICIES[normalize_plan(plan_name)]
    completed = int(metrics.get("completed_jobs") or 0)
    total = int(metrics.get("total_jobs") or 0)
    active = int(metrics.get("active_jobs") or 0)
    estimated_cost = estimate_cost_usd(metrics, policy)
    quota_used_ratio = min(1.0, total / max(policy.monthly_jobs, 1))
    return {
        "actor": principal.actor,
        "organization": principal.organization,
        "workspace": principal.workspace,
        "role": principal.effective_role,
        "plan": policy.name,
        "quota": {
            "monthly_jobs": policy.monthly_jobs,
            "used_jobs": total,
            "remaining_jobs": max(policy.monthly_jobs - total, 0),
            "used_ratio": round(quota_used_ratio, 4),
            "max_active_jobs": min(policy.max_active_jobs, configured_max_active_jobs),
            "configured_max_active_jobs": configured_max_active_jobs,
            "max_upload_mb": min(policy.max_upload_mb, round(configured_max_upload_bytes / 1024 / 1024)),
        },
        "usage": {
            "total_jobs": total,
            "completed_jobs": completed,
            "active_jobs": active,
            "failed_jobs": int(metrics.get("failed_jobs") or 0),
            "generated_reports": int(metrics.get("generated_reports") or 0),
            "avg_duration_ms": float(metrics.get("avg_duration_ms") or 0),
            "p95_duration_ms": float(metrics.get("p95_duration_ms") or 0),
            "estimated_cost_usd": estimated_cost,
        },
        "features": list(policy.features),
        "policy": asdict(policy),
    }


def estimate_cost_usd(metrics: dict[str, Any], policy: PlanPolicy | None = None) -> float:
    policy = policy or PLAN_POLICIES["free"]
    completed = int(metrics.get("completed_jobs") or 0)
    avg_duration = float(metrics.get("avg_duration_ms") or 0)
    duration_cost = (completed * avg_duration / 1000) * policy.price_per_1k_ms_usd
    job_cost = completed * policy.price_per_job_usd
    return round(job_cost + duration_cost, 4)


def usage_summary_for_metrics(metrics: dict[str, Any], plan_name: str | None = None) -> dict[str, float | int | str]:
    policy = PLAN_POLICIES[normalize_plan(plan_name)]
    return {
        "plan": policy.name,
        "estimated_cost_usd": estimate_cost_usd(metrics, policy),
        "monthly_job_quota": policy.monthly_jobs,
        "quota_used_ratio": round((int(metrics.get("total_jobs") or 0) / max(policy.monthly_jobs, 1)), 4),
    }
