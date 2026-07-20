# Milestone report — LiteLLM + Langfuse gateway

**Date:** 2026-07-19 (honesty pass INT-104; base after main flywheel #1–#9)  
**Branch:** evidence claims track `main` hermetic gates; live rows stay UNPROVEN until indexed  
**Honesty rule:** Claims must not exceed what was checked. Cost recon, Postgres chaos, Langfuse chaos, full provider live matrix, and org-wide app migration remain **UNPROVEN** unless a redacted run is linked from `docs/evidence/README.md`.

### Operator live notes (this environment)

| Item | Status |
| --- | --- |
| Virtual-key smokes (OpenAI / Gemini / Grok / Anthropic / llm-general) | **operator narrative only** — not indexed as a repo evidence row |
| Langfuse Cloud generations (classic `langfuse` callback) | **operator narrative only** — not indexed here |
| App wiring docs | **configured** on main (`app-wiring.md`) |

Narrative “exercised” notes without an evidence index row are **not** treated as verified live proof for DoD.

## Verification legend

| Label | Meaning |
| --- | --- |
| **configured** | Present in YAML/compose/docs |
| **hermetic-verified** | Unit/CI tests pass offline (no provider network) |
| **red-capable (live-gated)** | Automated test exists under `LLG_LIVE=1`; **not** proven until a live run is recorded |
| **exercised** | Ran against a real stack once **and** linked under Index of runs |
| **verified** | Exercised + durable evidence artifact |
| **UNPROVEN** | Not run, no credentials, or no captured evidence row |

## Definition of Done (1–20)

| # | Criterion | Status | Evidence pointer |
| --- | --- | --- | --- |
| 1 | All four providers called via LiteLLM with virtual keys | **UNPROVEN** (no indexed live row) | Smoke templates; matrix stream/tools unproven |
| 2 | Representative app needs no raw provider credential | **hermetic-verified** | `src/llm_client/`, `examples/`, `docs/llm-platform/app-wiring.md` |
| 3 | Postgres persistence survives gateway restart | **UNPROVEN** | `docs/evidence/failure-matrix.md` live row |
| 4 | Model restrictions, budgets, rate limits proven | **hermetic-verified** (error mapping + keys CLI) + **red-capable (live-gated)** ACL/budget tests; **live UNPROVEN** | Units: `tests/unit/test_llm_client.py`; live: `tests/integration/test_failure_modes_live.py` (`test_live_budget_exceeded`, `test_live_model_acl_denied`) — need `LLG_LIVE=1` + master + stack |
| 5 | Stable aliases documented and tested | **configured** + hermetic alias SoT checks | `model-aliases.yaml`, `litellm-config.yaml`, validate path |
| 6 | Provider failures → normalized actionable errors | **hermetic-verified** | `src/llm_client/errors.py`, unit tests |
| 7 | Safe fallback proven **or** explicitly disabled with rationale | **configured: disabled + rationale** | `litellm-config.yaml` (fallbacks off); ADRs / matrix |
| 8 | Every provider call in LiteLLM usage records | **UNPROVEN** | Requires live spend after smokes |
| 9 | Every provider call expected Langfuse telemetry | **configured** (classic `langfuse`); **live UNPROVEN** in index | `litellm-config.yaml`; keep host/region matched |
| 10 | Representative E2E correlated application trace | **UNPROVEN** (full app root correlation) | App wiring docs; dual-instrumentation optional |
| 11 | User/session/env/feature/release attribution per contract | **hermetic-verified** (schema + validator); live attach **UNPROVEN** | `metadata-contract.schema.json`, `tests/unit/test_metadata.py` |
| 12 | Prompt/response recording follows privacy policy | **configured** (policy doc) | `privacy-and-retention.md`; Cloud retention settings UNPROVEN |
| 13 | Langfuse outage tested, bounded | **UNPROVEN** (env-gated chaos: `LLG_CHAOS_LANGFUSE=1`) | failure-matrix; `test_langfuse_unreachable_llm_path_continues` |
| 14 | Postgres outage removes unhealthy instances (readiness) | **UNPROVEN** (env-gated chaos: `LLG_CHAOS_POSTGRES=1`) | failure-matrix; `test_postgres_down_readiness_fails` |
| 15 | Cost reconciled within approved tolerance | **UNPROVEN** | `cost-reconciliation.md` process only; no live run |
| 16 | Secrets absent from git, logs, fixtures, telemetry | **hermetic-verified** (gitignore hygiene + **CI gitleaks**) | `.github/workflows/ci.yml` `secret-scan` job (`gitleaks/gitleaks-action@v2`); scaffold hygiene |
| 17 | Production artifacts pinned | **configured** + **CI-enforced** digests on gateway compose files | `compose.yaml` digests; compose job pin check |
| 18 | Upgrade, rollback, backup, key-recovery documented | **configured** | `upgrade-notes.md`, `incident-recovery.md` |
| 19 | Verification evidence indexed and reproducible | **configured** (index + templates); live table empty | `docs/evidence/README.md` |
| 20 | No completion claim from docs/config/screenshots alone | **honored in this report** | Live items marked UNPROVEN until Index of runs has a row |

## Work package rollup (WP13–WP19)

| WP | Deliverable | Status |
| --- | --- | --- |
| WP13 | Stream/tools matrix; fallbacks disabled | **Docs live**; cells unproven |
| WP14 | Failure suite hermetic + live gates | **Hermetic proven**; live ACL/budget **red-capable**, chaos env-gated; all live **UNPROVEN** until run |
| WP15 | Cost recon process + CLI stub | **Docs + CLI**; numbers unproven |
| WP16 | Staging package (compose overlay + k8s sketch) | **Manifests/docs**; deploy unproven |
| WP17 | Production hardening checklist / operating guide | **Config + docs**; deploy unproven |
| WP18 | Platform docs + evidence index + this report | **Done (honest)** |
| WP19 | `llg` canonical; `smoke` / `reconcile-cost` stubs | **CLI stubs**; live smoke unproven |

## What was actually checked in hermetic hardening (repo CI)

- Unit tests under `tests/unit/` (failure-mode metadata/client mapping, alias SoT, etc.).
- Config validation path (`llg config validate` / unit coverage).
- **Gitleaks** secret scan on every PR/push to `main` (`.github/workflows/ci.yml`).
- Image digest pin enforcement + compose config validation.
- Mypy / ruff / TypeScript typecheck.
- Presence of pins, YAML SoT, fallbacks commented out, metadata contract.
- Live ACL/budget **test code** present under `LLG_LIVE` (does **not** prove enforcement without a live run).

## What was **not** checked (still UNPROVEN here)

- Live OpenAI / Anthropic / Gemini / xAI provider calls with indexed evidence.
- Live budget / ACL rejection against a real proxy (`LLG_LIVE=1` not claimed in this report).
- Langfuse Cloud export or correlation with evidence rows.
- Cost reconciliation arithmetic against real bills.
- Postgres-down / Langfuse-down chaos (`LLG_CHAOS_*` not exercised in this report).
- Staging or production cluster deploy.
- Controlled GitHub `live-smoke` workflow execution (workflow is opt-in; default CI never sets `LLG_LIVE`).

## Bottom line

Platform **scaffold and hermetic gates** (including gitleaks and pin enforcement) are in place. Live ACL/budget tests are **red-capable** under `LLG_LIVE=1` but **UNPROVEN** until operators run them and add an Index of runs row. **Milestone complete against DoD 1–20 is not claimed.** Unblock live rows with secrets, `LLG_LIVE=1` (optional chaos: `LLG_CHAOS_*`), optional [`.github/workflows/live-smoke.yml`](../../.github/workflows/live-smoke.yml), and evidence files linked from `docs/evidence/README.md`.
