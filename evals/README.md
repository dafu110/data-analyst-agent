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
- latency capture

Results are written to `evals/last_results.json`.
