# Launch Hardening Checklist

## Blocking Gates

- `DATA_ANALYST_AGENT_ENV=prod` must require a strong API token.
- `DATA_ANALYST_AGENT_EXECUTOR_MODE=docker` must be set for production.
- PostgreSQL and Redis/RQ should be configured for multi-user deployments.
- Docker sandbox image `data-analyst-agent-sandbox:latest` must be built and smoke-tested.
- Generated `reports/`, `uploads/`, local databases, and virtual environments must stay out of Git.

## Recommended Pre-Launch Commands

```powershell
python -m compileall data_analyst_agent backend evals
node --check frontend\app.js
node --check frontend\labels.js
node --check frontend\charts.js
python -m unittest discover -s tests
python -m evals.run_evals
python -m backend.production_check
```

Use the external gate before claiming production readiness:

```powershell
python -m backend.production_check --require-external
```

## Current Local Verification

The following checks were run on 2026-07-09 from this working tree:

```text
python -m compileall data_analyst_agent backend evals scripts: passed
node --check frontend\app.js: passed
node --check frontend\labels.js: passed
node --check frontend\charts.js: passed
python -m unittest discover -s tests: 74 tests passed
FastAPI smoke export coverage: Markdown, HTML, CSV, PDF, and PPTX passed
python -m evals.run_evals: 6/6 eval cases passed
python -m backend.production_check: local dependency/configuration checks passed
```

Docker daemon access was not available in this local session, so the external
`--require-external` sandbox smoke must still be run before claiming Docker,
PostgreSQL, and Redis/RQ production readiness.

## Portfolio Polish

- Split very large browser and server files when adding new UI or API features.
- Keep screenshot `docs/assets/data-analyst-agent-workbench.png` current.
- Add release notes that state whether Docker, PostgreSQL, and Redis were actually verified.
