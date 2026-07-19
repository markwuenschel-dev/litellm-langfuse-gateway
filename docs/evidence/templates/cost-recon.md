# Template: cost reconciliation (human narrative)

**Not machine input.** The engine reads a **YAML run file** only. Use this Markdown as an optional companion for interpretation, anomalies, and remediation after:

```bash
uv run llg reconcile-cost --run-file path/to/run.yaml
# optional: --json
```

```yaml
# Companion metadata (copy from the YAML run)
run_id: ""
date: ""
yaml_run_file: ""
currency: USD
tolerance: "relative 0.05 / absolute 0.01 (DOC′)"
cli_exit_code: 0|1|2
result: within|outside|incomplete|unproven
```

## Table (from CLI pair reports)

| Alias / group | comparison_scope_id | Provider $ | LiteLLM $ | Langfuse $ | All pairs within? |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

## Pair diagnostics

| Group | Pair | Diff | Limit | Within? |
| --- | --- | --- | --- | --- |
| | provider↔litellm | | | |
| | litellm↔langfuse | | | |
| | provider↔langfuse | | | |

## Known deltas / anomalies

-

## Evidence retained (immutable)

| Role | source_id | evidence_ref | collected_at |
| --- | --- | --- | --- |
| provider | | | |
| litellm | | | |
| langfuse | | | |

## Remediation

-
