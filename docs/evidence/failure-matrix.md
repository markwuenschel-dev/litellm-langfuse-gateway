# Failure matrix (WP14)

Hermetic coverage is automated under `tests/unit/`. Live/chaos rows require a running stack and are **UNPROVEN** without `LLG_LIVE=1` and intentional outages.

## Hermetic (CI — no network to providers)

| Scenario | Expected | Test / location | Status |
| --- | --- | --- | --- |
| Metadata rejects `Authorization` / auth-like keys | `MetadataValidationError` | `tests/unit/test_failure_modes_metadata.py`, `test_metadata.py` | **Proven** (unit) |
| Metadata rejects oversize strings (>128) | `MetadataValidationError` | same | **Proven** (unit) |
| Metadata rejects secret-shaped values / forbidden keys | `MetadataValidationError` | same | **Proven** (unit) |
| Client refuses master key as app credential | `GatewayConfigError` | `tests/unit/test_llm_client.py` | **Proven** (unit) |
| Connection error → `GatewayUnavailable` | no silent bypass | `test_failure_modes_metadata.py` / `test_llm_client.py` | **Proven** (unit) |
| Budget exceeded body → `BudgetExceeded` | fail closed mapping | same | **Proven** (unit) |
| Model ACL deny body → `ModelAccessDenied` | mapped | `test_llm_client.py` | **Proven** (unit) |
| Gateway RPM/TPM 429 → `GatewayRateLimited` | mapped | `test_llm_client.py` | **Proven** (unit) |

## Live / compose chaos (`LLG_LIVE=1`)

| Test | Status |
| --- | --- |
| Readiness healthy | Automated when `LLG_LIVE=1` |
| Budget exceeded (max_budget=0 key) | Automated when `LLG_LIVE=1` + master (`test_live_budget_exceeded`) |
| Model ACL denied | Automated when `LLG_LIVE=1` + master (`test_live_model_acl_denied`) |
| Postgres down → readiness fail | Manual chaos only |
| Langfuse unreachable → LLM continues | Manual chaos only |

## Live / compose chaos (`LLG_LIVE=1` — historical stubs note)

Document each run with `templates/failure-run.md`. Until then:

| Scenario | Expected | How to exercise | Status |
| --- | --- | --- | --- |
| Postgres down | `/health/readiness` fails; unhealthy instance removed from rotation | Stop postgres container; probe readiness | **UNPROVEN** |
| Wrong salt (fresh volume) | Decrypt/start issues; do not “fix” by regenerating salt against old volume | See `incident-recovery.md`; fresh volume + new salt only | **UNPROVEN** (documented procedure) |
| Missing provider key for alias | Clear error for that alias; other aliases may still work | Unset one `*_API_KEY`; call alias | **UNPROVEN** |
| Budget exceeded (live key) | Request rejected; `BudgetExceeded` | Key with tiny `--max-budget`; spend past it | **UNPROVEN** |
| Model ACL deny (live key) | Reject; `ModelAccessDenied` | Key with `--models` excluding target | **UNPROVEN** |
| Langfuse unreachable | LLM path still succeeds | Block OTEL/host or bad Langfuse keys; chat still 200 | **UNPROVEN** |
| Provider timeout | Normalized timeout / provider error | Low timeout / blocked egress to provider | **UNPROVEN** |
| Container restart mid-suite | Keys/spend persist in Postgres | Restart litellm only; re-auth with same virtual key | **UNPROVEN** |

## Integration test files (live-gated)

| File | Gate |
| --- | --- |
| `tests/integration/test_gateway_health.py` | `LLG_LIVE=1` |
| `tests/integration/test_virtual_key_access.py` | `LLG_LIVE=1` |
| `tests/integration/test_langfuse_export.py` | `LLG_LIVE=1` + Langfuse |
| `tests/integration/test_trace_grouping.py` | `LLG_LIVE=1` + Langfuse |
| `tests/integration/test_failure_modes_live.py` | `LLG_LIVE=1` — stub markers for chaos rows |

## Honesty

Do not mark DoD #13 (Langfuse outage) or #14 (Postgres outage readiness) complete until the live rows above have redacted evidence linked from `docs/evidence/README.md`.
