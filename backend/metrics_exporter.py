from __future__ import annotations

from typing import Any


GAUGE_NAMES = {
    "total_jobs": "data_analyst_agent_jobs_total",
    "active_jobs": "data_analyst_agent_jobs_active",
    "completed_jobs": "data_analyst_agent_jobs_completed_total",
    "failed_jobs": "data_analyst_agent_jobs_failed_total",
    "generated_reports": "data_analyst_agent_reports_generated_total",
    "avg_duration_ms": "data_analyst_agent_job_duration_average_ms",
    "p95_duration_ms": "data_analyst_agent_job_duration_p95_ms",
}


def metrics_to_prometheus(metrics: dict[str, Any]) -> str:
    lines: list[str] = []
    for key, name in GAUGE_NAMES.items():
        value = float(metrics.get(key) or 0)
        lines.append(f"# TYPE {name} gauge")
        lines.append(f"{name} {value}")
    for status, value in sorted((metrics.get("by_status") or {}).items()):
        safe_status = str(status).replace("\\", "\\\\").replace('"', '\\"')
        lines.append("# TYPE data_analyst_agent_jobs_by_status gauge")
        lines.append(f'data_analyst_agent_jobs_by_status{{status="{safe_status}"}} {float(value or 0)}')
    return "\n".join(lines) + "\n"
