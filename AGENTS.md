# Agent instructions — litellm-langfuse-gateway

Instructions for coding agents working in this repository.

## What this repo is

A **control-plane + observability** stack for LLM traffic:

| Plane | Owner | Responsibility |
| --- | --- | --- |
| Gateway control plane | **LiteLLM Proxy** | Provider credentials, model aliases, virtual keys, permissions, budgets, routing, rate limits, retries, fallbacks, normalized errors, consolidated spend |
| Observability / quality plane | **Langfuse** | Traces, nested spans, sessions, users, prompt versions, costs, latency, feedback, scores, datasets, evaluations |

Initial deployment target:

- **Self-hosted** LiteLLM + PostgreSQL
- **Langfuse Cloud** (not self-hosted unless residency/regulatory/cost force it)
- **Redis** only when running multiple LiteLLM replicas or needing distributed rate-limiting / routing state

## Architecture (do not invert ownership)

```
Applications and agents
         │
         │ OpenAI-compatible requests
         ▼
    LiteLLM Proxy
      │       │
      │       ├── PostgreSQL: keys, teams, budgets, spend, model config
      │       └── Langfuse OTEL callback: per-call telemetry
      │
      ├── OpenAI
      ├── Anthropic
      ├── Google Gemini
      └── xAI/Grok

Applications and agents
         │
         └── Langfuse application tracing
               ├── request trace
               ├── retrieval/tool spans
               ├── LiteLLM generations
               ├── user and session identity
               └── scores/evaluations
```

**LiteLLM** owns gateway policy. **Langfuse** owns product/quality observability. Application code should:

1. Call models through the LiteLLM OpenAI-compatible base URL (virtual key auth).
2. Instrument app-level traces in Langfuse (retrieval, tools, agents, sessions/users).
3. Rely on LiteLLM’s `langfuse_otel` callback for request-level token/cost/latency generation data — do not duplicate that in app code unless you have a deliberate dual-write reason.

## Hard rules

1. **Never commit secrets.** Use `.env` (gitignored) from `.env.example`. Provider keys, `LITELLM_MASTER_KEY`, `LITELLM_SALT_KEY`, DB passwords, and Langfuse keys stay local or in a secret store.
2. **`LITELLM_SALT_KEY` is permanent.** It encrypts data at rest for the proxy. Changing it can brick decryptable secrets. Treat it like a root encryption key; generate once, store offline, never rotate casually.
3. **Pin LiteLLM image tags.** Prefer a specific release (e.g. `ghcr.io/BerriAI/litellm:main-v1.x.x`) over floating `latest` / unpinned `main` in anything beyond local experimentation.
4. **PostgreSQL is required for production proxy features** (virtual keys, teams, budgets, spend, UI-backed config). Do not “simplify” production by removing the DB.
5. **Redis is optional until multi-instance.** Single-replica local/dev can omit Redis. Multi-replica or shared rpm/tpm / routing state requires Redis; prefer `redis_host` / `redis_port` / `redis_password` over a single `redis_url` per LiteLLM production guidance.
6. **Do not self-host Langfuse by default.** Compose Langfuse only if the user explicitly opts in for residency, regulation, or cost. Cloud is the default observability backend.
7. **Config is code.** Model aliases, fallbacks, and callback wiring live under `config/`. Prefer reviewable YAML over ad-hoc UI-only state when both are available.
8. **OpenAI-compatible surface is the contract.** Downstream apps should use standard chat/completions (and related) clients pointed at this proxy. Avoid baking provider-specific SDKs into first-party apps unless necessary.

## Layout

```
config/                 # LiteLLM proxy config (models, callbacks, router)
docker-compose.yml      # LiteLLM + PostgreSQL (default stack)
docker-compose.redis.yml# Optional Redis overlay for multi-replica / shared limits
examples/               # Minimal client examples (Python + TypeScript)
scripts/                # Ops helpers (secrets, health)
.github/workflows/      # CI
```

## Common tasks

| Goal | Approach |
| --- | --- |
| Local stack up | Copy `.env.example` → `.env`, fill keys, `docker compose up -d` |
| Add a model alias | Edit `config/litellm_config.yaml` `model_list`; keep provider keys in env |
| Enable Redis | `docker compose -f docker-compose.yml -f docker-compose.redis.yml up -d` and set Redis env vars |
| Wire Langfuse | Set `LANGFUSE_*` in `.env`; ensure `success_callback` / OTEL settings in config |
| Health check | `scripts/healthcheck` or `GET /health` / `/health/liveliness` on the proxy |
| CI | Push/PR runs lint + config validation workflow |

## Python / Node tooling

- **Python** (`pyproject.toml` + `uv.lock`): config validation helpers, scripts, optional thin client utilities. Use **`uv`** (`uv sync --all-extras`); `uv run ruff` + `uv run pytest` are the default quality gates.
- **Node** (`package.json` + `pnpm-lock.yaml`): lightweight TS examples and script runners. Use **`pnpm`** (`pnpm install`, `pnpm typecheck`). Not a full application monorepo — keep it thin.

## What not to do

- Do not put provider API keys in `config/*.yaml`; reference `os.environ/...` only.
- Do not document or implement exploit paths against the proxy, master key, or salt key.
- Do not expand scope into a full agent framework, RAG product, or self-hosted Langfuse HA cluster unless that is an explicit task.
- Do not claim production readiness without: pinned image, Postgres, master + salt keys, secrets management, and a health/smoke path.

## Verification bar

Before claiming a change works:

1. Config YAML still parses / validates.
2. Compose files are valid (`docker compose config`).
3. No secrets appear in the diff.
4. README / AGENTS stay aligned if architecture or env vars change.
