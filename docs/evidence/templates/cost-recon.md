# Template: cost reconciliation

```yaml
run_id: ""
date: ""
aliases: []
n_calls_per_alias: 0
tolerance: "±5% or ±$0.01 (larger)"
result: pass|fail|unproven
```

## Table

| Alias | Provider $ | LiteLLM $ | Langfuse $ | Δ max | Within tol? |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

## Known deltas

-

## Command

```bash
uv run llg reconcile-cost --run-id <run_id>
# Then fill this file from dashboards/APIs — CLI does not invent numbers.
```
