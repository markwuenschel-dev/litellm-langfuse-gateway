# ADR 0007 — Map attribution to Langfuse native dimensions

## Status

Accepted (2026-07)

## Context

Langfuse is Cloud (ADR 0001); its dashboards can only group/filter by data the
gateway emits. Attribution previously rode as an **opaque `metadata` blob**, so the
dashboard builder could chart totals but not break down by service/env/model/etc.
Two concrete gaps:

- LiteLLM's classic `langfuse` callback reads **`trace_user_id`**, but the client
  sent `user_id` → the native **Users view was empty**.
- `service` / `environment` / `feature` / `model_alias` / `release` were never
  emitted as native **tags** / **release**, so no native grouping.

LiteLLM's callback promotes a fixed set of **reserved metadata keys** to native
Langfuse fields. The repo's own plan flagged this as "verify names against pin."

## Decision

Derive reserved Langfuse keys from the **vendor-neutral** `RequestMetadata` contract
in `src/llm_client/langfuse_metadata.py` (`langfuse_fields`), merged into the request
body `metadata` **after** contract validation. `GatewayClient` does this
automatically; raw-SDK callers replicate it (reference parity, not enforced).

Locked semantics:

- **`release` → `trace_release`, never `version`.** Langfuse `release` = app
  deployment; `version` = observation/component version. We do **not** emit `version`
  until a genuine component/operation/prompt version exists.
- **`trace_name` and `generation_name`** both set to `service:feature` (Metrics API v2
  is observation-centric — stable observation names are required).
- **Tags are low-cardinality only**: `env:`, `service:`, `feature:`, `model_alias:`.
  The model tag is `model_alias:` (distinct from Langfuse's native provided-model
  dimension). **Never** tag `request_id`, `release`, `session_id`, `user_id`,
  `trace_id` (cardinality + immutable-tag bloat).
- **`user_id` → `trace_user_id`**, and `user_id` is tightened to a pseudonymous
  `usr_<opaque>` format (`^usr_[A-Za-z0-9_-]{16,80}$`, fail-closed), derived upstream
  via keyed HMAC. It becomes a first-class per-user record (see privacy-and-retention).
- **Reserved-key collision guard** in `client.py`: refuse to send if the attribution
  contract ever emits a reserved key (invariant asserted disjoint in tests).
- **Verification, not assertion:** promotion on pin **v1.92.0** is UNPROVEN until
  `tests/integration/test_litellm_langfuse_pin.py` (Gate 3, `test-litellm` extra) and a
  live Cloud read-API check pass. Contingency: LiteLLM also accepts `langfuse_*`-prefixed
  request headers if a key isn't promoted.
- **Dashboards** ship as version-controlled portable **JSON** under
  `observability/langfuse/` (the stable artifact). Dashboard/widget **API/CLI/MCP**
  automation is explicitly **unstable** and optional; pin any CLI used.

## Consequences

- Dashboards can group cost/latency/tokens/errors by env, service, feature, model,
  release, session, user (subject to Metrics v2 limits: `userId`/`sessionId` are
  **filter-only**, not group-by — use native Users/Sessions views).
- **Breaking:** `user_id` values not matching `usr_<opaque>` are rejected. Callers
  must migrate to HMAC-derived pseudonyms.
- Raw-SDK callers get native dimensions only if they send the reserved keys — universal
  enforcement would require a proxy-side callback (not adopted here).
- Changing the reserved-key set or tag scheme requires updating this ADR + Gate 1/3.

## Stage 2 (gated, not shipped)

Native `trace_environment` (Langfuse Environment dimension, lowercase ≤40 chars) is
deferred: an unexpected trace param could make the callback drop the whole event.
Keep `env:*` as the safe baseline; promote only after Gate 3 proves the pin accepts it.
