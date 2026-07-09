# API Surface

Data Analyst Agent exposes a FastAPI control plane for upload, job status, report export, follow-up questions, metrics, audit, and account usage.

OpenAPI is available at:

```text
http://127.0.0.1:8002/docs
```

## Authentication and Scope

Local development can run without a token. In production, set `DATA_ANALYST_AGENT_API_TOKEN` and send one of:

```text
X-API-Token: <token>
Authorization: Bearer <token>
```

Common scope headers:

| Header | Purpose |
| --- | --- |
| `X-Actor` | User or service actor. |
| `X-Role` | `viewer`, `analyst`, or `admin`. |
| `X-Org` | Organization scope. |
| `X-Workspace` | Workspace scope. |

Admin-only or sensitive endpoints require the configured admin actor and role permissions.

## Core Endpoints

| Method | Path | Purpose | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/health` | Runtime health. | Reports store, queue, database, and capacity state. |
| `POST` | `/api/analyze` | Upload CSV/Excel and create an analysis job. | Multipart `dataset`, optional `goal`, `options`, `data_dictionary`, `workspace`. |
| `GET` | `/api/jobs` | List visible jobs. | Scoped by actor, org, workspace, and role. |
| `GET` | `/api/jobs/{job_id}` | Fetch one job. | Owner/admin scoped. |
| `DELETE` | `/api/jobs/{job_id}` | Cancel a running job. | Requires job access. |
| `DELETE` | `/api/jobs` | Cleanup old jobs. | Requires admin-style cleanup permission. |
| `GET` | `/api/reports/{job_id}` | Export a completed report. | `format=md|html|csv|pdf|pptx`. |
| `POST` | `/api/jobs/{job_id}/ask` | Ask a follow-up question. | Requires completed job context. |
| `GET` | `/api/account` | Account usage and plan snapshot. | Useful for SaaS readiness demos. |
| `GET` | `/api/metrics` | JSON metrics. | Requires metrics permission. |
| `GET` | `/api/metrics.prometheus` | Prometheus metrics text. | Requires metrics permission. |
| `GET` | `/api/alerts` | Operational alerts. | Requires metrics permission. |
| `GET` | `/api/audit` | Audit event history. | Requires audit permission. |
| `GET` | `/api/examples/sales.csv` | Built-in sample dataset. | Public demo helper. |

## Upload Contract

`POST /api/analyze`

Required multipart field:

| Field | Type | Description |
| --- | --- | --- |
| `dataset` | file | `.csv`, `.xlsx`, or `.xls`. |

Optional fields:

| Field | Type | Description |
| --- | --- | --- |
| `goal` | string | Analysis goal shown in the report. |
| `options` | JSON string | Analysis depth, delivery mode, scenario, and BI settings. |
| `data_dictionary` | JSON string | Column labels and business meanings. |
| `workspace` | string | Workspace override within the actor scope. |

Response:

```json
{
  "id": "job-id",
  "filename": "sales.csv",
  "goal": "Generate an operating analysis report",
  "status": "queued",
  "owner": "alice"
}
```

## Report Export Contract

`GET /api/reports/{job_id}?format=md`

Supported formats:

| Format | Content-Type | Verification |
| --- | --- | --- |
| `md` | `text/markdown` | FastAPI smoke checks Markdown prefix. |
| `html` | `text/html` | HTML output escapes untrusted markdown text. |
| `csv` | `text/csv` | CSV summary includes insight rows and confidence fields. |
| `pdf` | `application/pdf` | Requires `reportlab` and a Chinese-capable font. |
| `pptx` | `application/vnd.openxmlformats-officedocument.presentationml.presentation` | Requires `python-pptx`. |

Report file paths are constrained to the configured report directory before export.

## Error Semantics

| Status | Meaning |
| --- | --- |
| `400` | Invalid upload, malformed JSON field, or unsupported dataset type. |
| `401` | Missing or invalid API token when token auth is enabled. |
| `403` | Authenticated principal lacks permission or workspace scope. |
| `404` | Job or report file is not visible/available. |
| `409` | Report requested before generation has completed. |
| `413` | Upload exceeds `DATA_ANALYST_AGENT_MAX_UPLOAD_MB`. |
| `422` | Invalid query parameter, such as unsupported report format. |
| `429` | Rate limit or active job quota exceeded. |

## Production Notes

- Set `DATA_ANALYST_AGENT_ENV=prod` before claiming production readiness.
- Use `DATA_ANALYST_AGENT_EXECUTOR_MODE=docker` for Python analysis execution in production.
- Configure PostgreSQL and Redis/RQ for multi-user deployments.
- Run `python -m backend.production_check --require-external` after Docker, PostgreSQL, Redis, and the sandbox image are available.
