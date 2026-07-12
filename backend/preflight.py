from __future__ import annotations

import base64
import hashlib
import hmac
import json
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from data_analyst_agent.business import build_analysis_context, build_quality_gates
from data_analyst_agent.data_safety import InputSafetyFinding, redact_samples, scan_dataframe, sensitive_columns
from data_analyst_agent.datasets import load_dataset_bundle
from data_analyst_agent.guardrails import GuardrailPolicy
from data_analyst_agent.models import AnalysisPlan, DatasetProfile, SemanticRole, TableRelationship, TableSummary
from data_analyst_agent.options import AnalysisOptions, parse_analysis_options
from data_analyst_agent.plan_validator import step_from_dict
from data_analyst_agent.planner import Planner
from data_analyst_agent.profiler import profile_dataframe
from data_analyst_agent.relationships import infer_table_relationships, summarize_tables
from data_analyst_agent.semantics import infer_semantic_roles
from data_analyst_agent.serialization import to_jsonable


PREFLIGHT_TTL_SECONDS = 15 * 60


@dataclass
class PreflightRecord:
    id: str
    fingerprint: str
    filename: str
    size_bytes: int
    owner: str
    organization: str
    workspace: str
    profile: DatasetProfile
    semantic_roles: list[SemanticRole]
    table_summaries: list[Any]
    table_relationships: list[Any]
    column_samples: dict[str, list[str]]
    security_findings: list[InputSafetyFinding]
    created_at: float
    expires_at: float
    plans: dict[str, AnalysisPlan] = field(default_factory=dict)


class PreflightRegistry:
    """Short-lived, scoped preflight state used to bind approval to execution."""

    def __init__(self, ttl_seconds: int = PREFLIGHT_TTL_SECONDS, redis_url: str | None = None, redis_client: Any | None = None) -> None:
        self.ttl_seconds = ttl_seconds
        self._records: dict[str, PreflightRecord] = {}
        self._lock = threading.RLock()
        self._redis = redis_client if redis_client is not None else _build_redis_client(redis_url)

    def create(self, *, filename: str, content: bytes, owner: str, organization: str, workspace: str) -> PreflightRecord:
        profile, semantic_roles, table_summaries, table_relationships, samples, security_findings = inspect_dataset(filename, content)
        now = time.time()
        record = PreflightRecord(
            id=uuid.uuid4().hex,
            fingerprint=hashlib.sha256(content).hexdigest(),
            filename=filename,
            size_bytes=len(content),
            owner=owner,
            organization=organization,
            workspace=workspace,
            profile=profile,
            semantic_roles=semantic_roles,
            table_summaries=table_summaries,
            table_relationships=table_relationships,
            column_samples=samples,
            security_findings=security_findings,
            created_at=now,
            expires_at=now + self.ttl_seconds,
        )
        with self._lock:
            self._remove_expired_locked(now)
            self._records[record.id] = record
        self._save(record)
        return record

    def get(self, preflight_id: str, *, owner: str, organization: str, workspace: str) -> PreflightRecord | None:
        with self._lock:
            self._remove_expired_locked(time.time())
            record = self._records.get(preflight_id)
        if record is None and self._redis is not None:
            record = self._load(preflight_id)
        if record is None:
            return None
        if (record.owner, record.organization, record.workspace) != (owner, organization, workspace):
            return None
        return record

    def create_plan(self, record: PreflightRecord, *, goal: str, data_dictionary: dict[str, str]) -> tuple[str, AnalysisPlan]:
        semantic_roles = infer_semantic_roles(record.profile, data_dictionary=data_dictionary)
        plan = Planner().create_plan(goal, record.profile, semantic_roles=semantic_roles)
        plan_id = uuid.uuid4().hex
        with self._lock:
            record.semantic_roles = semantic_roles
            record.plans[plan_id] = plan
        self._save(record)
        return plan_id, plan

    def get_plan(self, record: PreflightRecord, plan_id: str) -> AnalysisPlan | None:
        with self._lock:
            return record.plans.get(plan_id)

    def _save(self, record: PreflightRecord) -> None:
        if self._redis is None:
            return
        ttl = max(1, int(record.expires_at - time.time()))
        self._redis.setex(_redis_key(record.id), ttl, json.dumps(_record_to_dict(record), ensure_ascii=False, separators=(",", ":")))

    def _load(self, preflight_id: str) -> PreflightRecord | None:
        raw = self._redis.get(_redis_key(preflight_id))
        if not raw:
            return None
        try:
            return _record_from_dict(json.loads(raw))
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    def _remove_expired_locked(self, now: float) -> None:
        expired = [key for key, record in self._records.items() if record.expires_at <= now]
        for key in expired:
            self._records.pop(key, None)


