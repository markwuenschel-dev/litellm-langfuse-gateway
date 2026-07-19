# Agent instructions — litellm-langfuse-gateway

Instructions for coding agents working in this repository.

## What this repo is

A **control-plane + observability** stack for LLM traffic:

| Plane | Owner | Responsibility |
| --- | --- | --- |
| Gateway control plane | **LiteLLM Proxy** | Provider credentials, model aliases, virtual keys, permissions, budgets, routing, rate limits, retries, fallbacks, normalized errors, consolidated spend |
| Observability / quality plane | **Langfuse** | Traces, nested spans, sessions, users, prompt versions, costs, latency, feedback, scores, datasets, evaluations |

Deployment target:

- **Self-hosted** LiteLLM + PostgreSQL  
- **Langfuse Cloud** (not self-hosted unless residency/regulatory/cost force it)  
- **Redis service** optional (`--redis-service`); no shared rate-limit topology claimed on current pin

## Architecture (do not invert ownership)

```
Applications and agents
         │ OpenAI-compatible + virtual key
         ▼
    LiteLLM Proxy
      │       │
      │       ├── PostgreSQL: keys, teams, budgets, spend
      │       └── Langfuse callback (classic `langfuse`): generations
      │
      ├── OpenAI / Anthropic / Gemini / xAI

Applications
         └── Langfuse app tracing (root, tools, retrieval, scores)
```

**LiteLLM** owns gateway policy. **Langfuse** owns product/quality observability.

Application code should:

1. Call models through the LiteLLM OpenAI-compatible base URL with a **virtual key only** — see `docs/llm-platform/app-wiring.md`.
2. Instrument app-level traces for multi-step workflows (retrieval, tools, agents, sessions/users).
3. Rely on the proxy Langfuse success/failure callback for **generation** telemetry — do not dual-write the same generation unless deliberate.

## Hard rules

1. **Never commit secrets.** Use gitignored `.env` from `infra/llm-gateway/.env.example`. Apps use `infra/llm-gateway/.env.app.example`.
2. **`LITELLM_SALT_KEY` is permanent.** Generate once per environment; offline escrow; never rotate casually.
3. **Pin images by digest** in Compose (tag + `@sha256:…`). No floating `latest` / unpinned `main-stable` in production artifacts. CI enforces digests.
4. **PostgreSQL is required** for virtual keys, teams, budgets, spend.
5. **Redis service is optional** (`llg up --redis-service`). It starts a container only — **no** shared Router / virtual-key limit topology is claimed on the current pin (silent-degrade evidence). Reopen distributed controls only with fail-closed pin proof or an approved gateway-policy design.
6. **Do not self-host Langfuse by default.**
7. **YAML is model-registry SoT** (`infra/llm-gateway/litellm-config.yaml`). `STORE_MODEL_IN_DB=False`. No raw keys in YAML — `os.environ/...` only.
8. **OpenAI-compatible surface is the app contract.** Prefer stable aliases (`llm-general`, …).
9. **Master key is admin-only.** Apps use virtual keys (`LLG_DISALLOW_MASTER` default on).
10. **Langfuse region:** `LANGFUSE_HOST` and `LANGFUSE_OTEL_HOST` must match the project region (US vs bare `cloud.langfuse.com` EU). Never print secret key values in logs or chat.
11. **Never claim production readiness** without pins, Postgres, secrets hygiene, and a verified smoke + telemetry path.

## Layout

```
infra/llm-gateway/       # Compose, litellm-config, .env.example, .env.app.example
config/llm/              # model-aliases, metadata schema, environments/*
src/llg/                 # Ops CLI: uv run llg …
src/llm_client/          # App GatewayClient + metadata + errors
scripts/                 # Thin re-exports of llg
examples/                # reference_workflow, python/ts clients
docs/llm-platform/       # Architecture, app-wiring, ops, …
docs/adr/                # Architecture decision records (policy flips)
tests/                   # unit + live-gated integration
```

## Common tasks

| Goal | Approach |
| --- | --- |
| Local stack | `cp infra/llm-gateway/.env.example infra/llm-gateway/.env`, fill keys, `uv run llg up` |
| Health | `uv run llg health` |
| Secrets | `uv run llg secrets generate` |
| Validate config | `uv run llg config validate` |
| Virtual keys | `uv run llg keys create --models llm-general …` (needs master in shell) |
| Live smoke | `LLG_LIVE=1` + real `LITELLM_VIRTUAL_KEY` (`sk-…`) → `uv run llg smoke --alias …` |
| Wire an app | `docs/llm-platform/app-wiring.md` + `.env.app.example` |
| Add alias | Edit `config/llm/model-aliases.yaml` + `litellm-config.yaml`; keep in sync; validate |
| Langfuse | Proxy: `LANGFUSE_*` + classic `langfuse` callbacks in config; recreate litellm after env change |
| Redis service | `uv run llg up --redis-service` or redis compose overlay (container only; no shared-limit claim) |

## Tooling

- **Python:** `uv sync --all-extras`; `uv run ruff` / `uv run pytest` / `uv run llg …`
- **Node:** `pnpm install` / `pnpm typecheck` (examples only)

## What not to do

- Put provider keys or master key in app env or browser code.
- Put secrets in YAML, fixtures, or Langfuse metadata.
- Invent aliases without a consumer.
- Enable multi-provider fallbacks without compatibility evidence.
- Print full API keys in terminal diagnostics or user-facing chat.
- Claim “done” from docs alone — require exercised verification when asserting live behavior.

## Verification bar

Before claiming a change works:

1. `uv run llg config validate` (or equivalent) passes.
2. Compose validates (`docker compose … config`).
3. Hermetic tests pass; live claims need `LLG_LIVE` evidence.
4. No secrets in the diff.
5. README / AGENTS / app-wiring stay aligned when env vars, aliases, or callbacks change.
