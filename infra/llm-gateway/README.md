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
| `upgrade-notes.md` | Release/pin notes (WP3+) |

Root `docker-compose.yml` / `docker-compose.redis.yml` are thin `include:` shims for DX from the repo root.

## Model registry authority

**YAML is the source of truth** for production model aliases and provider routes (`litellm-config.yaml`).

- Compose defaults `STORE_MODEL_IN_DB=False`.
- Admin UI / DB model edits are **not** authority for production aliases.
- Never put raw API keys in YAML — use `os.environ/...` only.
- Postgres still holds keys, teams, budgets, and spend; that is separate from model-list authority.

See [docs/llm-platform/architecture.md](../../docs/llm-platform/architecture.md).

## Run

```bash
# From this directory
cp .env.example .env
# fill secrets (or: uv run python ../../scripts/generate_secrets.py)
docker compose -f compose.yaml up -d

# Optional Redis
docker compose -f compose.yaml -f compose.redis.yaml up -d
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
uv run python -m scripts.validate_config

# Compose (dummy required env)
# PowerShell / bash with env vars set:
docker compose -f infra/llm-gateway/compose.yaml config
```

## Health

```bash
curl -s http://localhost:4000/health/liveliness
uv run python scripts/healthcheck.py
```
