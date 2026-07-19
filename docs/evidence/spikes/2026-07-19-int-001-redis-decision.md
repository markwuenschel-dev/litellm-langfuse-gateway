# INT-001 product decision: downgrade to `--redis-service`

**Date:** 2026-07-19  
**Spike evidence:** [2026-07-19-int-001-redis-pin-compat.md](./2026-07-19-int-001-redis-pin-compat.md)  
**Choice:** **Downgrade** (not wrapper)

## Why not a wrapper

- LiteLLM owns gateway limiter/routing policy; a custom fail-closed layer around the internal limiter is a new control-plane product.
- Race-safety, OpenAI-compatible errors, and outage semantics are permanent maintenance.
- No current multi-replica consumer justifies that surface.

## Contract (shipped)

| Item | Behavior |
| --- | --- |
| CLI | `llg up --redis-service` / `llg down --redis-service` — **no** `--redis` alias |
| Overlay | Starts Redis container; **no** `REDIS_*` injection into LiteLLM |
| Docs / k8s | No shared-limit topology claimed on current pin |
| Reopen | Only with fail-closed pin proof **or** separately approved gateway-policy design |

## Related

- Integrity INT-001; production flywheel G2 ops batch
