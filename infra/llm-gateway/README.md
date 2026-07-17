# LLM Gateway stack (`infra/llm-gateway`)

Canonical **LiteLLM Proxy + PostgreSQL** Compose stack for this repository.

Langfuse stays **Cloud** (set `LANGFUSE_*` in `.env`). Redis is optional via `compose.redis.yaml`.

## Layout

| File | Role |
| --- | --- |
| `compose.yaml` | LiteLLM + Postgres (canonical) |
| `compose.redis.yaml` | Optional Redis overlay |
| `litellm-config.yaml` | **Model registry SoT** (aliases, callbacks, router) |
| `.env.example` | Env template (copy to `.env`) |
| `upgrade-notes.md` | Image pins, bump/rollback procedure |

Root `docker-compose.yml` / `docker-compose.redis.yml` are thin `include:` shims for DX from the repo root.

## Pinned images (digest-required)

Production defaults use **tag + multi-arch index digest** (immutable). Do not use floating `latest`, `main`, or unpinned `main-stable`.

| Service | Default image |
| --- | --- |
| LiteLLM | `ghcr.io/berriai/litellm:v1.92.0@sha256:9ef6f45bc0104940571765e610c52a1d761b5ec85efcd193795281086ee61277` |
| Postgres | `postgres:16-alpine@sha256:57c72fd2a128e416c7fcc499958864df5301e940bca0a56f58fddf30ffc07777` |
| Redis (optional) | `redis:7-alpine@sha256:6ab0b6e7381779332f97b8ca76193e45b0756f38d4c0dcda72dbb3c32061ab99` |

- Override LiteLLM only with a fully pinned ref: `LITELLM_IMAGE=ghcr.io/berriai/litellm:<tag>@sha256:…`
- How to bump/rollback: [upgrade-notes.md](./upgrade-notes.md)
- CI fails if compose `image:` lines lack `@sha256:` or use floating tags without digests

## Model registry authority

**YAML is the source of truth** for production model aliases and provider routes (`litellm-config.yaml`).

- Compose defaults `STORE_MODEL_IN_DB=False`.
- Admin UI / DB model edits are **not** authority for production aliases.
- Never put raw API keys in YAML — use `os.environ/...` only.
- Postgres still holds keys, teams, budgets, and spend; that is separate from model-list authority.

See [docs/llm-platform/architecture.md](../../docs/llm-platform/architecture.md).

## Ops CLI (`llg`)

From **repo root** (preferred):

```bash
uv run llg --help
uv run llg secrets generate          # paste into .env (store salt offline)
uv run llg config validate           # model_list / no literal secrets
uv run llg up                        # docker compose -f infra/llm-gateway/compose.yaml up -d
uv run llg up --redis                # + compose.redis.yaml overlay
uv run llg health                    # /health/liveliness
uv run llg health --path /health/readiness   # Postgres-backed readiness
uv run llg down
```

`scripts/*` remain thin re-exports for older entrypoints (`llg-validate-config`, etc.).

Live integration health tests (skipped unless opted in):

```bash
# stack must already be up
$env:LLG_LIVE = "1"   # PowerShell; export LLG_LIVE=1 on bash
uv run pytest tests/integration/test_gateway_health.py
```

## Run

```bash
# From this directory
cp .env.example .env
# fill secrets (or: uv run llg secrets generate)
uv run llg up
# equivalent: docker compose -f compose.yaml up -d

# Optional Redis
uv run llg up --redis
# equivalent: docker compose -f compose.yaml -f compose.redis.yaml up -d
```

From **repo root** (same stack via shims):

```bash
cp infra/llm-gateway/.env.example .env   # or keep .env next to compose
docker compose up -d
docker compose -f docker-compose.yml -f docker-compose.redis.yml up -d
```

| Service | Default | Role |
| --- | --- | --- |
| `litellm` | `http://localhost:4000` | OpenAI-compatible proxy + admin UI |
| `postgres` | `localhost:5432` | Keys, teams, budgets, spend |
| `redis` | `localhost:6379` | Optional shared limits / routing state |

## Validate

```bash
# Config YAML
uv run llg config validate
# legacy: uv run python -m scripts.validate_config

# Compose (dummy required env)
# PowerShell / bash with env vars set:
docker compose -f infra/llm-gateway/compose.yaml config
```

## Health

```bash
curl -s http://localhost:4000/health/liveliness
curl -s http://localhost:4000/health/readiness
uv run llg health
uv run llg health --path /health/readiness
# legacy: uv run python scripts/healthcheck.py
```
