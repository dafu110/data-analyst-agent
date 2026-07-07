from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.job_store import JobStore, utc_now


@dataclass(frozen=True)
class AuditContext:
    actor: str
    ip_address: str
    trace_id: str


def audit(store: JobStore, context: AuditContext, action: str, target: str, detail: dict[str, Any] | None = None) -> None:
    store.add_audit_event(
        actor=context.actor,
        action=action,
        target=target,
        trace_id=context.trace_id,
        ip_address=context.ip_address,
        detail=detail or {},
        timestamp=utc_now(),
    )
