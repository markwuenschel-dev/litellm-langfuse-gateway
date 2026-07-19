# LiteLLM + Langfuse Gateway

Centralized **OpenAI-compatible LLM gateway** (LiteLLM) with **observability** (Langfuse Cloud).

Applications talk to one proxy with a **virtual key**. LiteLLM owns provider credentials, aliases, budgets, routing, and spend. Langfuse owns traces, sessions, costs, and quality feedback.

## Architecture

```
Applications / agents
         │  LITELLM_BASE_URL + LITELLM_VIRTUAL_KEY
         │  model: llm-general | openai-general | …
         ▼
    LiteLLM Proxy  (pinned image + Postgres)
      │       │
      │       ├── PostgreSQL: keys, teams, budgets, spend
      │       └── Langfuse callback: per-call generations
      │
      ├── OpenAI
      ├── Anthropic
      ├── Google Gemini
      └── xAI/Grok

Applications (optional)
         └── Langfuse app tracing
               ├── root request trace
               ├── retrieval / tool spans
               ├── session / user identity
               └── scores / evaluations
```

### Ownership

| Concern | Owner |
| --- | --- |
| Provider credentials, model aliases, virtual keys, ACL | LiteLLM |
| Budgets, rate limits, routing, retries, normalized errors | LiteLLM |
| Consolidated spend | LiteLLM + PostgreSQL |
| Per-call generation telemetry | LiteLLM → Langfuse (`success_callback: ["langfuse"]`) |
| App workflow traces, tools, retrieval, scores | Langfuse (app instrumentation) |

### Default deployment

| Component | Choice |
| --- | --- |
| LiteLLM | Self-hosted (Compose / your platform) |
| PostgreSQL | Required for keys, budgets, spend |
| Langfuse | **Cloud** (match `LANGFUSE_HOST` to project region: US `https://us.cloud.langfuse.com` or EU `https://cloud.langfuse.com`) |
| Redis | Optional **service** only (`--redis-service`); no shared-limit topology claimed on current pin |

Treat **`LITELLM_SALT_KEY` as permanent**. Pin images by **tag + digest** (see `infra/llm-gateway/compose.yaml`).

---

## Documentation map

| Doc | Purpose |
| --- | --- |
| [docs/llm-platform/app-wiring.md](docs/llm-platform/app-wiring.md) | **Wire an app** (env, keys, Python/TS, verification) |
| [docs/llm-platform/architecture.md](docs/llm-platform/architecture.md) | Ownership, YAML SoT, secret hierarchy |
| [docs/llm-platform/operating-guide.md](docs/llm-platform/operating-guide.md) | Day-2 ops, checklist |
| [docs/llm-platform/application-migration.md](docs/llm-platform/application-migration.md) | Migrate off direct provider keys |
| [docs/llm-platform/provider-onboarding.md](docs/llm-platform/provider-onboarding.md) | Provider / alias notes |
| [docs/llm-platform/incident-recovery.md](docs/llm-platform/incident-recovery.md) | Salt / master recovery |
| [infra/llm-gateway/README.md](infra/llm-gateway/README.md) | Compose stack details, pins |
| [AGENTS.md](AGENTS.md) | Rules for coding agents |

---

## Quick start

### Prerequisites

