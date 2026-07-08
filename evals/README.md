# Agent Evals

Run deterministic regression evals:

```powershell
python -m evals.run_evals
```

The suite checks:

- required plan steps
- allowed tool usage
- report content
- chart spec generation
- semantic role coverage
- structured insights with evidence
- quality score and trace-span budgets
- risk-tag pass/fail summaries
- latency capture

Current cases cover sales happy path, data quality, monthly trends, customer operations, marketing funnel efficiency, and subscription retention risk.

Results are written to `evals/last_results.json`.