def inspect_dataset(filename: str, content: bytes) -> tuple[DatasetProfile, list[SemanticRole], list[Any], list[Any], dict[str, list[str]], list[InputSafetyFinding]]:
    suffix = Path(filename).suffix or ".csv"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(content)
        temporary_path = Path(handle.name)
    try:
        dataset = load_dataset_bundle(temporary_path)
        if dataset.primary.empty:
            raise ValueError("数据表为空，无法生成分析计划。")
        profile = profile_dataframe(dataset.primary, filename, GuardrailPolicy())
        semantic_roles = infer_semantic_roles(profile)
        table_summaries = summarize_tables(dataset.tables)
        table_relationships = infer_table_relationships(dataset.tables) if len(dataset.tables) > 1 else []
        findings = scan_dataframe(dataset.primary)
        return profile, semantic_roles, table_summaries, table_relationships, redact_samples(dataset.primary, sensitive_columns(dataset.primary)), findings
    finally:
        temporary_path.unlink(missing_ok=True)


def build_column_samples(df: pd.DataFrame, limit: int = 3) -> dict[str, list[str]]:
    samples: dict[str, list[str]] = {}
    for column in df.columns:
        values = df[column].dropna().head(limit).tolist()
        samples[str(column)] = [str(value) for value in values]
    return samples


def preflight_to_dict(record: PreflightRecord) -> dict[str, Any]:
    roles = {role.column: role for role in record.semantic_roles}
    columns = []
    for name in record.profile.column_names:
        role = roles.get(name)
        missing = int(record.profile.missing_values.get(name, 0))
        columns.append(
            {
                "name": name,
                "dtype": record.profile.dtypes.get(name, "unknown"),
                "samples": record.column_samples.get(name, []),
                "missing_count": missing,
                "missing_ratio": round(missing / max(record.profile.rows, 1), 4),
                "suggested_role": role.role if role else None,
                "confidence": role.confidence if role else 0.0,
                "reason": role.reason if role else "No semantic role matched automatically.",
                "needs_review": role is None or role.confidence < 0.9,
            }
        )
    context = build_analysis_context("", options=None)
    quality_gates = build_quality_gates(record.profile, record.semantic_roles, context)
    return {
        "id": record.id,
        "fingerprint": record.fingerprint,
        "filename": record.filename,
        "size_bytes": record.size_bytes,
        "expires_at": record.expires_at,
        "profile": to_jsonable(record.profile),
        "columns": columns,
        "semantic_roles": to_jsonable(record.semantic_roles),
        "quality_gates": to_jsonable(quality_gates),
        "table_summaries": to_jsonable(record.table_summaries),
        "table_relationships": to_jsonable(record.table_relationships),
        "security_findings": to_jsonable(record.security_findings),
        "review_required": any(column["needs_review"] for column in columns) or any(gate.status != "pass" for gate in quality_gates) or bool(record.security_findings),
    }


def plan_to_dict(plan: AnalysisPlan) -> dict[str, Any]:
    return to_jsonable(plan)


def analysis_plan_from_dict(payload: dict[str, Any]) -> AnalysisPlan:
    """Restore a server-signed plan; the agent validates it against the loaded dataset before use."""
    if not isinstance(payload, dict):
        raise ValueError("Approved plan payload is invalid.")
    goal = str(payload.get("user_goal") or "").strip()
    steps = payload.get("steps")
    if not goal or not isinstance(steps, list) or not steps:
        raise ValueError("Approved plan payload is incomplete.")
    return AnalysisPlan(user_goal=goal, steps=[step_from_dict(step) for step in steps])


