# LiteLLM + Langfuse Gateway

Centralized **OpenAI-compatible LLM gateway** (LiteLLM) with **observability and quality** (Langfuse).

Applications and agents talk to one proxy. LiteLLM owns credentials, virtual keys, budgets, routing, and spend. Langfuse owns traces, sessions, evaluations, and product-quality feedback.

## Architecture

```
Applications and agents
         │
         │ OpenAI-compatible requests
         ▼
    LiteLLM Proxy
      │       │
      │       ├── PostgreSQL: keys, teams, budgets, spend, model configuration
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

### Ownership split

| Concern | Owner |
| --- | --- |
| Provider credentials, model aliases, virtual keys, model permissions | LiteLLM |
| Budgets, routing, rate limits, retries, fallbacks, normalized errors | LiteLLM |
| Consolidated spend tracking | LiteLLM (+ Postgres) |
| Request-level token / cost / latency telemetry | LiteLLM → Langfuse (`langfuse_otel`) |
| App traces, retrieval/tools, agents, sessions, users, scores, datasets | Langfuse (app instrumentation) |

### Deployment recommendation (initial)

| Component | Choice | Why |
| --- | --- | --- |
| LiteLLM Proxy | **Self-hosted** | Control plane for keys, budgets, routing |
| PostgreSQL | **Self-hosted** (or managed) | Required for keys, teams, config, spend |
| Langfuse | **Cloud** | Avoid ops burden; Compose is for local/low-scale only |
| Redis | **Later** | Add when multi-replica or distributed rate limits / routing state |

LiteLLM production guidance: pin releases; treat **`LITELLM_SALT_KEY` as a permanent encryption secret**; use Postgres for multi-tenant proxy state; use Redis across multiple proxy instances.

**Do not self-host Langfuse initially** unless data-residency, regulatory, or cost requirements justify the extra infrastructure. Upstream Docker Compose for Langfuse is aimed at local or low-scale use and lacks HA, horizontal scaling, and built-in backup.

## Quick start

### Prerequisites

- Docker + Docker Compose
- Provider API keys you intend to use (OpenAI, Anthropic, Gemini, xAI, …)
- A [Langfuse Cloud](https://cloud.langfuse.com) project (public + secret key)

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

1. Generate strong values for `LITELLM_MASTER_KEY`, `LITELLM_SALT_KEY`, and `POSTGRES_PASSWORD`.
2. Set provider keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `XAI_API_KEY`, …).
3. Set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_HOST` (Cloud host).

> **Salt key:** generate once and store offline. Changing `LITELLM_SALT_KEY` later can make encrypted proxy data unreadable.

```bash
# Example secret generation (Python)
python -c "import secrets; print('sk-' + secrets.token_urlsafe(32))"
```

Or use `python scripts/generate_secrets.py`.

### 2. Start the stack

```bash
docker compose up -d
```

Services:

| Service | Default | Role |
| --- | --- | --- |
| `litellm` | `http://localhost:4000` | OpenAI-compatible proxy + admin UI |
| `postgres` | `localhost:5432` | Keys, teams, budgets, spend, config |

Optional Redis (multi-replica / shared limits):

```bash
docker compose -f docker-compose.yml -f docker-compose.redis.yml up -d
```

### 3. Smoke test

```bash
# Liveness
curl -s http://localhost:4000/health/liveliness

# Chat completion (use a virtual key from the UI, or master key only for admin bootstrapping)
curl -s http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Say hello in one word."}]
  }'
```

Prefer **virtual keys** (scoped, budgeted) for applications. Reserve the master key for administration.

### 4. Point clients at the gateway

**Python (OpenAI SDK):**

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-...",  # LiteLLM virtual key
    base_url="http://localhost:4000/v1",
)
```

**TypeScript:**

```ts
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.LITELLM_VIRTUAL_KEY,
  baseURL: "http://localhost:4000/v1",
});
```

See `examples/` for runnable snippets.

## Configuration

| Path | Purpose |
| --- | --- |
| `config/litellm_config.yaml` | Models, aliases, callbacks, router settings |
| `.env` | Secrets and runtime env (not committed) |
| `docker-compose.yml` | LiteLLM + Postgres |
| `docker-compose.redis.yml` | Optional Redis overlay |

Model list entries reference provider keys via environment variables — never put raw API keys in YAML.

Langfuse wiring uses LiteLLM’s success/failure callbacks and OTEL settings so each proxied call emits generation-level telemetry. Application code should still create Langfuse traces for retrieval, tools, agents, and session/user identity.

## Repository layout

```
.
├── AGENTS.md                 # Instructions for coding agents
├── config/
│   └── litellm_config.yaml   # Proxy configuration
├── docker-compose.yml
├── docker-compose.redis.yml
├── examples/
│   ├── python_client.py
│   └── ts_client.ts
├── scripts/
│   ├── generate_secrets.py
│   └── healthcheck.py
├── .github/workflows/ci.yml
├── pyproject.toml            # Python tooling
└── package.json              # JS/TS examples & scripts
```

## Development tooling

**Python** ([uv](https://docs.astral.sh/uv/)):

```bash
uv sync --all-extras
uv run ruff check .
uv run pytest
```

**Node / TypeScript** ([pnpm](https://pnpm.io/)):

```bash
pnpm install
pnpm typecheck
```

**CI** (GitHub Actions) uses `uv` + `pnpm` lockfiles for lint, Python tests, typecheck, and Compose config validation on push/PR to `main`.

## Production checklist

- [ ] Pin LiteLLM image to a specific release tag
- [ ] Postgres with backups and durable volume
- [ ] Unique `LITELLM_MASTER_KEY` and permanent `LITELLM_SALT_KEY` in a secret store
- [ ] Virtual keys per app/team with budgets and model allow-lists
- [ ] Langfuse Cloud keys restricted and rotated as policy requires
- [ ] Redis when running >1 proxy replica
- [ ] TLS termination and network isolation in front of the proxy
- [ ] Health checks and log aggregation
- [ ] Fallback model groups tested under provider failure

## License

MIT — see [LICENSE](LICENSE).
