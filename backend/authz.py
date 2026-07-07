from __future__ import annotations

import hmac
import re
from dataclasses import dataclass
from typing import Protocol


ROLE_PERMISSIONS = {
    "viewer": {"job.read", "job.list", "report.read", "metrics.read"},
    "analyst": {"job.create", "job.read", "job.list", "job.cancel", "report.read", "metrics.read"},
    "admin": {"job.create", "job.read", "job.list", "job.cancel", "job.cleanup", "report.read", "metrics.read", "audit.read"},
}
IDENTITY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@:-]{0,63}$")


@dataclass(frozen=True)
class Principal:
    actor: str
    role: str
    organization: str = "default"
    workspace: str = "default"
    is_admin_actor: bool = False

    @property
    def effective_role(self) -> str:
        if self.is_admin_actor:
            return "admin"
        if self.role == "admin":
            return "viewer"
        return self.role if self.role in ROLE_PERMISSIONS else "viewer"


def has_permission(principal: Principal, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(principal.effective_role, set())


class ScopedJob(Protocol):
    owner: str
    organization: str
    workspace: str


def token_is_valid(expected_token: str | None, token: str | None, authorization: str | None = None) -> bool:
    if expected_token is None:
        return True
    candidate = token or ""
    if not candidate and authorization:
        candidate = authorization.removeprefix("Bearer ").strip()
    return hmac.compare_digest(candidate, expected_token)


def can_access_job_scope(principal: Principal, job: ScopedJob) -> bool:
    if principal.effective_role == "admin":
        return True
    return (
        job.owner == principal.actor
        and job.organization == principal.organization
        and job.workspace == principal.workspace
    )


def normalize_principal_value(value: str | None, default: str = "default", *, strict: bool = False) -> str:
    normalized = (value or default).strip() or default
    if IDENTITY_PATTERN.fullmatch(normalized):
        return normalized
    if strict:
        raise ValueError("identity values must be 1-64 characters and use letters, numbers, dot, underscore, at, colon, or dash.")
    return default


def normalize_workspace(value: str | None, default: str = "default", *, strict: bool = False) -> str:
    return normalize_principal_value(value, default, strict=strict)
