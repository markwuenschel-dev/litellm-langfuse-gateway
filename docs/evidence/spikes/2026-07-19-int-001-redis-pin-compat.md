# Spike: INT-001 Redis control-state pin compatibility

**Date:** 2026-07-19  
**Status:** harness landed — **claim-neutral** (no production `--redis` claim)  
**Branch intent:** characterization only; product A′ profile waits on green evidence

## Contract (binding)

- Dual pinned LiteLLM + Postgres + Redis + fake upstream
- Outcomes: `green` | `silent-degrade` | `harness-unstable`
- `silent-degrade` → policy tests **exit nonzero** (not soft pass)
- Outage probes after bounded detection window (not first request after kill)
- Isolate Compose project; stop only harness Redis
- **Not** `LLG_LIVE`
- Native readiness/liveness **characterized**, not required red until product probe
- No change to operator `--redis` behavior/help/docs claims in this spike

## How to run

See `tests/runtime_pin/README.md`.

```text
$env:LLG_PIN_SPIKE = "1"
uv run pytest tests/runtime_pin -m pin_spike -v -s
```

## Evidence log

| Run | Date | Result | Notes |
| --- | --- | --- | --- |
| local Docker (Windows) | 2026-07-19 | **shared_limit=green** · **redis_outage=silent-degrade** · health char OK | Suite exit **nonzero** (policy fail on outage). Pin v1.92.0 serves `200` on both proxies after Redis stop + 15s window; native readiness stays `200` (`db:connected` only). Shared RPM across A/B holds while Redis up (`429` on B). |

### Log excerpts (redacted)

```text
PIN_SPIKE shared_limit outcome=green detail=B observed shared limit (status=429); statuses=[200, 429, 429]
PIN_SPIKE outage outcome=silent-degrade detail=pin served with local-only success while Redis stopped (A=200, B=200)
PIN_SPIKE native_health A liveliness=200 readiness=200 ready_body='{"status":"healthy","db":"connected"}'
PIN_SPIKE native_health B liveliness=200 readiness=200 ready_body='{"status":"healthy","db":"connected"}'
```

### Implication for product claim

**No distributed-limit claim** for `--redis` on this pin until a fail-closed path exists
(wrapper at limiter seam or pin/config that yields request-path 503 without local success).
Next decision: **wrapper-at-limiter-seam** vs **rename/downgrade** (`--redis-service`).

## Decision table

| Spike result | Next product change | Permitted claim |
| --- | --- | --- |
| Green | Land A′ profile, atomic Compose/K8s, preflight, Redis-aware readiness | `--redis` shared control state |
| Silent degrade | Wrapper at limiter seam **or** rename/downgrade | **No** distributed-limit claim |
| Harness unstable | Repair harness/runner | No claim until stable green |

## Related

- Integrity candidate INT-001 (parallel report 2026-07-19)
- Production flywheel item 1 — spike PR only
