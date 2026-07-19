# Evidence index

Runtime and hermetic proof for the LiteLLM + Langfuse gateway milestone.

**Rule:** Config + docs alone are not verification. Live provider smokes, Langfuse correlation, cost recon, Postgres outage, and similar items stay **UNPROVEN** until run with credentials and `LLG_LIVE=1` (or equivalent), with redacted artifacts linked here.

## What may be committed

| Allowed | Forbidden |
| --- | --- |
| Redacted JSON (IDs, token counts, status) | Provider keys, master/salt, virtual keys |
| Pass/fail matrices with timestamps | Full prompts containing PII |
| Curl exit codes / health snippets | Authorization headers |
| Spend totals without account numbers | Raw `.env` dumps |

## Templates

| Template | Use |
| --- | --- |
| [`templates/provider-smoke.md`](./templates/provider-smoke.md) | Per-alias live chat smoke |
| [`templates/langfuse-correlation.md`](./templates/langfuse-correlation.md) | App trace ↔ LiteLLM generation |
| [`templates/cost-recon.md`](./templates/cost-recon.md) | Provider vs LiteLLM vs Langfuse |
| [`templates/failure-run.md`](./templates/failure-run.md) | Outage / ACL / budget live runs |

## Pin-compatibility spikes (Docker, not `LLG_LIVE`)

| Spike | Harness | Claim status |
| --- | --- | --- |
| INT-001 Redis control-state | `tests/runtime_pin/` (`LLG_PIN_SPIKE=1`) | **Claim-neutral** until green evidence → product PR; see [`spikes/2026-07-19-int-001-redis-pin-compat.md`](./spikes/2026-07-19-int-001-redis-pin-compat.md) |

## Unproven without `LLG_LIVE` / credentials (matrix)

| Capability | Hermetic (CI) | Live required | Evidence path when done |
| --- | --- | --- | --- |
| Unit: metadata forbidden keys / oversize | **Proven** via `tests/unit/` | — | pytest |
| Unit: error mapping (budget, unavailable) | **Proven** via `tests/unit/` | — | pytest |
| Gateway health (liveliness/readiness) | skipped | `LLG_LIVE=1` | integration tests / template |
| Four-provider non-stream smoke | — | credentials + stack | `templates/provider-smoke.md` |
| Stream / tools / structured | — | credentials + stack | `provider-compatibility-matrix.md` + smoke template |
| Virtual key ACL / budget / RPM | unit maps only | live keys | failure-matrix + integration |
| Postgres restart persistence | — | live compose | failure-matrix |
| Postgres down → readiness fail | stub listed | live chaos | `failure-matrix.md` |
| Langfuse export + correlation | — | Langfuse project | langfuse template |
| Langfuse unreachable (LLM still works) | — | live chaos | failure-matrix |
| Cost reconciliation ±5% / ±$0.01 | process only | billing + spend + Langfuse | cost-recon template |
| Staging/prod deploy | manifests only | hosting + secrets | operating-guide checklist |

## Index of runs

| Date | Run ID | Kind | Result | Artifact |
| --- | --- | --- | --- | --- |
| — | — | — | **No live runs indexed yet** | — |

Add a row per live exercise. Prefer one markdown file per run under `docs/evidence/` using the templates.

## Milestone report

Honest Definition of Done status: [`MILESTONE-REPORT.md`](./MILESTONE-REPORT.md).

## Related

- `docs/llm-platform/provider-compatibility-matrix.md`
- `docs/llm-platform/cost-reconciliation.md`
- `docs/evidence/failure-matrix.md`
- `uv run llg smoke` / `uv run llg reconcile-cost` (stubs without live data)
