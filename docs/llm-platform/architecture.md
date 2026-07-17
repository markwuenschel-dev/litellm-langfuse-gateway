# LLM platform architecture

Control-plane + observability split for LLM traffic in this repository.

## Ownership

| Plane | Owner | Responsibility |
| --- | --- | --- |
| Gateway control plane | **LiteLLM Proxy** | Provider credentials, model aliases, virtual keys, permissions, budgets, routing, rate limits, retries, fallbacks, normalized errors, consolidated spend |
| Observability / quality plane | **Langfuse** | Traces, nested spans, sessions, users, prompt versions, costs, latency, feedback, scores, datasets, evaluations |

```
Applications and agents
         │
         │ OpenAI-compatible requests
         ▼
    LiteLLM Proxy
      │       │
      │       ├── PostgreSQL: keys, teams, budgets, spend
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

**Do not invert ownership:** LiteLLM owns gateway policy; Langfuse owns product/quality observability.

## Model registry source of truth (YAML)

| Authority | Artifact | Role |
| --- | --- | --- |
| **Production model aliases / routes** | `infra/llm-gateway/litellm-config.yaml` | **Single reconciliation authority** |
| Runtime secrets & provider keys | Environment (`.env` / secret store) | Never raw keys in YAML |
| Virtual keys, teams, budgets, spend | PostgreSQL | Multi-tenant proxy state |
| Admin UI model edits / DB model rows | Not production SoT | Disabled for registry authority |

### Policy

1. **YAML is the source of truth** for model `model_name` aliases and `litellm_params` routes shipped to production.
2. Compose defaults **`STORE_MODEL_IN_DB=False`** so the proxy does not treat DB/UI model config as a second writable registry.
3. **Do not** treat Admin UI or DB model edits as authority for production aliases without an explicit ADR that flips SoT.
4. Postgres remains required for keys, teams, budgets, and spend — that is orthogonal to model-list authority.
5. Prefer reviewable config-as-code PRs over ad-hoc UI-only model changes.

### Layout (gateway)

```
infra/llm-gateway/
  compose.yaml           # LiteLLM + Postgres (canonical)
  compose.redis.yaml     # Optional Redis overlay
  litellm-config.yaml    # Model registry + callbacks (YAML SoT)
  .env.example
  README.md
  upgrade-notes.md       # Pin / upgrade log (WP3+)
```

Root `docker-compose.yml` / `docker-compose.redis.yml` are thin `include:` shims for root-level DX.

## Deployment defaults

| Component | Choice |
| --- | --- |
| LiteLLM Proxy | Self-hosted (Compose under `infra/llm-gateway/`) |
| PostgreSQL | Required for production proxy features |
| Langfuse | Cloud by default (not self-hosted unless residency/reg/cost force it) |
| Redis | Optional until multi-replica or shared rpm/tpm / routing state |

## Client contract

1. Call models through the LiteLLM OpenAI-compatible base URL (virtual key auth).
2. Instrument app-level traces in Langfuse (retrieval, tools, agents, sessions/users).
3. Rely on LiteLLM’s `langfuse_otel` callback for request-level token/cost/latency generation data.
