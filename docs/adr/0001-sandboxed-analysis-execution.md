# ADR 0001: Sandboxed Analysis Execution

## Status

Accepted.

## Context

The Data Analyst Agent can run generated or planned analysis steps over user-supplied CSV and Excel data. Those steps may use SQL or Python. In local development, the project supports an in-process guarded Python runner for fast iteration. In production, the same capability crosses a high-risk boundary because user data and model-planned code can interact with the host runtime.

## Decision

Production deployments must use `DATA_ANALYST_AGENT_EXECUTOR_MODE=docker` and the `data-analyst-agent-sandbox:latest` image. The Docker path keeps network disabled, drops Linux capabilities, sets memory and CPU limits, uses a read-only container filesystem, and still applies AST-level guardrails before execution.

## Consequences

- Production startup must fail when Docker executor mode is missing.
- The in-process executor is retained only for local demos and tests.
- Release verification must include a Docker sandbox smoke test.
- Any new Python analysis feature must pass through the same plan validation and sandbox boundary.

## Verification

```powershell
python -m unittest tests.test_security_controls tests.test_plan_validator
python -m backend.production_check --require-external
```
