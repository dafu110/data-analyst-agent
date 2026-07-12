# Sales Review Demo

## Goal

Demonstrate that the Agent produces a reviewable sales decision, not unchecked generated code.

## Flow

1. Start the API with `DATA_ANALYST_AGENT_EXECUTOR_MODE=docker` and a built `data-analyst-agent-sandbox:latest` image.
2. Upload `examples/sales.csv` in the workbench.
3. Confirm the preflight: schema, quality gates, semantic roles, file fingerprint, and input-safety findings.
4. Review the generated plan. It lists objectives, data scope, SQL/Python steps, risks, and expected outputs before execution.
5. Approve the plan. The API validates actor, workspace, goal, file fingerprint, expiry, and the signed approval contract.
6. Review the decision brief, data-quality gates, action owner/deadline/impact, and security execution evidence.
7. Open Analysis Details for the approved plan, trace, bounded tool output, and the source steps behind every conclusion.
8. Export the Markdown report. It includes evidence, calculation steps, limitations, action ownership, and execution isolation controls.

## Acceptance Evidence

- Docker evidence reports network disabled, read-only root filesystem, dropped capabilities, CPU/memory/PID limits, and timeout.
- Local runs are labelled `guarded_python`; they are not presented as Docker-isolated runs.
- Formula-like spreadsheet cells and sensitive columns are recorded in the preflight; sensitive preview samples are redacted.
- Empty datasets are rejected before planning.
- Goals attempting SQL injection or unsafe execution do not alter the allow-listed SQL/Python plan.
