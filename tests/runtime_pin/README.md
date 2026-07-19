# Runtime pin spikes

Docker integration suites that characterize the **pinned** LiteLLM image.
These are **not** `LLG_LIVE` (no real provider credentials).

## INT-001 — Redis control-state pin compatibility

**Claim-neutral.** This spike does **not** change `llg up --redis`, production
config profiles, help text, or documentation claims about distributed limits.

### What it runs

- Two LiteLLM proxies (production image digest)
- Shared Postgres + Redis
- Deterministic fake OpenAI-compatible upstream
- Low-RPM virtual key through both proxies
- Redis stop (project container only) after a bounded detection window
- Assertions with three outcomes:
  - `green` — invariants hold
  - `silent-degrade` — harness OK, pin violated invariant → **pytest fails**
  - `harness-unstable` — scenario could not be established → **pytest fails**

Native readiness/liveness after outage are **recorded**, not required to go red
(product PR owns Redis-aware readiness).

### Run

```bash
# PowerShell
$env:LLG_PIN_SPIKE = "1"
uv run pytest tests/runtime_pin -m pin_spike -v -s
```

```bash
# bash
export LLG_PIN_SPIKE=1
uv run pytest tests/runtime_pin -m pin_spike -v -s
```

Requires Docker with compose. Uses unique project name `llg-pin-<id>` and
`finally` teardown (`down -v`). Does not stop operator Redis on the host.

Optional env:

| Variable | Default | Meaning |
| --- | --- | --- |
| `PIN_SPIKE_PORT_A` | `14001` | Host port proxy A |
| `PIN_SPIKE_PORT_B` | `14002` | Host port proxy B |
| `PIN_SPIKE_OUTAGE_WINDOW_S` | `15` | Wait after Redis stop before probes |
| `PIN_SPIKE_STARTUP_TIMEOUT_S` | `180` | Stack ready timeout |

### Promotion

Green evidence is required before any product PR that advertises `--redis`
shared control state. Future product PR should promote this suite to a
**controlled Docker runner** check (not waived; not every-commit GHA unless stable).

Hermetic CI (`uv run pytest` without `LLG_PIN_SPIKE`) skips these tests.
