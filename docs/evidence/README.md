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

## Hermetic CI (always on `main` PR/push)

| Capability | Status | Where |
| --- | --- | --- |
| Unit: metadata forbidden keys / oversize | **Proven** | `tests/unit/` |
| Unit: error mapping (budget, ACL, rate limit) | **Proven** | `tests/unit/` |
| Secret scan (gitleaks) | **Proven** (CI job) | `.github/workflows/ci.yml` → `secret-scan` |
| Image digest pins + compose config | **Proven** (CI job) | compose job in `ci.yml` |
| Live integration tests | **Skipped** by default (`LLG_LIVE` unset) | `tests/integration/` |

## Unproven without `LLG_LIVE` / credentials (matrix)

| Capability | Hermetic (CI) | Live required | Evidence path when done |
| --- | --- | --- | --- |
| Gateway health (liveliness/readiness) | skipped | `LLG_LIVE=1` | integration tests / template |
| Four-provider non-stream smoke | — | credentials + stack | `templates/provider-smoke.md` |
| Stream / tools / structured | — | credentials + stack | `provider-compatibility-matrix.md` + smoke template |
| Virtual key ACL / budget | unit maps + **red-capable** live tests | `LLG_LIVE=1` + master | failure-matrix + `test_failure_modes_live.py` |
| Postgres restart persistence | — | live compose | failure-matrix |
| Postgres down → readiness fail | env-gated chaos | `LLG_LIVE=1` + `LLG_CHAOS_POSTGRES=1` | `failure-matrix.md` |
| Langfuse export + correlation | — | Langfuse project | langfuse template |
| Langfuse unreachable (LLM still works) | env-gated chaos | `LLG_LIVE=1` + `LLG_CHAOS_LANGFUSE=1` | failure-matrix |
| Cost reconciliation ±5% / ±$0.01 | process only | billing + spend + Langfuse | cost-recon template |
| Staging/prod deploy | manifests only | hosting + secrets | operating-guide checklist |

## Index of runs

| Date | Run ID | Kind | Result | Artifact |
| --- | --- | --- | --- | --- |
| — | — | — | **No live runs indexed yet** | — |

**How to read this table:** An empty table (placeholder row only) means **no captured live evidence has been committed**. Operator anecdotes, local terminal history, and CI green hermetic jobs do **not** fill this table. Live claims stay **UNPROVEN** until a row exists.

### How to add a row

1. Run the exercise with real credentials (`LLG_LIVE=1`, stack up). Do not commit secrets.
2. Copy a template under `docs/evidence/templates/` to a dated file, e.g.  
   `docs/evidence/runs/2026-07-19-budget-acl.md` (create `runs/` if needed).
3. Fill redacted status codes, aliases, pass/fail — never keys or full prompts.
4. Append one row to the table above: date, run id, kind, result, relative link to the artifact.
5. Optionally update `MILESTONE-REPORT.md` DoD cells that the run covers (only those cells).

### Controlled CI live path (opt-in, costs money)

[`.github/workflows/live-smoke.yml`](../../.github/workflows/live-smoke.yml) is **`workflow_dispatch` only** — never on push/PR. It needs a reachable gateway (`LITELLM_BASE_URL`), secrets (`LITELLM_VIRTUAL_KEY`, and master for ACL/budget key create), and burns provider spend. Prefer a protected GitHub Environment named `live-smoke`. After a green dispatch, still add an Index of runs row; the workflow alone is not an evidence artifact.

## Milestone report

Honest Definition of Done status: [`MILESTONE-REPORT.md`](./MILESTONE-REPORT.md).

## Related

- `docs/llm-platform/provider-compatibility-matrix.md`
- `docs/llm-platform/cost-reconciliation.md`
- `docs/evidence/failure-matrix.md`
- `uv run llg smoke` / `uv run llg reconcile-cost` (stubs without live data)
