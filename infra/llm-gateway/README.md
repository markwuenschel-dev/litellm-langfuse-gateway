# LLM Gateway stack (`infra/llm-gateway`)

Canonical **LiteLLM Proxy + PostgreSQL** Compose stack for this repository.

Langfuse stays **Cloud** (set `LANGFUSE_*` in `.env`). Redis is an optional **service** via `compose.redis.yaml` / `llg up --redis-service` — container only; **no** shared-limit claim on the current LiteLLM pin.

## Layout

| File | Role |
| --- | --- |
| `compose.yaml` | LiteLLM + Postgres (canonical) |
| `compose.redis.yaml` | Optional Redis *service* overlay (no LiteLLM REDIS_* injection) |
| `litellm-config.yaml` | **Model registry SoT** (aliases, callbacks, router) |
| `.env.example` | Env template for **proxy** (copy to `.env`) |
| `.env.app.example` | Env template for **apps** (base URL + virtual key only) |
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
uv run llg up --redis-service        # + Redis container only (no shared-limit claim)
uv run llg health                    # /health/liveliness
uv run llg health --path /health/readiness   # Postgres-backed readiness
uv run llg down
uv run llg smoke --alias llm-general # skips unless LLG_LIVE=1 + virtual key
uv run llg reconcile-cost            # process stub; no invented numbers

# Virtual keys (admin; requires LITELLM_MASTER_KEY — never for apps)
uv run llg keys create --models openai-general --max-budget 10 --rpm 60 --key-alias ref-app-dev
uv run llg keys list
uv run llg keys revoke sk-...                 # POST /key/delete
uv run llg keys revoke sk-... --mode block    # soft-disable
```

**`llg` is the canonical ops surface.** `scripts/*` remain thin re-exports for older entrypoints
(`llg-validate-config`, `python scripts/healthcheck.py`, etc.). Prefer `uv run llg …`.

Staging overlay (non-secret posture): `compose.staging.yaml` (+ optional Redis).  
k8s sketch (pinned image, probes, secret refs): `k8s/README.md`.

### Virtual keys (operating notes)

| Concern | Practice |
| --- | --- |
| Auth for admin | `LITELLM_MASTER_KEY` via env (or `--master-key`); **never** printed by `llg` |
| App traffic | Use the virtual key printed once by `llg keys create` — store in a secret manager |
| Model ACL | `--models` is a comma-separated allow-list of **gateway aliases** |
| Budget / RPM | `--max-budget` (USD), `--rpm` → `rpm_limit`, optional `--tpm`, `--budget-duration` |
| Team | Optional `--team-id` (create teams in Admin UI / API first) |
| Inventory | `llg keys list` → `GET /key/list` (metadata only). If 404 on your pin, use Admin UI |
| Revoke | Default `delete`; `--mode block` soft-disables without hard delete |
| Do not | Commit virtual keys; put master key in app env; log full tokens in CI |

Live integration tests (skipped unless opted in):

```bash
# stack must already be up; LITELLM_MASTER_KEY must match the running proxy
$env:LLG_LIVE = "1"   # PowerShell; export LLG_LIVE=1 on bash
uv run pytest tests/integration/test_gateway_health.py
uv run pytest tests/integration/test_virtual_key_access.py
```

## Run

```bash
# From this directory
cp .env.example .env
# fill secrets (or: uv run llg secrets generate)
uv run llg up
# equivalent: docker compose -f compose.yaml up -d

# Optional Redis container (service only — not shared Router / virtual-key limits)
uv run llg up --redis-service
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
| `redis` | `localhost:6379` | Optional service only; **not** wired for shared limits on this pin |

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

## Langfuse Cloud (generation export)

LiteLLM exports per-call generation telemetry via the classic **`langfuse`** callback
in `litellm-config.yaml`:

```yaml
litellm_settings:
  success_callback: ["langfuse"]
  failure_callback: ["langfuse"]
```

Set these in `.env` (see `.env.example`). **Host must match the Langfuse project region**
(US keys against `https://cloud.langfuse.com` return 401 “invalid credentials / host”):

| Variable | Role |
| --- | --- |
| `LANGFUSE_PUBLIC_KEY` | Project public key (`pk-lf-…`) |
| `LANGFUSE_SECRET_KEY` | Project secret key (`sk-lf-…`) |
| `LANGFUSE_HOST` | US `https://us.cloud.langfuse.com` · EU `https://cloud.langfuse.com` |
| `LANGFUSE_OTEL_HOST` | Keep on the **same region host** as `LANGFUSE_HOST` if set |
| `LANGFUSE_BASE_URL` | Optional; same host (do not wrap the value in quotes in `.env`) |

Compose passes these through to the `litellm` service. After changing Langfuse env:

```bash
docker compose -f compose.yaml up -d --force-recreate litellm
```

**Missing or invalid Langfuse credentials must not break the LLM path** — fix telemetry
separately (proxy logs may show export errors; **never print secret key values**).

Use separate Langfuse projects (keys) for dev vs prod. App workflows may create root
traces and pass `metadata.trace_id` + `metadata.request_id` on gateway calls
(see `docs/llm-platform/app-wiring.md`, `config/llm/metadata-contract.schema.json`,
`examples/reference_workflow.py`).

Hermetic config check / live-gated probe:

```bash
uv run pytest tests/integration/test_langfuse_export.py -q
# Live optional: $env:LLG_LIVE="1"; $env:LITELLM_VIRTUAL_KEY="sk-..."; uv run pytest tests/integration/test_langfuse_export.py
```

## Application client (wiring)

**Runbook:** [docs/llm-platform/app-wiring.md](../../docs/llm-platform/app-wiring.md)  
**App env template:** [`.env.app.example`](./.env.app.example) (not this proxy `.env`)

```bash
# Virtual key only (never master key in apps) — must start with sk-
export LITELLM_VIRTUAL_KEY=sk-...
export LITELLM_BASE_URL=http://localhost:4000/v1
uv run python examples/reference_workflow.py
# OpenAI SDK thin example:
uv run --extra clients python examples/python_client.py
```

Python package: `src/llm_client` (`GatewayClient`, `RequestMetadata`, error types).
`LLG_DISALLOW_MASTER` defaults on — virtual key must not equal `LITELLM_MASTER_KEY`.
