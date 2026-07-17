# Provider / alias compatibility matrix (WP13)

**Status of live cells:** **unproven / requires `LLG_LIVE=1`** plus provider credentials and a running gateway. Hermetic CI does not exercise stream, tools, structured output, or cost fields against real providers.

Aliases match `config/llm/model-aliases.yaml` and `infra/llm-gateway/litellm-config.yaml`.

## Legend

| Cell value | Meaning |
| --- | --- |
| **unproven** | Configured in YAML; no live smoke evidence in this repo |
| **N/A** | Not applicable for this column |
| **pass / fail** | Only after a live run with redacted evidence under `docs/evidence/` |

## Matrix

| Alias | Provider route | non-stream | stream | tools | structured | cost fields |
| --- | --- | --- | --- | --- | --- | --- |
| `llm-general` | `openai/gpt-4o-mini` | unproven / requires `LLG_LIVE` | unproven / requires `LLG_LIVE` | unproven / requires `LLG_LIVE` | unproven / requires `LLG_LIVE` | unproven / requires `LLG_LIVE` |
| `openai-general` | `openai/gpt-4o-mini` | unproven / requires `LLG_LIVE` | unproven / requires `LLG_LIVE` | unproven / requires `LLG_LIVE` | unproven / requires `LLG_LIVE` | unproven / requires `LLG_LIVE` |
| `anthropic-general` | `anthropic/claude-haiku-4-5-20251001` | unproven / requires `LLG_LIVE` | unproven / requires `LLG_LIVE` | unproven / requires `LLG_LIVE` | unproven / requires `LLG_LIVE` | unproven / requires `LLG_LIVE` |
| `gemini-general` | `gemini/gemini-2.0-flash` | unproven / requires `LLG_LIVE` | unproven / requires `LLG_LIVE` | unproven / requires `LLG_LIVE` | unproven / requires `LLG_LIVE` | unproven / requires `LLG_LIVE` |
| `grok-general` | `xai/grok-3-mini` | unproven / requires `LLG_LIVE` | unproven / requires `LLG_LIVE` | unproven / requires `LLG_LIVE` | unproven / requires `LLG_LIVE` | unproven / requires `LLG_LIVE` |

**Deferred alias:** `llm-fast` is not enabled (no consumer yet). Do not invent matrix rows for unused aliases.

## How to fill a cell (live)

```bash
# Stack + virtual key + provider keys in .env
export LLG_LIVE=1
export LITELLM_VIRTUAL_KEY=sk-...   # not master
uv run llg smoke --alias openai-general
# Stream / tools / structured: exercise via GatewayClient or OpenAI SDK against
# LITELLM_BASE_URL, then attach redacted response + spend + Langfuse observation IDs
# under docs/evidence/ (never commit secrets or full prompts with PII).
```

See `docs/evidence/README.md` for templates. Until those artifacts exist, keep cells as **unproven**.

## Fallbacks: disabled (DoD #7)

**Router fallbacks are OFF by default.** `infra/llm-gateway/litellm-config.yaml` leaves `router_settings.fallbacks` commented out.

### Rationale (semantic risk)

1. **Tool / structured incompatibility:** Cross-provider fallback can change tool schemas, structured-output fidelity, and stop sequences mid-workflow. That is a silent behavior change, not a pure availability win.
2. **Cost and attribution:** Failover hops must be explicit aliases with a consumer and evidence; automatic multi-provider fallback obscures spend and ACL intent.
3. **No proven pair yet:** WP13 matrix cells above are unproven. Enabling fallbacks before stream/tools/structured proof for each hop violates plan policy.

### When to reconsider

Enable only after:

1. A documented pair (primary → fallback alias) with **pass** cells for non-stream, tools, and structured (if used by the consumer).
2. Explicit consumer ownership and budget/ACL on both aliases.
3. An ADR or config PR that uncomments a **named** fallback list (not silent provider SDK bypass).

Until then: apps retry or fail closed; no silent direct-to-provider path on gateway failure.

Also recorded in `docs/llm-platform/architecture.md` (fallback policy section).
