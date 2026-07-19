# Operating guide (WP17 / WP18)

Day-2 operations for the LiteLLM + Langfuse gateway. Canonical stack: `infra/llm-gateway/`. Ops surface: **`uv run llg`** (scripts under `scripts/` are thin wrappers only).

## Production checklist

| # | Item | Config / artifact | Verified? |
| --- | --- | --- | --- |
| 1 | Pinned image digests (LiteLLM, Postgres, Redis) | `compose.yaml`, `compose.redis.yaml`, `upgrade-notes.md` | Pin **configured**; live deploy **unproven** here |
| 2 | `LITELLM_MODE=PRODUCTION` (staging/prod) | Set in runtime env / Compose; environments YAML is **docs checklist only** (ADR 0005) | Configured in env / Compose |
| 3 | JSON logs, non-verbose | `litellm-config.yaml`: `json_logs: true`, `set_verbose: false` | Configured |
| 4 | `request_timeout: 600` | `litellm_settings.request_timeout` + env YAMLs | Configured |
| 5 | `num_workers: 1`; scale out replicas | `compose.yaml` command; k8s sketch | Configured |
| 6 | `proxy_batch_write_at` / DB write batching | Notes in `production.yaml` + `upgrade-notes.md` (enable when pin supports / load needs) | Guidance only until live-tuned |
| 7 | Redis service optional; **no** shared-limit topology on current pin | `compose.redis.yaml` (service only); spike evidence | Service overlay only; distributed controls **not** claimed |
| 8 | Salt + master in secret manager; salt offline escrow | `incident-recovery.md` | Process documented; escrow **ops-owned** |
| 9 | Admin UI not public without SSO / network control | `production.yaml` `admin_ui.public: false` | Policy; network enforcement **unproven** here |
| 10 | Postgres backups + restore drill | `incident-recovery.md` | Documented; drill **unproven** without live DB |
| 11 | Upgrade / rollback via prior digest | `upgrade-notes.md` | Procedure documented |
| 12 | YAML model registry SoT (`STORE_MODEL_IN_DB=False`) | compose + config | Configured |
| 13 | Langfuse outage must not fail LLM path | callbacks + policy | Unit/hermetic only; live outage **UNPROVEN** |
| 14 | Apps use virtual keys only | `llm_client`, `LLG_DISALLOW_MASTER` | Hermetic unit tests pass |

## Daily / weekly ops

```bash
uv run llg config validate
uv run llg health
uv run llg health --path /health/readiness
uv run llg keys list          # needs master; metadata only
```

| Cadence | Action |
| --- | --- |
| Daily | Readiness health; error rate / 5xx from proxy logs |
| Weekly | Spend by key/team; budget headroom; Langfuse traces present for sample traffic |
| As needed | App wiring checklist: `docs/llm-platform/app-wiring.md` |
| Per release | Pin bump procedure; smoke matrix (`LLG_LIVE=1`); cost recon if pricing changed |
| Quarterly | Salt escrow existence check; Postgres restore drill |

## Staging vs production

| Concern | Staging | Production |
| --- | --- | --- |
| Compose overlay | `infra/llm-gateway/compose.staging.yaml` | Same base + prod secret store |
| Env contract | `config/llm/environments/staging.yaml` | `production.yaml` |
| Smoke identity | Low budget, restricted models | Same pattern; stricter network |
| Redis | Required if replicas > 1 | Required if replicas > 1 |
| Langfuse | Cloud project (staging keys) | Cloud project (prod keys); never mix |

## Smoke identity (staging)

```bash
uv run llg keys create \
  --models llm-general,openai-general \
  --max-budget 5 \
  --rpm 30 \
  --key-alias staging-smoke
# Store virtual key in staging secret store — never commit
export LLG_LIVE=1 LITELLM_VIRTUAL_KEY=sk-...
uv run llg smoke --alias llm-general
```

## Alerting hooks

LiteLLM supports optional alerting (e.g. Slack webhook) via proxy config when enabled for the pin. This repo does **not** enable webhooks by default (no secrets in YAML). Document the webhook secret name in your secret manager and wire it in the deploy overlay only.

## TLS / ingress

TLS terminates at the platform ingress (or managed load balancer). Compose local binds plain HTTP on `localhost:4000`. k8s sketch: `infra/llm-gateway/k8s/README.md`. Do not expose Admin UI on the public internet without SSO and network policy.

## Related docs

| Doc | Topic |
| --- | --- |
| `architecture.md` | Ownership, YAML SoT, fallbacks disabled |
| `incident-recovery.md` | Salt, master, Postgres, key recovery |
| `provider-onboarding.md` | Adding aliases / providers |
| `provider-compatibility-matrix.md` | Stream/tools/structured status |
| `cost-reconciliation.md` | Spend accuracy process |
| `application-migration.md` | Moving apps onto the gateway |
| `privacy-and-retention.md` | PII, prompts, retention |
| `docs/evidence/` | Evidence index + milestone honesty |
