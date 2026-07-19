# ADR 0006 — Model alias authority chain (INT-002 / INT-117)

## Status

Accepted (2026-07); amended INT-117 (equality + registry roles)

## Context

Three lists claimed authority: `model-aliases.yaml`, `litellm-config.yaml`
`model_list`, and a hardcoded `STABLE_ALIASES` frozenset in `validate_config.py`.
Docs disagreed which file was write SoT.

INT-117 asked whether production `model_list` may contain undeclared
runtime-only routes. Forward-only validation (`aliases ⊆ model_list`) allowed
orphans that never appear in the semantic registry.

## Decision

| Layer | File / mechanism | Role |
| --- | --- | --- |
| **Semantic write SoT** | `config/llm/model-aliases.yaml` (`aliases:` keys) | Full registry: app + optional internal routes |
| **Runtime SoT** | `infra/llm-gateway/litellm-config.yaml` (`model_list`) | What the proxy actually serves |
| **App-facing set** | `load_stable_aliases()` | Registry keys with `registry_role: app` (default when omitted) |
| **Full registry set** | `load_registry_names()` | All `aliases:` keys |
| **Sync gate** | `llg config validate` | **Set equality**: registry names = `model_list` `model_name` set; each registry entry matches route + `os.environ/` key |

**No arbitrary runtime-only routes.** A name may appear in `model_list` only if
declared under `aliases:`. Internal/eval routes use `registry_role: internal`
plus non-empty `exemption_rationale` — not undeclared orphans.

No general config renderer in this ADR. Adding an alias: edit both YAMLs, run validate.

## Consequences

- Hardcoded frozenset removed; tests use `load_stable_aliases()` / derived `STABLE_ALIASES`.
- `llm-general` must remain present as the default app alias.
- Admin UI / DB still not production alias authority (ADR 0002).
- Undeclared `model_list` entries fail `llg config validate`.
- Virtual-key `--models` validation continues to use app-facing `load_stable_aliases()`.
