# Provider-call inventory (current state)

**Status:** Reference-only milestone  
**Date:** 2026-07-17  
**Scope searched:** This worktree only  
  (`C:\Users\Nalakram\Documents\GitHub\litellm-langfuse-gateway\.worktrees\feature-llm-gateway`)

## External consumers

**No external application monorepo or sibling apps were found or accessible from this repository.**

Evidence checked in-repo:

| Source | Finding |
| --- | --- |
| `README.md`, `AGENTS.md` | Describe gateway + examples only; no named production apps |
| Plan (`docs/superpowers/plans/2026-07-17-unified-litellm-langfuse-gateway.md`) | Explicit greenfield platform repo; WP1 says if no external apps → document reference-only milestone |
| Code search | Provider SDK usage limited to `examples/` + test fixtures; no app packages calling providers directly |

Therefore this inventory is **reference-only**: consumers are this repo’s examples, README smoke path, planned reference workflow, and planned provider smokes — not live org apps.

---

## Search method

| Method | What was scanned |
| --- | --- |
| Config | `infra/llm-gateway/litellm-config.yaml` |
| Env template | `infra/llm-gateway/.env.example`, root `.env.example` |
| Compose | `infra/llm-gateway/compose.yaml`, `compose.redis.yaml` (+ root include shims) |
| Examples | `examples/python_client.py`, `examples/ts_client.ts` |
| Docs | `README.md`, `AGENTS.md`, plan §7.1 aliases |
| Tests | `tests/test_validate_config.py` (fixture models only) |
| Deps | `package.json` (`openai`), `pyproject.toml` (`openai`) |
| Grep | `openai`, `anthropic`, `gemini`, `grok`, `xai`, `azure`, `bedrock`, `cohere`, `mistral`, model strings |

No raw provider base URLs (`api.openai.com`, etc.) appear in first-party call sites. Clients target LiteLLM (`LITELLM_BASE_URL`, default `http://localhost:4000/v1`).

---

## Scaffold model list (`infra/llm-gateway/litellm-config.yaml`)

These are the **current** LiteLLM `model_name` aliases clients may request. Provider routes are env-keyed; no secrets in YAML.

| Client alias (`model_name`) | Provider route (`litellm_params.model`) | Credential env |
| --- | --- | --- |
| `gpt-4o` | `openai/gpt-4o` | `OPENAI_API_KEY` |
| `gpt-4o-mini` | `openai/gpt-4o-mini` | `OPENAI_API_KEY` |
| `claude-sonnet` | `anthropic/claude-sonnet-4-20250514` | `ANTHROPIC_API_KEY` |
| `claude-haiku` | `anthropic/claude-haiku-4-5-20251001` | `ANTHROPIC_API_KEY` |
| `gemini-flash` | `gemini/gemini-2.0-flash` | `GEMINI_API_KEY` |
| `gemini-pro` | `gemini/gemini-2.0-pro` | `GEMINI_API_KEY` |
| `grok` | `xai/grok-3` | `XAI_API_KEY` |
| `grok-mini` | `xai/grok-3-mini` | `XAI_API_KEY` |

**Not enabled in model_list (env stubs only):** Azure (`AZURE_API_KEY` / `AZURE_API_BASE`), Cohere (`COHERE_API_KEY`), Groq (`GROQ_API_KEY` in `.env.example` only). No consumers → do not invent aliases for them.

**Fallbacks:** Commented out in config; not live.

**Telemetry (gateway):** `success_callback` / `failure_callback`: classic `langfuse` (requires `LANGFUSE_*` env; host must match project region).

---

## Call-site inventory

| App / source | Models / aliases requested | Features used | Credential source | Telemetry today | Privacy tier |
| --- | --- | --- | --- | --- | --- |
| `examples/python_client.py` | Default `llm-general`; override via `LITELLM_MODEL` | Chat completions only (non-stream, no tools) | `LITELLM_VIRTUAL_KEY` only (`sk-…`); base `LITELLM_BASE_URL` | Gateway classic `langfuse` if configured | Non-sensitive (“pong” prompt) |
| `examples/ts_client.ts` | Same: default `gpt-4o-mini`; `LITELLM_MODEL` | Same as Python | Same | Same | Non-sensitive |
| `README.md` / `llg smoke` | Stable aliases (`llm-general`, …) | Chat smokes | Virtual key for apps; master for admin only | Gateway classic `langfuse` if configured | Non-sensitive |
| `tests/test_validate_config.py` | Fixture names `demo`, `gpt-4o-mini` | N/A (config validation, no live calls) | Fixture `os.environ/OPENAI_API_KEY` strings | N/A | N/A |
| Planned reference workflow (plan WP11 / §7.1) | Intended: `llm-general` (and optionally `llm-fast`) | Planned: chat + later stream/tools/structured matrix (WP13) | Virtual key per app/env via gateway | App Langfuse root + gateway generation | Default non-sensitive for reference |
| Planned provider smokes (plan WP6) | Intended: `openai-general`, `anthropic-general`, `gemini-general`, `grok-general` | Smoke: chat; matrix later | Gateway provider keys + smoke uses gateway auth | Spend + Langfuse generation evidence | Non-sensitive smoke prompts |

