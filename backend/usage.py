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


@dataclass(frozen=True)
class AlertThresholds:
    warning_failure_rate: float = 0.03
    critical_failure_rate: float = 0.05
    warning_quota_ratio: float = 0.8
    critical_quota_ratio: float = 0.95
    warning_p95_ms: float = 30_000
    critical_p95_ms: float = 60_000
    warning_cost_usd: float = 10
    critical_cost_usd: float = 25


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


def build_usage_alerts(metrics: dict[str, Any], plan_name: str | None = None, thresholds: AlertThresholds | None = None) -> dict[str, Any]:
    thresholds = thresholds or AlertThresholds()
    summary = usage_summary_for_metrics(metrics, plan_name)
    total_jobs = int(metrics.get("total_jobs") or 0)
    failed_jobs = int(metrics.get("failed_jobs") or 0)
    active_jobs = int(metrics.get("active_jobs") or 0)
    completed_jobs = int(metrics.get("completed_jobs") or 0)
    p95_duration_ms = float(metrics.get("p95_duration_ms") or 0)
    max_active_jobs = int(metrics.get("max_concurrent_jobs") or metrics.get("max_active_jobs") or 0)
    estimated_cost = float(summary["estimated_cost_usd"])
    quota_ratio = float(summary["quota_used_ratio"])
    failure_rate = failed_jobs / max(total_jobs, 1)
    alerts: list[dict[str, Any]] = []

    add_threshold_alert(
        alerts,
        key="failure_rate",
        value=failure_rate,
        warning=thresholds.warning_failure_rate,
        critical=thresholds.critical_failure_rate,
        title="失败率偏高",
        detail=f"{failed_jobs}/{total_jobs} 个任务失败。",
        recommendation="检查最近失败任务、数据格式、权限配置和执行日志。",
    )
    add_threshold_alert(
        alerts,
        key="quota_usage",
        value=quota_ratio,
        warning=thresholds.warning_quota_ratio,
        critical=thresholds.critical_quota_ratio,
        title="额度接近上限",
        detail=f"当前套餐 {summary['plan']} 已使用 {quota_ratio:.0%} 月度任务额度。",
        recommendation="清理无效任务、升级套餐或提高月度配额。",
    )
    add_threshold_alert(
        alerts,
        key="p95_latency",
        value=p95_duration_ms,
        warning=thresholds.warning_p95_ms,
        critical=thresholds.critical_p95_ms,
        title="P95 延迟偏高",
        detail=f"P95 耗时 {p95_duration_ms:.0f} ms。",
        recommendation="检查队列积压、数据规模、worker 容量和沙箱启动耗时。",
    )
    add_threshold_alert(
        alerts,
        key="estimated_cost",
        value=estimated_cost,
        warning=thresholds.warning_cost_usd,
        critical=thresholds.critical_cost_usd,
        title="估算成本偏高",
        detail=f"当前范围估算成本 ${estimated_cost:.4f}。",
        recommendation="按组织/工作区复盘高频任务，限制重复分析或配置预算告警。",
    )
    if max_active_jobs and active_jobs >= max_active_jobs:
        alerts.append(
            {
                "key": "capacity",
                "severity": "critical",
                "title": "执行容量已满",
                "detail": f"{active_jobs}/{max_active_jobs} 个并发槽位正在使用。",
                "recommendation": "扩容 worker 或等待当前任务完成后再提交。",
                "value": active_jobs,
                "threshold": max_active_jobs,
            }
        )

    severity = summarize_alert_severity(alerts)
    return {
        "status": "ok" if severity == "ok" else "needs_attention",
        "severity": severity,
        "alerts": alerts,
        "summary": {
            "plan": summary["plan"],
            "total_jobs": total_jobs,
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "active_jobs": active_jobs,
            "failure_rate": round(failure_rate, 4),
            "quota_used_ratio": quota_ratio,
            "p95_duration_ms": p95_duration_ms,
            "estimated_cost_usd": estimated_cost,
        },
    }


def add_threshold_alert(
    alerts: list[dict[str, Any]],
    *,
    key: str,
    value: float,
    warning: float,
    critical: float,
    title: str,
    detail: str,
    recommendation: str,
) -> None:
    if value >= critical:
        severity = "critical"
        threshold = critical
    elif value >= warning:
        severity = "warning"
        threshold = warning
    else:
        return
    alerts.append(
        {
            "key": key,
            "severity": severity,
            "title": title,
            "detail": detail,
            "recommendation": recommendation,
            "value": round(value, 4),
            "threshold": threshold,
        }
    )


def summarize_alert_severity(alerts: list[dict[str, Any]]) -> str:
    severities = {alert.get("severity") for alert in alerts}
    if "critical" in severities:
        return "critical"
    if "warning" in severities:
        return "warning"
    return "ok"
