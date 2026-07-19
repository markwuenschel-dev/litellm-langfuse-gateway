# ADR 0002 — YAML model registry is production source of truth

## Status

Accepted (2026-07)

## Context

LiteLLM can store models in the DB / Admin UI (`store_model_in_db`). Dual authority
between YAML and UI creates split-brain aliases for apps that expect stable names
(`llm-general`, `openai-general`, …).

## Decision

- Production model aliases and routes are defined in `infra/llm-gateway/litellm-config.yaml`.
- Semantic contract mirror: `config/llm/model-aliases.yaml` (kept in sync via `llg config validate`).
- Compose sets `STORE_MODEL_IN_DB=False`.
- Admin UI / DB model edits are **not** authority for production aliases.

## Consequences

- Alias changes are code review + validate, not runtime UI edits.
- Flipping SoT to DB/UI requires an explicit ADR and migration plan.
- Triple write surface (`STABLE_ALIASES` frozenset in validate_config) remains a
  known integrity follow-up (INT-002) until a single compile/render seam lands.
