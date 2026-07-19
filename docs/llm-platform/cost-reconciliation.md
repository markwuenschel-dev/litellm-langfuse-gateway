# Cost reconciliation process (WP15 / INT-116)

Compare **provider-reported usage**, **LiteLLM spend**, and **Langfuse observation costs** for a fixed comparison scope. Do **not** claim live three-system reconciliation without a completed run artifact whose retained exports back every amount.

## Status

| Item | State |
| --- | --- |
| Process document | **This file (live)** |
| Machine contract | YAML run file (required for the engine) |
| Human narrative | Optional Markdown companion (`docs/evidence/templates/cost-recon.md`) — **not** parser input |
| CLI | `uv run llg reconcile-cost --run-file PATH` |
| Mechanism (S1′) | **Implemented** — pure engine + exit codes over a run file |
| Live three-system fetch | **Not implemented** (out of scope for S1′); `LLG_LIVE` reserved for future fetchers |
| Live reconciliation claim | **UNPROVEN** until a real complete run with retained exports exists |

**Ledger honesty:** shipping the mechanism closes “reconciliation mechanism never implemented.” It does **not** close “three-system costs reconciled.”

## Run artifact (machine input)

Operators (or future fetchers) produce a YAML file. Schema version `1`.

| Run field | Rule |
| --- | --- |
| `run_id` | Required; sole authority (no CLI `--run-id`) |
| `currency` | One run-level currency (e.g. `USD`); mixed currency rejected; no FX |
| `tolerance.relative` / `tolerance.absolute` | Quoted decimal strings |
| `required_source_roles` | Default/minimum for DoD #15: `provider`, `litellm`, `langfuse`; `custom` additive only |
| `groups[]` | Non-empty |

| Group field | Rule |
| --- | --- |
| `id` | Group label (e.g. alias) |
| `comparison_scope_id` | Stable cohort id proving the same inclusion set |
| `inclusion_basis` | Required narrative (not the only proof of cohort match) |
| `sources[]` | Must cover all required roles |

| Source field | Rule |
| --- | --- |
| `source_role` | `provider` \| `litellm` \| `langfuse` \| `custom` |
| `source_id` | Concrete system id (e.g. `openai-billing-export`) |
| `amount` | **Quoted** decimal string → `Decimal` (never bare YAML floats) |
| `period` | UTC half-open `[start, end)` — **exactly equal** bounds across required roles in the group |
| `collected_at` | When the figure was collected (systems settle at different times) |
| `evidence_ref` | Retained export/screenshot/note path; a mutable dashboard URL alone is insufficient |
| `provenance` | `manual` \| `export` \| `api` (label only in S1′ — no fetch) |

See fixtures: `tests/fixtures/cost_recon/*.yaml`.

## Comparison algorithm (DOC′)

For each complete group, evaluate **three named pairs**:

1. provider ↔ litellm  
2. litellm ↔ langfuse  
3. provider ↔ langfuse  

For each pair `(a, b)` with `Decimal` arithmetic:

```text
difference = abs(a - b)
limit = max(relative * max(abs(a), abs(b)), absolute)
within = difference <= limit
```

- Group **within** only if **all three** pairs are within.
- Under non-negative amounts this is equivalent in pass/fail to a max−min range check; the engine still **emits three pair reports** for diagnosis.
- zero↔zero pair: `relative_delta` is `null` (no divide-by-zero).
- All required amounts zero → incomplete, reason `unproven_zero_cost_group` (not a green DoD).
- Negative amounts → invalid v1 input.

Default tolerance proposal: relative `0.05`, absolute `0.01` (same currency units).

## Exit codes

| Code | Meaning |
| --- | --- |
| **0** | Complete comparable table; every group within tolerance |
| **1** | Complete table; one or more groups outside tolerance |
| **2** | Incomplete, incompatible, invalid, or unproven inputs (including guide mode with no `--run-file`) |

A valid manual/export-backed run file can exit **0 without `LLG_LIVE`**. This slice performs **no network access**.

## CLI

```bash
uv run llg reconcile-cost
# → guide; exit 2

uv run llg reconcile-cost --run-file path/to/run.yaml
# → human result on stdout; exit 0|1|2

uv run llg reconcile-cost --run-file path/to/run.yaml --json
# → one JSON object on stdout; diagnostics on stderr; exit 0|1|2
```

## Process (operator)

```text
1. Fix comparison_scope_id + prompt set (N calls per alias under test)
2. Capture retained exports for provider, LiteLLM, Langfuse for identical UTC [start, end)
3. Fill YAML run file (quoted decimals, evidence_ref paths, collected_at)
4. uv run llg reconcile-cost --run-file run.yaml
5. Optionally write human narrative via docs/evidence/templates/cost-recon.md
6. Index under docs/evidence/ when claiming a live milestone
```

### Known delta classes (do not “fix” without notes)

| Class | Notes |
| --- | --- |
| Cached / prompt-cache tokens | Provider may bill differently than LiteLLM estimate |
| Reasoning / thinking tokens | Some models report extra token classes |
| Failed retries | Provider may bill failed attempts; ensure LiteLLM counts match |
| Streaming vs non-stream | Prefer same mode for a reconciliation group |
| Currency / rounding | Sub-cent rounding can trip absolute floor on tiny calls |

## Honesty rule

Docs, unit tests, or a synthetic fixture alone do **not** satisfy a **live** Definition of Done #15 claim. Milestone claims require a filled run artifact with measured values and retained evidence files. The engine shipping does satisfy “reconciliation mechanism implemented.”
