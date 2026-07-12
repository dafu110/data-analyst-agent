# Tool Agent Specification

## 1. Goal and Scope

The Sales Operations Agent turns a CSV or Excel sales export into a reviewed operating brief. It reads data, proposes a bounded SQL/Python plan, executes approved analysis, and returns evidence-linked conclusions and human-owned actions.

It never changes source data, prices, budgets, campaigns, CRM records, or external systems.

## 2. Tools and Permissions

| Tool | Purpose | Reversible | Gate |
| --- | --- | --- | --- |
| Dataset loader | Read CSV/Excel into an in-memory frame | Yes | File type, size, empty-table, and input-safety validation |
| SQL runner | Read-only query against an in-memory SQLite table | Yes | Single `SELECT` validation |
| Python runner | Bounded dataframe analysis | Yes | Approved plan plus AST validation; Docker isolation in production |
| Report exporter | Produce Markdown/HTML/CSV/PDF/PPTX | Yes | Export-readiness review |

## 3. Control Loop

1. Preflight data and issue a fingerprinted contract.
2. Generate a structured plan containing objectives, tools, risks, and outputs.
3. Require user approval of the signed plan.
4. Execute only approved, allow-listed steps.
5. Verify output usability; a fixed fallback may run only when approved steps yield no usable signal.
6. Stop after the approved plan and at most one bounded fallback; never invent additional actions.

## 4. Guardrails and Approval

- Block imports, file I/O, `eval`, `exec`, dangerous attributes, and export methods in generated Python.
- Allow only read-only SQL against the in-memory `data` table.
- Reject oversized and empty uploads; flag formula-like cells and sensitive columns.
- Docker execution uses no network, a read-only root filesystem, dropped capabilities, CPU/memory/PID limits, and a timeout.
- Business actions are recommendations only and always require human confirmation.

## 5. Memory and State

The job keeps the reviewed plan, file fingerprint, input-safety findings, trace, tool results, report, and export metadata. Preflight contracts expire after 15 minutes and are scoped to actor, organization, and workspace.

## 6. Escalation

Stop and request review when a required business field is missing, quality gates fail, confidence is low, an input-safety risk is found, a plan fails validation, or a tool times out.

## 7. Evaluation

Success requires a completed report with source-step evidence, quality gates, and action ownership. Safety evaluation covers formula-like CSV values, sensitive columns, empty tables, unsafe SQL prompts, blocked imports, oversized uploads, and Docker execution controls.

## 8. Failure Handling

Invalid input is rejected before planning. Tool failures are recorded in the trace and job error. The system does not retry arbitrary generated code or make external changes after a failure.
