# Incident recovery — secrets and gateway state

Runbook for secret-related failures on the LiteLLM + Langfuse gateway.
**Never paste real secret values into tickets, chat, git, or this file.**

Related:

- Env template: `infra/llm-gateway/.env.example`
- Non-secret env knobs: `config/llm/environments/*.yaml`
- Image pin / rollback: `infra/llm-gateway/upgrade-notes.md`

---

## Secret hierarchy (quick reference)

| Secret | Scope | Rotation policy |
| --- | --- | --- |
| `LITELLM_SALT_KEY` | Encryption of proxy data at rest | **Permanent** — restore only, never casual rotate |
| `LITELLM_MASTER_KEY` | Admin bootstrap | Rotatable via admin procedure |
| `POSTGRES_PASSWORD` / `DATABASE_URL` | DB auth | Rotatable with coordinated app restart |
| Provider API keys | Proxy → provider | Per provider policy; apps never hold these |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | Telemetry | Rotatable in Langfuse project |
| `REDIS_PASSWORD` | Redis **container** auth when using `--redis-service` (not LiteLLM shared limits) | Rotatable with Redis restart |
| Virtual keys | App → proxy | Revoke/reissue per app (`uv run llg keys revoke`); prefer over master |

---

## `LITELLM_SALT_KEY` — permanent encryption secret

### Why it is special

LiteLLM uses the salt key to encrypt sensitive proxy state at rest (for example secrets stored for the proxy). It is effectively a **root encryption key** for that environment’s proxy database.

- **One salt per environment** (dev / staging / production are independent).
- **Identical salt** on every LiteLLM replica that shares the same Postgres.
- **Generate once**, store in the secret manager **and** in an offline escrow (printed sealed backup, HSM, or equivalent).
- **Do not** treat it like a password you rotate on a schedule.

### Failure: wrong or missing salt

| Symptom | Likely cause |
| --- | --- |
| Proxy fails to start or admin operations fail after deploy | Wrong salt injected vs the DB that holds encrypted rows |
| Decrypt errors / unreadable stored secrets | Salt changed or truncated; replica mismatch |
| Fresh empty database boots with a new salt | Expected only on **new** environments with no prior encrypted data |

Detection: proxy boot / admin logs (redact any residual secret material). Compare secret-manager version IDs and deploy env fingerprints — not the raw key material in tickets.

### Recovery procedure (lost or wrong salt)

**Goal:** restore the **original** salt that encrypted the existing database.  
**Do not** generate a new salt and point it at a DB that already has encrypted rows.

1. **Stop** rolling deploys / scale-down writes if decrypt failures are cascading.
2. **Locate offline escrow** for this environment’s `LITELLM_SALT_KEY` (sealed offline backup created at environment bootstrap).
3. **Confirm environment identity** (staging vs production DB endpoint, secret path, cluster). Never apply prod salt to staging DB or vice versa.
4. **Restore** the original salt into the secret manager (new secret version with the **same historical value**).
5. **Redeploy / restart** all LiteLLM replicas so every instance receives the restored value.
6. **Verify**:
   - `/health/liveliness` and readiness (Postgres reachable).
   - Admin path or a known virtual key still works (ids only in evidence; no raw keys).
   - No decrypt errors in proxy logs.
7. **If offline escrow is missing** and the salt cannot be recovered:
   - Treat encrypted-at-rest proxy secrets as **unrecoverable**.
   - Plan a **controlled rebuild**: new environment salt, new or wiped proxy DB state, re-create virtual keys / teams / budgets, re-inject provider keys, update app virtual keys.
   - Do **not** invent a “rotate salt in place” procedure against live encrypted rows without an explicit, tested LiteLLM migration path (out of scope unless documented upstream and rehearsed in staging).

### Bootstrap checklist (prevent the incident)

- [ ] Generate salt once: `uv run llg secrets generate`
- [ ] Store in secret manager under a clear path (e.g. `llm-gateway/{env}/LITELLM_SALT_KEY`)
- [ ] Write offline escrow; dual-control access; test restore from escrow in staging once
- [ ] Document who can retrieve escrow (on-call + security)
- [ ] Ensure multi-replica deploys inject the **same** secret version

---

## `LITELLM_MASTER_KEY` — admin only

- Used for bootstrap and admin APIs; **not** for application traffic.
- Applications use **virtual keys** (`LITELLM_VIRTUAL_KEY` or app-specific keys).
- **Rotation (high level):**
  1. Issue replacement master in secret manager.
  2. Restart / roll proxies with the new value.
  3. Re-authenticate admin tooling; revoke or retire the old master if the product supports invalidation.
  4. Confirm apps still use virtual keys only (master must not appear in app env).

Missing master key: Compose is configured to **fail boot** (`LITELLM_MASTER_KEY:?...`). That is intentional.

---

## Provider key leak or rotation

1. Rotate the provider key in the provider console.
2. Update proxy secret manager / `.env` only (never application env).
3. Restart or refresh proxy so new env is loaded.
4. Smoke a single alias for that provider; check Langfuse/export for errors without logging the key.
5. Audit spend for the incident window.

---

## Langfuse credential failure

- Expected: **LLM path still succeeds**; telemetry export may error or drop.
- Recovery: fix `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` / optional `LANGFUSE_OTEL_HOST`; confirm project region host.
- Do not dual-write generation telemetry from apps unless deliberately designed.

---

## Postgres unavailable

- Readiness should fail; instance out of load balancer; **no fail-open auth**.
- Restore DB from backup; re-attach same salt and master as that environment.
- After restore, verify virtual key ids still authenticate (not secret material in logs).

---

## Redis unavailable (when enabled)

- Multi-replica rate limits / routing state may be wrong or fail closed depending on config.
- Fix Redis; do not claim multi-replica correctness until shared state is healthy.
- Single-replica dev without Redis: omit Redis entirely (see `config/llm/environments/development.yaml`).

---

## Evidence hygiene

When filing incidents or evidence packs:

- Record **key ids**, secret **version ids**, deploy **revision**, timestamps.
- Redact master key, salt, provider keys, virtual key tokens, DB passwords.
- Prefer “salt restored from escrow version N; proxies rolled” over any key substring.
