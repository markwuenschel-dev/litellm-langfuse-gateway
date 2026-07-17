# Provider onboarding

**Status:** Stub (WP6 + WP7)  
**Related:** `config/llm/model-aliases.yaml`, `infra/llm-gateway/litellm-config.yaml`,  
`docs/llm-platform/provider-call-inventory.md`

## Purpose

Document how a provider family is wired into the gateway: env keys, LiteLLM model
prefix, stable alias, and a smoke matrix (chat / stream / tools / structured /
embeddings). Fill cells at pin time and when running live smokes — do not invent
support claims without evidence.

## Stable aliases (app-facing contract)

| Alias | Intent | Initial route (verify at smoke) | Env key | Consumers |
| --- | --- | --- | --- | --- |
| `llm-general` | Default chat | `openai/gpt-4o-mini` | `OPENAI_API_KEY` | Examples, README, reference workflow |
| `openai-general` | Explicit OpenAI | `openai/gpt-4o-mini` | `OPENAI_API_KEY` | Provider smoke |
| `anthropic-general` | Explicit Anthropic | `anthropic/claude-haiku-4-5-20251001` | `ANTHROPIC_API_KEY` | Provider smoke |
| `gemini-general` | Explicit Gemini | `gemini/gemini-2.0-flash` | `GEMINI_API_KEY` | Provider smoke |
| `grok-general` | Explicit xAI | `xai/grok-3-mini` | `XAI_API_KEY` | Provider smoke |

**Not shipped:** `llm-fast` (no consumer yet). Azure / Cohere / Groq (env stubs only).

**Fallbacks:** Off by default. Do not enable multi-provider fallback groups until
stream/tools/structured compatibility is proven (plan WP13).

## Alias change checklist

Before changing any alias → provider mapping:

1. Reason for the change
2. Eval / quality evidence
3. Cost comparison
4. Latency comparison
5. Tools / structured-output check
6. Rollback mapping documented
7. Release note / config changelog entry

## Provider matrix (placeholders — verify at pin / smoke)

| Provider | Prefix | Chat | Stream | Tools | Structured | Embeddings | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OpenAI | `openai/` | TBD | TBD | TBD | TBD | TBD | Verify model id against pinned LiteLLM docs |
| Anthropic | `anthropic/` | TBD | TBD | TBD | TBD | TBD | Dated model ids change; re-check at smoke |
| Google Gemini | `gemini/` | TBD | TBD | TBD | TBD | TBD | Confirm flash/pro id availability |
| xAI / Grok | `xai/` | TBD | TBD | TBD | TBD | TBD | Confirm mini vs full id |

## Smoke (planned CLI — WP6+)

```bash
# Per provider (when llg smoke exists):
uv run llg smoke --provider openai --alias openai-general
uv run llg smoke --provider anthropic --alias anthropic-general
uv run llg smoke --provider gemini --alias gemini-general
uv run llg smoke --provider xai --alias grok-general
```

Until smoke CLI lands, manual chat via OpenAI SDK / curl against
`LITELLM_BASE_URL` with the alias as `model` is acceptable.

**Evidence per call (when exercised):** alias, resolved model, request_id,
LiteLLM spend row, Langfuse generation id, tokens, latency.

## Credential rules

- Provider keys live only in env / secret manager (`OPENAI_API_KEY`, etc.).
- Config YAML must use `api_key: os.environ/<NAME>` only — never literals.
- Apps use virtual keys against the gateway; they never hold provider keys.

## Validation

```bash
uv run llg config validate
# enforces: unique model_name, os.environ/ api keys, provider prefix on routes,
# and sync with config/llm/model-aliases.yaml
```
