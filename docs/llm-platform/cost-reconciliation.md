# Cost reconciliation process (WP15)

Compare **provider-reported usage**, **LiteLLM spend**, and **Langfuse observation costs** for a fixed prompt set. Do **not** claim cost accuracy without a completed run and evidence under `docs/evidence/`.

## Status

| Item | State |
| --- | --- |
| Process document | **This file (live)** |
| CLI helper | `uv run llg reconcile-cost` (prints procedure; does not invent numbers) |
| Live reconciliation run | **UNPROVEN** without provider credentials, gateway spend data, and Langfuse project access |

## Tolerance proposal (initial)

Per call group (same alias + fixed prompt set, N≥3):

| Rule | Value |
| --- | --- |
| Relative | **±5%** of the larger of (LiteLLM spend, provider spend) |
| Absolute floor | **±$0.01** (use the larger of relative vs absolute) |

Example: if LiteLLM reports $0.12 and provider reports $0.125, relative delta is ~4% and absolute is $0.005 → **within** tolerance.

**Adjust after first live run** if known systematic deltas (cached tokens, reasoning tokens, failed retries billed once) dominate noise.

## Process

```text
1. Fix prompt set (N calls per alias/provider under test)
2. Capture provider usage (dashboard or billing API) for the time window
3. Capture LiteLLM spend (Admin UI / spend API / Postgres spend logs)
4. Capture Langfuse observation / generation costs for the same request_ids
5. Diff pairwise (provider↔LiteLLM, LiteLLM↔Langfuse)
6. Flag groups outside ±5% or ±$0.01 (whichever larger)
7. Document known deltas; file defect if unexplained
```

### Fixed prompt guidance

- Short, non-sensitive fixed text (no PII).
- Same `model_alias`, temperature, and max_tokens for the group.
- Prefer a dedicated low-budget virtual key (`llg keys create --max-budget …`).
- Record `request_id` values for Langfuse join.

### Known delta classes (do not “fix” without notes)

| Class | Notes |
| --- | --- |
| Cached / prompt-cache tokens | Provider may bill differently than LiteLLM estimate |
| Reasoning / thinking tokens | Some models report extra token classes |
| Failed retries | Provider may bill failed attempts; ensure LiteLLM counts match |
| Streaming vs non-stream | Prefer same mode for a reconciliation group |
| Currency / rounding | Sub-cent rounding can trip absolute floor on tiny calls |

## CLI

```bash
uv run llg reconcile-cost
uv run llg reconcile-cost --run-id my-run-2026-07-17
```

Without live data the command explains the process and exits **0** with a clear **UNPROVEN** message. It does **not** fabricate reconciliation tables.

## Evidence

Store redacted run summaries under:

```text
docs/evidence/cost-recon-<run-id>.md
```

Template: `docs/evidence/templates/cost-recon.md`. Index: `docs/evidence/README.md`.

## Honesty rule

Docs, screenshots, or unit tests alone do **not** satisfy Definition of Done #15. Milestone claims require a filled reconciliation table with measured values.
