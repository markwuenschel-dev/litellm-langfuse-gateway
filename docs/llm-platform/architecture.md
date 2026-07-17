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
  .env.example           # Canonical secret/env template (no real secrets)
  README.md
  upgrade-notes.md       # Pin / upgrade log (WP3+)

config/llm/environments/
  development.yaml       # Non-secret env contract (timeouts, log level, redis_required)
  staging.yaml
  production.yaml

docs/llm-platform/
  incident-recovery.md   # Salt/master recovery; never regenerate salt against live encrypted DB
```

Root `docker-compose.yml` / `docker-compose.redis.yml` are thin `include:` shims for root-level DX.
Root `.env.example` is a DX copy that points at `infra/llm-gateway/.env.example`.

### Secret hierarchy (summary)

| Class | Examples | Policy |
| --- | --- | --- |
| Encryption root | `LITELLM_SALT_KEY` | **Permanent** per environment; offline escrow; restore only |
| Admin bootstrap | `LITELLM_MASTER_KEY` | Admin only; rotatable; never ship to apps |
| Provider credentials | `OPENAI_API_KEY`, … | Proxy env / secret manager only |
| Observability | `LANGFUSE_PUBLIC_KEY`, `SECRET_KEY`, `HOST`, `OTEL_HOST` | Cloud defaults; rotatable |
| App traffic | Virtual keys | Per app/env; not the master key |

Values never go in git or model YAML. See `infra/llm-gateway/.env.example` and `docs/llm-platform/incident-recovery.md`.

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

**In-repo client:** `src/llm_client` (`GatewayClient`, `RequestMetadata`, §7.3 error types).
Env: `LITELLM_BASE_URL`, `LITELLM_VIRTUAL_KEY`. Master key is rejected by default
(`LLG_DISALLOW_MASTER`, default on). Metadata schema: `config/llm/metadata-contract.schema.json`.
Reference path: `examples/reference_workflow.py` (alias `llm-general`).

**Langfuse env (proxy):** `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`,
optional `LANGFUSE_OTEL_HOST`. Pin uses `success_callback` / `failure_callback`:
`["langfuse_otel"]`. Telemetry failure must not fail the LLM path.

## Fallback policy (disabled)

**Router fallbacks are OFF by default.** `infra/llm-gateway/litellm-config.yaml` keeps
`router_settings.fallbacks` commented out.

**Rationale (semantic risk):** Cross-provider automatic failover can change tool schemas,
structured-output behavior, and cost attribution mid-workflow. Enabling fallbacks before
stream/tools/structured compatibility is proven for each hop is disallowed.

See `docs/llm-platform/provider-compatibility-matrix.md` (WP13 matrix; live cells unproven
without `LLG_LIVE`). Re-enable only via explicit config PR + evidence for a named pair.

## Ops and evidence

| Doc | Role |
| --- | --- |
| `operating-guide.md` | Production checklist, smoke identity |
| `application-migration.md` | Moving apps onto virtual keys |
| `privacy-and-retention.md` | PII / prompts / retention |
| `cost-reconciliation.md` | Spend accuracy process |
| `docs/evidence/` | Evidence index + honest milestone report |
| `uv run llg` | Canonical ops CLI (`scripts/*` are thin wrappers) |
