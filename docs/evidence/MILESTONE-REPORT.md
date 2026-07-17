# Milestone report — LiteLLM + Langfuse gateway

**Date:** 2026-07-17  
**Branch worktree:** `feature-llm-gateway`  
**Honesty rule:** Claims must not exceed what was checked. Live provider smokes, Langfuse correlation, cost recon, Postgres outage, and similar rows are **UNPROVEN** without credentials / `LLG_LIVE`.

## Verification legend

| Label | Meaning |
| --- | --- |
| **configured** | Present in YAML/compose/docs |
| **hermetic-verified** | Unit/CI tests pass offline |
| **exercised** | Ran against a real stack once |
| **verified** | Exercised + evidence artifact |
| **UNPROVEN** | Not run or no credentials/evidence |

## Definition of Done (1–20)

| # | Criterion | Status | Evidence pointer |
| --- | --- | --- | --- |
| 1 | All four providers called via LiteLLM with virtual keys | **UNPROVEN** | Needs provider keys + `LLG_LIVE`; matrix: `docs/llm-platform/provider-compatibility-matrix.md` |
| 2 | Representative app needs no raw provider credential | **hermetic-verified** (client/examples design) | `src/llm_client/`, `examples/reference_workflow.py`; live path UNPROVEN |
| 3 | Postgres persistence survives gateway restart | **UNPROVEN** | `docs/evidence/failure-matrix.md` live row |
| 4 | Model restrictions, budgets, rate limits proven | **hermetic-verified** (error mapping + keys CLI); **live UNPROVEN** | `tests/unit/test_llm_client.py`, `llg keys`; live ACL/budget unproven |
| 5 | Stable aliases documented and tested | **configured** + config validate; live smoke **UNPROVEN** | `model-aliases.yaml`, `litellm-config.yaml`, `llg config validate` |
| 6 | Provider failures → normalized actionable errors | **hermetic-verified** | `src/llm_client/errors.py`, unit tests |
| 7 | Safe fallback proven **or** explicitly disabled with rationale | **configured: disabled + rationale** | `litellm-config.yaml` (fallbacks off); `provider-compatibility-matrix.md`, `architecture.md` |
| 8 | Every provider call in LiteLLM usage records | **UNPROVEN** | Requires live spend after smokes |
| 9 | Every provider call expected Langfuse telemetry | **configured** (`langfuse_otel`); export **UNPROVEN** | `litellm-config.yaml` callbacks |
| 10 | Representative E2E correlated application trace | **UNPROVEN** | Langfuse project + `templates/langfuse-correlation.md` |
| 11 | User/session/env/feature/release attribution per contract | **hermetic-verified** (schema + validator); live attach **UNPROVEN** | `metadata-contract.schema.json`, `tests/unit/test_metadata.py` |
| 12 | Prompt/response recording follows privacy policy | **configured** (policy doc) | `privacy-and-retention.md`; Cloud retention settings UNPROVEN |
| 13 | Langfuse outage tested, bounded | **UNPROVEN** | failure-matrix live row |
| 14 | Postgres outage removes unhealthy instances (readiness) | **UNPROVEN** | failure-matrix live row; health tests only when stack up |
| 15 | Cost reconciled within approved tolerance | **UNPROVEN** | `cost-reconciliation.md` process only; no live run |
| 16 | Secrets absent from git, logs, fixtures, telemetry | **hermetic hygiene** (gitignore, no secrets in scaffold) | Manual review of this worktree; no gitleaks run claimed here |
| 17 | Production artifacts pinned | **configured** | `compose.yaml` digests, `upgrade-notes.md` |
| 18 | Upgrade, rollback, backup, key-recovery documented | **configured** | `upgrade-notes.md`, `incident-recovery.md` |
| 19 | Verification evidence indexed and reproducible | **configured** (index + templates) | `docs/evidence/README.md`; live runs empty |
| 20 | No completion claim from docs/config/screenshots alone | **honored in this report** | Live items marked UNPROVEN |

## Work package rollup (WP13–WP19)

| WP | Deliverable | Status |
| --- | --- | --- |
| WP13 | Stream/tools matrix; fallbacks disabled | **Docs live**; cells unproven |
| WP14 | Failure suite hermetic + live stubs | **Hermetic tests**; live chaos unproven |
| WP15 | Cost recon process + CLI stub | **Docs + CLI**; numbers unproven |
| WP16 | Staging package (compose overlay + k8s sketch) | **Manifests/docs**; deploy unproven |
| WP17 | Production hardening checklist / operating guide | **Config + docs**; deploy unproven |
| WP18 | Platform docs + evidence index + this report | **Done (honest)** |
| WP19 | `llg` canonical; `smoke` / `reconcile-cost` stubs | **CLI stubs**; live smoke unproven |

## What was actually checked in hermetic hardening

- Unit tests under `tests/unit/` (including failure-mode metadata/client mapping).
- Config validation path (`llg config validate` / unit coverage).
- Presence of pins, YAML SoT, fallbacks commented out, metadata contract.

## What was **not** checked

- Live OpenAI / Anthropic / Gemini / xAI calls.
- Langfuse Cloud export or correlation.
- Cost reconciliation arithmetic against real bills.
- Postgres down / Langfuse down chaos.
- Staging or production cluster deploy.
- Secret scanning CI job success in this session (not asserted).

## Bottom line

Platform **scaffold and hermetic gates** are in place for control-plane + observability design. **Milestone complete against DoD 1–20 is not claimed.** Unblock live rows with secrets, `LLG_LIVE=1`, and evidence files linked from `docs/evidence/README.md`.
