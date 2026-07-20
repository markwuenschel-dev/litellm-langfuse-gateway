# Failure matrix (WP14)

Hermetic coverage is automated under `tests/unit/` and runs in default CI.  
Live and chaos rows are **red-capable** when gated env vars are set, but remain **UNPROVEN** until a run is recorded in `docs/evidence/README.md` (Index of runs). Default CI never sets `LLG_LIVE`.

## Labeling

| Label | Meaning |
| --- | --- |
| **Proven (hermetic)** | Automated unit/CI; no provider network |
| **Red-capable (live-gated)** | Test code will fail red when `LLG_LIVE=1` (+ secrets/stack); **not** a live pass claim |
| **UNPROVEN (live)** | No captured live evidence row yet |
| **Env-gated chaos** | Skipped unless operator sets `LLG_CHAOS_*` after inducing the fault |

## Hermetic (CI — no network to providers)

| Scenario | Expected | Test / location | Status |
| --- | --- | --- | --- |
| Metadata rejects `Authorization` / auth-like keys | `MetadataValidationError` | `tests/unit/test_failure_modes_metadata.py`, `test_metadata.py` | **Proven (hermetic)** |
| Metadata rejects oversize strings (>128) | `MetadataValidationError` | same | **Proven (hermetic)** |
| Metadata rejects secret-shaped values / forbidden keys | `MetadataValidationError` | same | **Proven (hermetic)** |
| Client refuses master key as app credential | `GatewayConfigError` | `tests/unit/test_llm_client.py` | **Proven (hermetic)** |
| Connection error → `GatewayUnavailable` | no silent bypass | `test_failure_modes_metadata.py` / `test_llm_client.py` | **Proven (hermetic)** |
| Budget exceeded body → `BudgetExceeded` | fail closed mapping | same | **Proven (hermetic)** |
| Model ACL deny body → `ModelAccessDenied` | mapped | `test_llm_client.py` | **Proven (hermetic)** |
| Gateway RPM/TPM 429 → `GatewayRateLimited` | mapped | `test_llm_client.py` | **Proven (hermetic)** |

## Live-gated automated tests (`LLG_LIVE=1`)

These are **not** proven by hermetic CI. They are **red-capable** when a stack + secrets exist. Live result remains **UNPROVEN** until Index of runs has a row.

| Scenario | Expected | Test | Status |
| --- | --- | --- | --- |
| Readiness healthy | `/health/readiness` OK | `test_readiness_ok_when_stack_healthy` | **Red-capable (live-gated)** · **UNPROVEN (live)** |
| Budget exceeded (`max_budget=0` key) | non-2xx **with budget-related body tokens** (bare 401/403/429 alone is not a pass) | `test_live_budget_exceeded` | **Red-capable (live-gated)** · **UNPROVEN (live)** |
| Model ACL denied | non-200 for disallowed alias | `test_live_model_acl_denied` | **Red-capable (live-gated)** · **UNPROVEN (live)** |
| Health liveliness / root | 200 when stack up | `test_gateway_health.py` | **Red-capable (live-gated)** · **UNPROVEN (live)** |
| Virtual key access paths | allowed vs denied models | `test_virtual_key_access.py` | **Red-capable (live-gated)** · **UNPROVEN (live)** |

Requires: running gateway, provider keys on the proxy, and for budget/ACL key create: `LITELLM_MASTER_KEY`. Optional app virtual key: `LITELLM_VIRTUAL_KEY`.

## Chaos (env-gated; operator induces fault first)

| Scenario | Expected | Gate | Test | Status |
| --- | --- | --- | --- | --- |
| Postgres down | `/health/readiness` fails | `LLG_LIVE=1` + `LLG_CHAOS_POSTGRES=1` | `test_postgres_down_readiness_fails` | **Env-gated chaos** · **UNPROVEN (live)** |
| Langfuse unreachable | LLM chat still succeeds | `LLG_LIVE=1` + `LLG_CHAOS_LANGFUSE=1` + virtual key | `test_langfuse_unreachable_llm_path_continues` | **Env-gated chaos** · **UNPROVEN (live)** |

Without `LLG_CHAOS_*`, tests **skip** with a reason naming the env var (not a permanent un-escapable skip). Operators: stop postgres / block Langfuse **before** enabling the gate, then run pytest. Document with `templates/failure-run.md`.

## Other live scenarios (manual procedure)

| Scenario | Expected | How to exercise | Status |
| --- | --- | --- | --- |
| Wrong salt (fresh volume) | Decrypt/start issues; do not “fix” by regenerating salt against old volume | See `incident-recovery.md`; fresh volume + new salt only | **UNPROVEN (live)** |
| Missing provider key for alias | Clear error for that alias; other aliases may still work | Unset one `*_API_KEY`; call alias | **UNPROVEN (live)** |
| Provider timeout | Normalized timeout / provider error | Low timeout / blocked egress to provider | **UNPROVEN (live)** |
| Container restart mid-suite | Keys/spend persist in Postgres | Restart litellm only; re-auth with same virtual key | **UNPROVEN (live)** |

## Integration test files

| File | Gate |
| --- | --- |
| `tests/integration/test_gateway_health.py` | `LLG_LIVE=1` |
| `tests/integration/test_virtual_key_access.py` | `LLG_LIVE=1` |
| `tests/integration/test_langfuse_export.py` | `LLG_LIVE=1` + Langfuse (optional chat) |
| `tests/integration/test_trace_grouping.py` | `LLG_LIVE=1` + Langfuse (optional chat) |
| `tests/integration/test_failure_modes_live.py` | `LLG_LIVE=1`; chaos also needs `LLG_CHAOS_POSTGRES` / `LLG_CHAOS_LANGFUSE` |
| `tests/integration/test_compose_env_origin.py` | Docker (hermetic compose; not `LLG_LIVE`) |

## Controlled live CI

Opt-in workflow: [`.github/workflows/live-smoke.yml`](../../.github/workflows/live-smoke.yml) — **`workflow_dispatch` only**, never push/PR. Costs provider money. See evidence README.

## Honesty

Do not mark DoD #13 (Langfuse outage) or #14 (Postgres outage readiness) complete until the chaos rows above have redacted evidence linked from `docs/evidence/README.md`.  
Do not treat “Automated when `LLG_LIVE=1`” as a live pass — that only means the test is red-capable.