def create_execution_contract(
    record: PreflightRecord,
    plan_id: str,
    plan: AnalysisPlan,
    *,
    data_dictionary: dict[str, str],
    analysis_options: AnalysisOptions | dict[str, object] | None,
    signing_secret: str,
) -> str:
    """Create a portable, short-lived approval contract for web and worker processes."""
    payload = {
        "preflight_id": record.id,
        "plan_id": plan_id,
        "fingerprint": record.fingerprint,
        "owner": record.owner,
        "organization": record.organization,
        "workspace": record.workspace,
        "goal": plan.user_goal.strip(),
        "expires_at": record.expires_at,
        "plan": plan_to_dict(plan),
        "data_dictionary": normalize_data_dictionary(data_dictionary),
        "analysis_options": normalize_analysis_options(analysis_options).to_dict(),
        "security_findings": to_jsonable(record.security_findings),
    }
    encoded = _encode_contract_payload(payload)
    signature = hmac.new(signing_secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def verify_execution_contract(
    contract: str,
    *,
    signing_secret: str,
    owner: str,
    organization: str,
    workspace: str,
    fingerprint: str,
    goal: str,
    data_dictionary: dict[str, str],
    analysis_options: AnalysisOptions | dict[str, object] | None,
) -> dict[str, Any]:
    """Verify an approval contract without relying on process-local preflight state."""
    encoded, separator, supplied_signature = str(contract or "").partition(".")
    expected_signature = hmac.new(signing_secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).hexdigest()
    if not separator or not hmac.compare_digest(supplied_signature, expected_signature):
        raise ValueError("Preflight approval contract is invalid.")
    try:
        payload = json.loads(_decode_contract_payload(encoded))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Preflight approval contract cannot be read.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("plan"), dict) or not isinstance(payload.get("data_dictionary"), dict) or not isinstance(payload.get("analysis_options"), dict):
        raise ValueError("Preflight approval contract is incomplete.")
    if float(payload.get("expires_at", 0)) <= time.time():
        raise ValueError("Preflight approval contract has expired.")
    expected_scope = (owner, organization, workspace)
    contract_scope = (payload.get("owner"), payload.get("organization"), payload.get("workspace"))
    if contract_scope != expected_scope:
        raise ValueError("Preflight approval contract is outside the current workspace.")
    if payload.get("fingerprint") != fingerprint:
        raise ValueError("The uploaded file does not match the reviewed dataset.")
    if payload.get("goal") != goal.strip():
        raise ValueError("Analysis goal changed after plan approval. Regenerate the plan.")
    if payload["data_dictionary"] != normalize_data_dictionary(data_dictionary):
        raise ValueError("Data dictionary changed after plan approval. Regenerate the plan.")
    if payload["analysis_options"] != normalize_analysis_options(analysis_options).to_dict():
        raise ValueError("Analysis options changed after plan approval. Regenerate the plan.")
    return payload


def normalize_data_dictionary(data_dictionary: dict[str, str] | None) -> dict[str, str]:
    if not isinstance(data_dictionary, dict):
        raise ValueError("Data dictionary must be an object.")
    return {str(key).strip(): str(value).strip() for key, value in sorted(data_dictionary.items()) if str(key).strip() and str(value).strip()}


def normalize_analysis_options(analysis_options: AnalysisOptions | dict[str, object] | None) -> AnalysisOptions:
    return analysis_options if isinstance(analysis_options, AnalysisOptions) else parse_analysis_options(analysis_options)


def _build_redis_client(redis_url: str | None):
    if not redis_url:
        return None
    try:
        from redis import Redis
    except ImportError as exc:  # pragma: no cover - configuration dependency
        raise RuntimeError("Redis-backed preflights require the redis package.") from exc
    return Redis.from_url(redis_url, decode_responses=True)


def _redis_key(preflight_id: str) -> str:
    return f"data-analyst-agent:preflight:{preflight_id}"


def _record_to_dict(record: PreflightRecord) -> dict[str, Any]:
    return {
        "id": record.id, "fingerprint": record.fingerprint, "filename": record.filename, "size_bytes": record.size_bytes,
        "owner": record.owner, "organization": record.organization, "workspace": record.workspace,
        "profile": to_jsonable(record.profile), "semantic_roles": to_jsonable(record.semantic_roles),
        "table_summaries": to_jsonable(record.table_summaries), "table_relationships": to_jsonable(record.table_relationships),
        "column_samples": record.column_samples, "security_findings": to_jsonable(record.security_findings),
        "created_at": record.created_at, "expires_at": record.expires_at,
        "plans": {plan_id: plan_to_dict(plan) for plan_id, plan in record.plans.items()},
    }


def _record_from_dict(payload: dict[str, Any]) -> PreflightRecord:
    profile = dict(payload["profile"])
    profile["path"] = Path(profile["path"])
    return PreflightRecord(
        id=str(payload["id"]), fingerprint=str(payload["fingerprint"]), filename=str(payload["filename"]), size_bytes=int(payload["size_bytes"]),
        owner=str(payload["owner"]), organization=str(payload["organization"]), workspace=str(payload["workspace"]),
        profile=DatasetProfile(**profile), semantic_roles=[SemanticRole(**item) for item in payload["semantic_roles"]],
        table_summaries=[TableSummary(**item) for item in payload["table_summaries"]], table_relationships=[TableRelationship(**item) for item in payload["table_relationships"]],
        column_samples={str(key): [str(value) for value in values] for key, values in payload["column_samples"].items()},
        security_findings=[InputSafetyFinding(**item) for item in payload["security_findings"]], created_at=float(payload["created_at"]), expires_at=float(payload["expires_at"]),
        plans={str(plan_id): analysis_plan_from_dict(plan) for plan_id, plan in payload.get("plans", {}).items()},
    )


def _encode_contract_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_contract_payload(encoded: str) -> str:
    padded = encoded + "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