---

## Provider SDK / credential surface (repo)

| Provider | First-party direct SDK usage | Gateway env | Notes |
| --- | --- | --- | --- |
| OpenAI | Indirect only: OpenAI SDK pointed at LiteLLM base URL | `OPENAI_API_KEY` | Examples + README; package deps `openai` |
| Anthropic | None | `ANTHROPIC_API_KEY` | Scaffold models only |
| Google Gemini | None | `GEMINI_API_KEY` | Scaffold models only |
| xAI / Grok | None | `XAI_API_KEY` | Scaffold models only |
| Azure / Cohere / Groq | None | Optional stubs | No `model_list` entries |

---

## Planned semantic aliases (from plan §7.1)

| Alias | Intent | Plan consumers | Consumer status in this repo |
| --- | --- | --- | --- |
| `llm-fast` | Low latency / cost | Reference app + external | **No external apps**; keep only if reference workflow uses it |
| `llm-general` | Default chat | Reference app | **Real planned consumer** (reference workflow + examples migration) |
| `openai-general` | Explicit OpenAI A/B | Tests / smokes | **Real planned consumer** (provider smoke) |
| `anthropic-general` | Explicit Anthropic | Tests | **Real planned consumer** (provider smoke) |
| `gemini-general` | Explicit Gemini | Tests | **Real planned consumer** (provider smoke) |
| `grok-general` | Explicit xAI | Tests | **Real planned consumer** (provider smoke) |

Current scaffold names (`gpt-4o-mini`, `claude-sonnet`, …) are **vendor-ish bootstrap aliases**, not the stable application contract. They remain valid until WP7 renames/compiles aliases; do not add more vendor aliases without a consumer.

---

## Recommended alias set for next work packages

**Rule applied:** only aliases with a real consumer (examples + planned reference workflow + four `*-general` provider smokes). No Azure/Cohere/Groq. No unused “nice to have” names.

| Recommended alias | Maps from / to (initial lean) | Consumer | When |
| --- | --- | --- | --- |
| `llm-general` | Prefer `openai/gpt-4o-mini` (only model with live example/README demand today) | Examples, README smoke, reference workflow | WP7 + client migration |
| `openai-general` | `openai/gpt-4o-mini` or verified OpenAI id at pin time | Provider smoke (OpenAI) | WP6/WP7 |
| `anthropic-general` | `anthropic/claude-haiku-4-5-20251001` or verified id (cheap smoke lean) | Provider smoke (Anthropic) | WP6/WP7 |
| `gemini-general` | `gemini/gemini-3.5-flash` | Provider smoke (Gemini) | WP6/WP7 |
| `grok-general` | `xai/grok-3-mini` or verified id | Provider smoke (xAI) | WP6/WP7 |
| `llm-fast` | **Defer** unless reference workflow needs a second tier; candidate backends: `gpt-4o-mini` or `gemini-flash` | Only if WP11/WP13 explicitly needs distinct fast path | Optional later |

**Pruned (do not implement until a consumer appears):**

- Extra vendor aliases beyond smoke/reference needs (`gpt-4o`, `claude-sonnet`, `gemini-pro`, `grok` as app-facing names) — keep as temporary scaffold routes only if still useful for manual debugging; prefer collapsing to `*-general` + `llm-general` for apps.
- Azure / Cohere / Groq aliases — env stubs only, zero call sites.
- Fallback groups — disabled until stream/tools/structured compatibility proven (plan WP13).

**Example migration note:** After WP7, point `examples/*` and README default from `gpt-4o-mini` → `llm-general` (or keep `LITELLM_MODEL` override for smokes).

---

## Gaps and non-claims

| Claim boundary | What was / was not checked |
| --- | --- |
| Org-wide consumers | **Not checked** outside this worktree; no sibling repos in scope |
| Live provider reachability | **Not exercised** (docs-only WP) |
| Actual dated model ID validity | Scaffold IDs as written; verify at image pin / smoke time |
| Embeddings / Responses API | No call sites; plan defers day-one requirement |
| Streaming / tools / structured | No example usage; planned matrix WP13 |

---

## Sources (in-repo)

- `infra/llm-gateway/litellm-config.yaml` — model_list, callbacks
- `examples/python_client.py`, `examples/ts_client.ts` — sole runnable client call sites
- `infra/llm-gateway/.env.example`, compose files — provider env surface
- `README.md` — curl smoke model string
- `docs/superpowers/plans/2026-07-17-unified-litellm-langfuse-gateway.md` §7.1, WP1, WP6, WP7, WP11, WP13
- `AGENTS.md` — architecture ownership
