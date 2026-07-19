# ADR 0004 — Redis overlay is service-only on current pin

## Status

Accepted (2026-07) — see also `docs/evidence/spikes/2026-07-19-int-001-*`

## Context

Pin-compatibility spike showed shared virtual-key RPM across two proxies while
Redis is healthy, but **silent local-only success** after Redis loss. A fail-closed
wrapper around LiteLLM’s limiter would be a new control-plane product.

## Decision

- CLI flag: `llg up --redis-service` (no ambiguous `--redis`).
- Compose overlay starts Redis **only**; does **not** inject `REDIS_*` into LiteLLM
  or claim shared Router / virtual-key limits.
- Reopen distributed control-state only with fail-closed pin proof **or** a
  separately approved gateway-policy design.

## Consequences

- Operators cannot infer multi-replica rate safety from starting Redis.
- Product docs and k8s sketch must not advertise shared limits on this pin.
