# Privacy and retention (WP18)

Policy for prompts, completions, identifiers, and telemetry retained by the gateway and Langfuse. **Platform defaults; legal/security may tighten.**

## Data classes

| Class | Examples | Default handling |
| --- | --- | --- |
| Secrets | Provider keys, master/salt, virtual keys, `Authorization` | Never in git, logs, metadata, Langfuse attributes, or fixtures |
| Auth material in metadata | Keys named `authorization`, `api_key`, `token`, `secret`, … | Rejected by `llm_client.metadata` contract |
| Pseudonymous IDs | `user_id`, `session_id` (opaque) | Allowed when non-PII; do not put email/MRN/name in these fields |
| Direct PII | Email, legal name, phone, MRN, exact address | **Forbidden** in metadata and preferred forbidden in prompts unless a written privacy approval exists for that product |
| Prompts / completions | Chat content | Subject to Langfuse + provider retention; minimize; redact where possible |
| Operational | `request_id`, `service`, `feature`, `environment`, `release`, `model_alias` | Required for attribution; non-sensitive by design |

## Metadata contract

- Schema: `config/llm/metadata-contract.schema.json`
- Enforced in-process: `src/llm_client/metadata.py` (forbidden keys, secret-shaped values, max string length 128)
- `user_id` / `session_id`: treat as **pseudonymous**; do not encode raw PII

## Prompt / response recording

| Store | What may be retained | Control |
| --- | --- | --- |
| LiteLLM / Postgres | Spend, key/team metadata, request logs if enabled | Prefer minimal request logging in prod; no secrets |
| Langfuse Cloud | Traces, generations (token/cost/latency), app spans | Project retention settings in Langfuse Cloud UI; regional host via `LANGFUSE_HOST` / `LANGFUSE_OTEL_HOST` |
| Provider | Per provider ToS / retention | Outside this repo; minimize sensitive content |

**DoD #12:** Prompt/response recording must follow this policy. Live proof that production projects enforce retention windows is **ops-owned** and **unproven** in this milestone without Cloud project access.

## Retention defaults (proposal)

| System | Proposal | Status |
| --- | --- | --- |
| Langfuse Cloud traces | Align with org security (e.g. 30–90 days) | Set in Langfuse project; not enforced by this repo |
| LiteLLM spend logs | Keep for cost recon + audit (e.g. 90 days) | Postgres backup/retention is ops-owned |
| Virtual keys | Revoke on offboarding; no key material in git | `llg keys revoke` |
| Evidence under `docs/evidence/` | Redacted only; no live secrets | Process |

## Langfuse and the LLM path

Observability failure must **not** fail primary LLM traffic by default (`langfuse.required_for_llm_path: false` in env contracts). Privacy incident response for telemetry leakage is separate from availability: rotate Langfuse keys; scrub project data per Langfuse tools; revoke compromised virtual keys.

## Related

- `config/llm/metadata-contract.schema.json`
- `docs/llm-platform/incident-recovery.md`
- `docs/evidence/README.md` (what may be committed as evidence)
