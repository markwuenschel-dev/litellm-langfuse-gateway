# Provider-call inventory (current state)

**Status:** Live platform inventory  
**Date:** 2026-07-19  
**Scope:** This repository (`litellm-langfuse-gateway`) — gateway config, examples, tests, docs.

## External consumers

Sibling apps may call this gateway with a virtual key and stable aliases. This inventory tracks **in-repo** call surfaces and the **canonical model registry**. External app wiring is documented in `docs/llm-platform/app-wiring.md`, not listed as code in this tree.

---

## Search method

| Method | What was scanned |
| --- | --- |
| Config | `infra/llm-gateway/litellm-config.yaml`, `config/llm/model-aliases.yaml` |
| Env template | `infra/llm-gateway/.env.example` (canonical); root `.env.example` pointer-only |
| Compose | `infra/llm-gateway/compose.yaml`, `compose.redis.yaml` (+ root include shims) |
| Examples | `examples/python_client.py`, `examples/ts_client.ts`, `examples/reference_workflow/` |
| Docs | `README.md`, `AGENTS.md`, `docs/llm-platform/*` |
| Tests | `tests/unit/`, `tests/integration/` |
| Client | `src/llm_client/` (GatewayClient) |
| Ops CLI | `src/llg/` (`llg smoke`, keys, health) |

No raw provider base URLs (`api.openai.com`, etc.) appear in first-party app call sites. Clients target LiteLLM (`LITELLM_BASE_URL`; dual dialect normalized via `llm_client.proxy_url`).

---

## Stable model list (YAML SoT)

**Source of truth:** `infra/llm-gateway/litellm-config.yaml` (must stay in sync with `config/llm/model-aliases.yaml`).

| Client alias (`model_name`) | Provider route (`litellm_params.model`) | Credential env |
| --- | --- | --- |
| `llm-general` | `openai/gpt-4o-mini` | `OPENAI_API_KEY` |
| `openai-general` | `openai/gpt-4o-mini` | `OPENAI_API_KEY` |
| `anthropic-general` | `anthropic/claude-haiku-4-5-20251001` | `ANTHROPIC_API_KEY` |
| `gemini-general` | `gemini/gemini-3.5-flash` | `GEMINI_API_KEY` |
| `grok-general` | `xai/grok-3-mini` | `XAI_API_KEY` |

**Not enabled in model_list (env stubs only):** Azure, Cohere, Groq — no aliases without a consumer.

**Fallbacks:** Off by default (commented in config).

**Telemetry (gateway):** classic `langfuse` success/failure callbacks (`LANGFUSE_*`; host must match project region).

---

## Call-site inventory

| App / source | Models / aliases | Features | Credential | Telemetry |
| --- | --- | --- | --- | --- |
| `examples/python_client.py` | `llm-general` (override `LITELLM_MODEL`) | Chat completions | `LITELLM_VIRTUAL_KEY` | Gateway Langfuse if configured |
| `examples/ts_client.ts` | Same | Chat completions | Same | Same |
| `examples/reference_workflow/` | Stable aliases | Reference multi-step | Virtual key | App + gateway |
| `uv run llg smoke` | `--alias` (default `llm-general`) | Chat smoke | Virtual key + `LLG_LIVE=1` | Gateway |
| `src/llm_client` unit tests | `llm-general` fixtures | Mocked HTTP | Test keys | N/A |
| Config unit tests | Stable alias fixtures | Validate YAML | `os.environ/...` strings | N/A |

---

## Provider SDK / credential surface

| Provider | Direct SDK in apps | Gateway env | Notes |
| --- | --- | --- | --- |
| OpenAI | Via OpenAI SDK → LiteLLM base URL | `OPENAI_API_KEY` | Default for `llm-general` / `openai-general` |
| Anthropic | None first-party | `ANTHROPIC_API_KEY` | `anthropic-general` |
| Google Gemini | None first-party | `GEMINI_API_KEY` | `gemini-general` (`gemini-3.5-flash`) |
| xAI / Grok | None first-party | `XAI_API_KEY` | `grok-general` |
| Azure / Cohere / Groq | None | Optional stubs | No `model_list` entries |

---

## URL dialect

| Surface | Shape | Helper |
| --- | --- | --- |
| Ops / health / keys | Proxy root **without** `/v1` | `llm_client.proxy_url.proxy_root` |
| Apps / chat completions | OpenAI base **with** `/v1` | `llm_client.proxy_url.openai_base` |

`LITELLM_BASE_URL` may be set either way; both helpers normalize.

---

## Honesty

- Live provider smokes and multi-system cost recon remain **UNPROVEN** without `LLG_LIVE` + credentials + evidence under `docs/evidence/`.
- Do not invent aliases without a consumer.
- Do not claim production readiness from this inventory alone.
