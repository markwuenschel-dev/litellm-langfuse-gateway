# Slice Contract — INT-116 (S1′)

**Queue:** production-flywheel · PR #10 (`feat/integrity-v2-batch`)  
**Design lane:** A (grill-with-docs) — Decisions 1–4 ratified.

## Behavior to change

Replace the always-`Exit(2)` / `LLG_LIVE`-gated `llg reconcile-cost` stub with a **file-backed, auditable reconciliation engine** that validates a YAML run artifact and evaluates three-way cost agreement with honest exit codes.

## Public interface

```text
uv run llg reconcile-cost
  → process guide; exit 2

uv run llg reconcile-cost --run-file PATH
  → human result on stdout; exit 0 | 1 | 2

uv run llg reconcile-cost --run-file PATH --json
  → one JSON object on stdout; diagnostics on stderr; exit 0 | 1 | 2
```

Module: `src/llg/reconcile_cost.py`

- `load_run(path) -> RunDocument`
- `reconcile(run) -> ReconcileResult` (pure)
- `format_human(result) -> str`
- `format_json(result) -> str`

## Acceptance criteria

1. YAML run file is the only machine input; `run_id` lives only in YAML (no `--run-id`).
2. Markdown is optional human narrative (not parsed); `--write-md` **not** in this slice.
3. Amounts are quoted decimal strings → `Decimal`; one run-level `currency`.
4. Periods are UTC half-open `[start, end)` with **exactly equal** bounds across required sources in a group.
5. DoD #15 mode requires `required_source_roles` default/minimum `{provider, litellm, langfuse}`; custom roles additive only.
6. Per source: `source_role`, `source_id`, `amount`, `period`, `collected_at`, `evidence_ref` (immutable retained artifact; dashboard URL alone insufficient), `provenance`.
7. Group: `comparison_scope_id` + narrative `inclusion_basis`.
8. Pair formula DOC′; emit all three pair reports; group within iff all pairs within.
9. Exit `0` complete + all groups within; `1` complete + any group outside; `2` incomplete/invalid/unproven.
10. All required amounts zero → exit 2, `unproven_zero_cost_group`.
11. Negative amount → exit 2. No `LLG_LIVE` required for exit 0 on a valid manual/export file.
12. Closes ledger wording: **mechanism implemented**; does **not** claim three-system live recon without a real complete run.

## Out of scope

- Live multi-system fetch (S2/S3)
- FX / multi-currency
- Credits/negatives policy
- `--write-md`
- Claiming milestone DoD #15 live-proven

## Verification

```text
uv run pytest tests/unit/test_reconcile_cost.py tests/unit/test_cli.py -q
uv run ruff check src/llg/reconcile_cost.py src/llg/cli.py tests/unit/test_reconcile_cost.py
uv run llg reconcile-cost   # exit 2 guide
```

## Capture

- Docs: `docs/llm-platform/cost-reconciliation.md` (DOC′ three-way)
- Template: `docs/evidence/templates/cost-recon.md` (companion, not parser input)
- Ledger: INT-116 → shipped
- Example fixture under `tests/fixtures/cost_recon/`