- Docker + Docker Compose  
- [uv](https://docs.astral.sh/uv/) (Python tooling / `llg` CLI)  
- Provider API keys you will use  
- Langfuse Cloud project (public + secret key), **region matched to host**

### 1. Proxy environment

```bash
cp infra/llm-gateway/.env.example infra/llm-gateway/.env
# or: cp .env.example .env   # root copy points at the same contract
```

In `infra/llm-gateway/.env` (or root `.env` used by Compose):

1. Set `LITELLM_MASTER_KEY`, `LITELLM_SALT_KEY`, `POSTGRES_PASSWORD` (generate with `uv run llg secrets generate`).
2. Set provider keys you need (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `XAI_API_KEY`, …).
3. Set Langfuse:
   - `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`
   - `LANGFUSE_HOST` **and** `LANGFUSE_OTEL_HOST` to the **same** region host (e.g. both `https://us.cloud.langfuse.com` for a US project).

Optional: if host Postgres already uses `5432`, set `POSTGRES_PORT=5433`.

### 2. Start the stack

```bash
# From repo root (preferred ops CLI)
uv sync --all-extras
uv run llg up

# Or Compose directly
docker compose -f infra/llm-gateway/compose.yaml up -d
# root shim: docker compose up -d
```

| Service | Host default | Role |
| --- | --- | --- |
| LiteLLM | `http://localhost:4000` | API + Admin UI |
| Postgres | `localhost:5432` (or `POSTGRES_PORT`) | Keys / spend |

```bash
uv run llg health
# or: curl -s http://localhost:4000/health/liveliness
```

### 3. Create a virtual key (apps use this, not the master key)

```bash
# Master key must be in the shell for admin API (not in the app)
export LITELLM_MASTER_KEY=sk-...   # from .env
export LITELLM_BASE_URL=http://localhost:4000

uv run llg keys create \
  --models llm-general,openai-general,gemini-general,grok-general,anthropic-general \
  --max-budget 10 \
  --rpm 60 \
  --key-alias local-dev
```

Copy the printed `sk-…` key once. Put it in the **app** env (see `.env.app.example`), never commit it.

### 4. Smoke (live)

```bash
export LLG_LIVE=1
export LITELLM_VIRTUAL_KEY=sk-...   # real virtual key, must start with sk-
export LITELLM_BASE_URL=http://localhost:4000/v1

uv run llg smoke --alias openai-general
# optional: gemini-general, grok-general, anthropic-general, llm-general
```

Confirm a generation in the Langfuse UI (same region/project as proxy keys).  
Spend / keys: Admin UI at `http://localhost:4000/ui` (master key).

### 5. Wire an application

Apps need **only**:

```env
LITELLM_BASE_URL=http://localhost:4000/v1
LITELLM_VIRTUAL_KEY=sk-...
LITELLM_MODEL=llm-general
```

Template: [`infra/llm-gateway/.env.app.example`](infra/llm-gateway/.env.app.example)  
Full guide: [`docs/llm-platform/app-wiring.md`](docs/llm-platform/app-wiring.md)

**Do not** put provider API keys or `LITELLM_MASTER_KEY` in the app.

```python
from llm_client import GatewayClient, GatewayConfig, RequestMetadata
import uuid, os

client = GatewayClient(GatewayConfig.from_env())
model = os.environ.get("LITELLM_MODEL", "llm-general")
meta = RequestMetadata(
    request_id=str(uuid.uuid4()),
    service="myapp",
    feature="chat",
    environment="development",
    release="dev",
    model_alias=model,
)
with client:
    result = client.chat(
        model=model,
        messages=[{"role": "user", "content": "Hello"}],
        metadata=meta,
    )
```

Or any OpenAI-compatible SDK with `base_url` / `baseURL` + virtual key. Samples: `examples/reference_workflow.py`, `examples/python_client.py`, `examples/ts_client.ts`.

---

## Model aliases

Configured in `config/llm/model-aliases.yaml` and `infra/llm-gateway/litellm-config.yaml` (YAML is source of truth).

| Alias | Role |
| --- | --- |
| `llm-general` | Default product chat (OpenAI-backed) |
| `openai-general` | Explicit OpenAI |
| `anthropic-general` | Explicit Anthropic |
| `gemini-general` | Explicit Gemini (`gemini-3.5-flash`) |
| `grok-general` | Explicit xAI / Grok |

Apps should prefer **aliases**, not raw vendor model strings. Fallbacks are **off** by default.

---

## Configuration

| Path | Purpose |
| --- | --- |
| `infra/llm-gateway/compose.yaml` | Canonical LiteLLM + Postgres |
| `infra/llm-gateway/litellm-config.yaml` | Models, callbacks, timeouts |
| `infra/llm-gateway/.env.example` | **Proxy** secrets template |
| `infra/llm-gateway/.env.app.example` | **App** env template |
| `config/llm/model-aliases.yaml` | Alias contract |
| `config/llm/metadata-contract.schema.json` | Request metadata schema |
| `docker-compose.yml` | Thin include shim → infra |

Never put raw API keys in YAML — only `os.environ/...`.

---

## Repository layout

```
.
├── AGENTS.md
├── README.md
├── infra/llm-gateway/          # Compose, litellm-config, .env templates
├── config/llm/                 # Aliases, metadata schema, env contracts
├── src/llg/                    # Ops CLI: uv run llg …
├── src/llm_client/             # App client (GatewayClient)
├── scripts/                    # Thin re-exports of llg helpers
├── examples/
│   ├── reference_workflow.py
│   ├── python_client.py
│   └── ts_client.ts
├── docs/llm-platform/          # Architecture, wiring, ops, …
├── tests/
├── pyproject.toml + uv.lock
└── package.json + pnpm-lock.yaml
```

---

## Development tooling

```bash
# Python
uv sync --all-extras
uv run ruff check .
uv run pytest
uv run llg config validate

# TypeScript examples
pnpm install
pnpm typecheck
```

CI on `main` runs ruff, pytest, typecheck, image-pin enforcement, and Compose validation.

---

## Production checklist

- [ ] Image digests pinned (not floating `latest` / `main-stable`)
- [ ] Postgres backups + durable volume
- [ ] `LITELLM_MASTER_KEY` + permanent `LITELLM_SALT_KEY` in a secret store
- [ ] Virtual keys per app × environment (budgets + model allow-lists)
- [ ] Langfuse keys match project region; host and OTEL host consistent
- [ ] Redis service only if needed for non-LiteLLM uses; multi-replica shared limits require fail-closed design (not supplied by `--redis-service`)
- [ ] TLS + private network for the proxy
- [ ] Apps have no provider keys / no master key
- [ ] Health checks and log aggregation

See [operating-guide.md](docs/llm-platform/operating-guide.md).

---

## License

MIT — see [LICENSE](LICENSE).
