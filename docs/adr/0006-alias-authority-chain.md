# ADR 0006 — Model alias authority chain (INT-002)

## Status

Accepted (2026-07)

## Context

Three lists claimed authority: `model-aliases.yaml`, `litellm-config.yaml`
`model_list`, and a hardcoded `STABLE_ALIASES` frozenset in `validate_config.py`.
Docs disagreed which file was write SoT.

## Decision

| Layer | File / mechanism | Role |
| --- | --- | --- |
| **Semantic write SoT** | `config/llm/model-aliases.yaml` (`aliases:` keys) | App-facing stable alias set + route intent |
| **Runtime SoT** | `infra/llm-gateway/litellm-config.yaml` (`model_list`) | What the proxy actually serves |
| **Derived check set** | `load_stable_aliases()` | Keys of `aliases:` — **not** a third hand-edited list |
| **Sync gate** | `llg config validate` | Every alias appears in `model_list` with matching route + `os.environ/` key |

No general config renderer in this slice. Adding an alias: edit both YAMLs, run validate.

## Consequences

- Hardcoded frozenset removed; tests use `load_stable_aliases()` / derived `STABLE_ALIASES`.
- `llm-general` must remain present as the default app alias.
- Admin UI / DB still not production alias authority (ADR 0002).
