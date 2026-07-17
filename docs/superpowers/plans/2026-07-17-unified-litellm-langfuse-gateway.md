# Unified LiteLLM Gateway + Langfuse Observability — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task after explicit approval. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Status:** PLAN ONLY — do not implement until reviewed/approved.
> **Plan date:** 2026-07-17
> **Repo inspected:** `litellm-langfuse-gateway` (greenfield scaffold on `main`, no commits at discovery time)

**Goal:** Establish a production-grade, OpenAI-compatible LLM control plane (LiteLLM Proxy + PostgreSQL, optional Redis) and observability plane (Langfuse Cloud + app tracing) so every production LLM call is attributable, controllable, costed, and observable without applications owning raw provider credentials.

**Architecture:** Applications call stable model aliases on LiteLLM with per-app virtual keys. LiteLLM owns provider credentials, routing, budgets, rate limits, retries/fallbacks, and spend. Langfuse owns end-to-end traces, sessions/users, scores, and quality analysis. Gateway generations export via `langfuse_otel`; applications create root traces and child spans, correlating with a shared metadata contract.

**Tech Stack:** LiteLLM Proxy (pin ≥ latest secure release; candidate **v1.92.0** published 2026-07-12), PostgreSQL 16, Redis 7 (multi-replica only), Langfuse Cloud OTEL, Python 3.12 + `uv`, TypeScript Node 22 + `pnpm`, Docker Compose (local), GitHub Actions CI.

## Global Constraints

- Pin all production images/deps; **never** `latest`, floating `main`, or unpinned `main-stable` in production artifacts.
- Use **`uv`** for Python and **`pnpm`** for JS/TS (migrate off scaffold `pip`/`npm`/`package-lock.json`).
- Prefer a **thin consolidated ops CLI** over a growing set of standalone runner scripts.
- `LITELLM_SALT_KEY` is permanent; never rotate casually; identical across replicas.
- Applications use **virtual keys only**; master key is admin-only.
- Provider credentials never appear in source, YAML literals, images, browser code, or logs.
- Default observability backend: **Langfuse Cloud** (not self-hosted unless residency/policy/cost requires).
- Official LiteLLM + Langfuse docs for the **pinned versions** are the external authority.
- Config-as-code for model aliases; single reconciliation authority for model registry (YAML vs DB).
- No silent direct-provider bypass on gateway failure.
- Langfuse outage must not fail the primary LLM path by default (prove with outage test).
- Definition of Done §20 is binding for completion claims.

---

# 1. Executive assessment

This repository is a **greenfield platform repo**, not an application monorepo. Discovery found a coherent scaffold (Compose, LiteLLM YAML, env template, unit tests for config validation, CI) that correctly expresses the intended ownership split—but it is **not production-grade** and has **not been exercised** end-to-end against providers or Langfuse.

| Dimension | Assessment |
| --- | --- |
| Fit for purpose | Correct product shape; incomplete control plane |
| Largest gaps | Unpinned image; no stable semantic aliases; no virtual-key/budget automation; no client library; no integration/adversarial tests; no ops docs; dual model-registry risk (`STORE_MODEL_IN_DB=True` + YAML) |
| Blocker to “done” | Live provider credentials + Langfuse Cloud project + pinned image verification; no external apps in-repo to migrate—must prove path via **reference vertical slice** then document external migration |
| Recommended posture | Harden platform first → vertical slice (1 alias × 1 provider × virtual key × spend × correlated trace) → four providers → enforcement/failure/cost → staging/prod runbooks |

**Recommendation:** Approve this plan, then execute Work Packages 1–7 as the critical path before expanding scope to multi-app migration.

---

# 2. Project purpose and non-negotiable promise

**Purpose:** One secure, observable, governable path for LLM usage across OpenAI, Anthropic, Google Gemini, and xAI/Grok.

**Promise:**

> Every production LLM call must be attributable, controllable, costed, and observable without requiring application code to manage raw provider credentials or duplicate provider-specific integration logic.

**Must deliver:** single gateway endpoint; centralized credentials; stable aliases; per-app/team virtual credentials; model ACL; spend by app/team/env/provider/model; budgets & rate limits; Langfuse request telemetry; end-to-end app traces for important workflows; explicit failure policies; reproducible env configs; evidence per provider.

**Violations (disallowed):** raw provider keys in apps; bypass SDK paths; unattributable spend; disconnected Langfuse generations; hard-coded vendor model IDs in apps; secrets in git/logs/telemetry; master key in apps; unpinned images; Langfuse outage failing LLM path without explicit decision; silent direct-provider fallback; docs claiming support without smoke+telemetry evidence; unreconciliation cost claims.

---

# 3. Current-state truth table

Evidence base: filesystem inspection of this repo on 2026-07-17; local unit tests previously run (7 passed); Compose config validation; Docker pull of `ghcr.io/berriai/litellm:main-stable` digest `sha256:9ef6f45bc0104940571765e610c52a1d761b5ec85efcd193795281086ee61277`; GitHub latest release tag `v1.92.0` (2026-07-12). **No live stack exercise, no provider smoke, no Langfuse export verification performed for this plan.**

| Area | Path / system | State | Notes |
| --- | --- | --- | --- |
| Repo purpose docs | `README.md`, `AGENTS.md` | Partially implemented | Architecture correct; production checklist not proven |
| LiteLLM config | `config/litellm_config.yaml` | Configured but not exercised | Vendor-ish aliases; hardcoded dated model IDs; `langfuse_otel` via success/failure callbacks; fallbacks commented out |
| Compose stack | `docker-compose.yml`, `docker-compose.redis.yml` | Partially implemented | Postgres + LiteLLM present; image default `main-stable` (**unpinned**); Redis optional overlay exists |
| Env contract | `.env.example` | Partially implemented | Good secret shapes; no staging/prod split files |
| Secrets in git | `.gitignore`, no `.env` | Planned hygiene present | No real secrets observed in scaffold |
| Virtual keys / teams / budgets | — | Planned but unimplemented | No provisioning automation or tests |
| Model registry authority | `STORE_MODEL_IN_DB=True` + YAML | Conflict / unproven | Dual path without reconciliation rule |
| Langfuse Cloud wiring | env + callbacks | Configured but not exercised | Needs `LANGFUSE_OTEL_HOST` regional correctness verification vs docs |
| App client library | `examples/*` only | Planned but unimplemented | Examples call gateway but are not a hardened client |
| Metadata / trace contract | — | Planned but unimplemented | No schema |
| Integration tests | `tests/` | Unit only | Config + secret generator tests only |
| CI | `.github/workflows/ci.yml` | Partially implemented | Lint/unit/compose config; no live smoke; uses `pip`/`npm` |
| Package managers | `pyproject.toml`, `package-lock.json` | Stale relative to mandate | Spec requires `uv` + `pnpm`; scaffold uses pip/npm |
| Ops CLI | `scripts/*.py` entrypoints | Partially implemented | Three scripts; not a consolidated CLI surface |
| Platform docs | `docs/llm-platform/` | Planned but unimplemented | Does not exist yet |
| External consumer apps | (outside this repo) | Speculative / unknown | No in-repo applications; inventory must target external consumers or treat reference demo as first “app” |
| Production deployment | k8s/helm/terraform | Planned but unimplemented | Compose-only |
| Provider smoke evidence | — | Unproven | |
| Cost reconciliation | — | Unproven | |
| Security posture vs CVEs | image pin | Unproven | Plan requires pin ≥ current secure release; CVEs historically in pre-1.83 lines—candidate pin v1.92.0+ |

**Legend used:** fully implemented and verified | implemented but not integrated | partially implemented | configured but not exercised | planned but unimplemented | speculative | stale | unproven | conflict.

---

# 4. Source-of-truth hierarchy

1. Explicit stakeholder / security decisions (privacy classes, residency, emergency bypass).
2. This approved plan + locked decisions table (§8).
3. Runtime code and **deployed** configuration (Compose/k8s manifests as applied).
4. Versioned contracts: model alias map, metadata JSON Schema, error contract.
5. Infrastructure manifests and secret references (never secret values).
6. Automated integration / e2e tests under `tests/integration/`.
7. Runtime evidence from real provider + Langfuse calls (`docs/evidence/` index).
8. Generated reports (cost reconciliation, smoke matrices).
9. Unit tests and fixtures.
10. README / examples.
11. Historical plans and stale scaffold comments.

**External authority:** Official LiteLLM docs and Langfuse docs for the **pinned versions**.

**Conflict rule:** Runtime evidence beats docs when they diverge; open a defect and update docs, do not “paper over.”

---

# 5. Authority and ownership map

| Concern | Canonical owner | Not owner |
| --- | --- | --- |
| Provider API credentials | LiteLLM (env/secret manager → proxy) | Apps, Langfuse |
| Model aliases & routing | LiteLLM config (YAML source of truth) | Apps |
| Virtual keys, teams, budgets, RPM/TPM | LiteLLM + PostgreSQL | Langfuse |
| Spend enforcement | LiteLLM | Langfuse |
| Normalized OpenAI-compatible API + errors | LiteLLM | Apps (map to domain errors only) |
| Gateway health / readiness | LiteLLM + deploy probes | Langfuse |
| Per-call generation telemetry | LiteLLM → Langfuse (`langfuse_otel`) | Apps (avoid dual-write of same generation unless deliberate) |
| Workflow traces, tools, retrieval, agents | Application + Langfuse SDK/OTEL | LiteLLM |
| Sessions, users, scores, datasets, evals | Langfuse | LiteLLM |
| Privacy classification & retention policy | Platform ops / security docs | Individual app ad-hoc choices |
| Cost reconciliation process | Platform ops (this repo’s tooling) | Either dashboard alone |

---

# 6. Canonical lifecycle and data flow

```text
App request
  → assign request_id, start Langfuse root trace (env, release, service, feature, user?, session?)
  → child spans: retrieve / tools / prep
  → POST LiteLLM /v1/chat/completions
       Authorization: Bearer <virtual key>
       model: <stable alias>
       metadata: { request_id, trace_id, session_id, user_id, ...contract fields }
  → LiteLLM: auth → model ACL → budget → rate limit → resolve alias → provider call
  → LiteLLM: normalize response/error; write spend (Postgres); export generation (langfuse_otel)
  → App: parse/validate spans; complete root trace (status, latency, non-sensitive metadata)
  → Later: scores / feedback attach to same trace_id
```

**Data planes:**

- **Control / spend:** LiteLLM ↔ PostgreSQL (keys, teams, budgets, spend logs).
- **Optional shared state:** Redis (multi-instance rpm/tpm, cache, transaction buffer at high RPS).
- **Telemetry:** LiteLLM OTEL export → Langfuse; App SDK → Langfuse.
- **Correlation key:** `metadata.request_id` + Langfuse `trace_id` (propagated into LiteLLM metadata per pinned-version API).

---

# 7. Contracts and architectural invariants

## 7.1 Model alias contract (application-facing)

| Alias | Intent | Initial provider mapping (to be verified at pin time) | Consumers |
| --- | --- | --- | --- |
| `llm-fast` | Low latency / cost | Prefer OpenAI mini or Gemini flash (decide after inventory) | Reference app + external |
| `llm-general` | Default chat | One primary + optional fallback group | Reference app |
| `openai-general` | Explicit OpenAI comparison | `openai/<verified-id>` | Tests / deliberate A-B |
| `anthropic-general` | Explicit Anthropic | `anthropic/<verified-id>` | Tests |
| `gemini-general` | Explicit Gemini | `gemini/<verified-id>` | Tests |
| `grok-general` | Explicit xAI | `xai/<verified-id>` | Tests |

**Rule:** Do not invent unused aliases. Do not silently change alias→provider. Alias change requires: reason, eval, cost/latency comparison, tool/structured-output check, rollback mapping, config changelog entry.

**Source of truth:** `config/llm/model-aliases.yaml` compiled/merged into `infra/llm-gateway/litellm-config.yaml` (or single file with documented sections). **YAML is authority**; Admin UI / DB model edits are disabled or read-only for production aliases (`store_model_in_db` policy: **false** for production unless a later ADR flips authority).

## 7.2 Metadata contract (bounded)

Schema file: `config/llm/metadata-contract.schema.json`

Required / allowed fields (apps + gateway logging):

```text
request_id          # required, UUID
service             # required
feature             # required
environment         # required: development|staging|production
release             # required: git sha or semver
model_alias         # required (echo of requested alias)
trace_id            # required when app creates Langfuse root
session_id          # optional
user_id             # optional, pseudonymous
tenant_id           # optional
cost_center         # optional
workflow_type       # optional
retry_attempt       # optional int
fallback_used       # optional bool
experiment_variant  # optional
```

**Forbidden in metadata/logs/telemetry:** provider keys, virtual keys, master key, Authorization headers, cookies, DB passwords, raw PII (email, names, MRNs) unless privacy policy explicitly approves a class.

## 7.3 Error contract (application-visible)

Client library maps HTTP status + LiteLLM error body to stable types:

| Condition | Client error | Notes |
| --- | --- | --- |
| Invalid/revoked key | `GatewayAuthError` | 401/403 |
| Model not allowed | `ModelAccessDenied` | Distinct from budget |
| Budget exceeded | `BudgetExceeded` | Fail closed |
| Rate limited (gateway) | `GatewayRateLimited` | Distinct from provider 429 |
| Provider 429 / 5xx | `ProviderUnavailable` | After retries exhausted |
| Gateway down | `GatewayUnavailable` | No silent bypass |
| Timeout | `GatewayTimeout` | |

## 7.4 Invariants (must not break)

As specified in agent instructions §16 (1–20): apps never own provider credentials; never use master key; distinct virtual keys per app/env; all prod LLM traffic via LiteLLM; stable aliases; LiteLLM enforces budget/routing; Langfuse owns quality plane; observability failure does not change routing; gateway failure does not create direct bypass; secrets out of git/logs/telemetry; Postgres state survives restart; multi-instance claims require Redis; fallbacks explicit; env/release on traces; privacy on user/session IDs; pinned artifacts; explicit migrations; evidence ≠ screenshots alone; cost reconciled.

---

# 8. Locked decisions and terminology

| Decision | Choice | Rationale |
| --- | --- | --- |
| Gateway product | LiteLLM Proxy (not custom) | Spec non-goal: no custom gateway |
| Observability product | Langfuse Cloud first | Avoid self-host HA burden |
| Local stack | Compose: LiteLLM + Postgres; no Redis | Single replica default |
| Staging/prod multi-replica | ≥2 LiteLLM + Redis when shared limits needed | LiteLLM prod guidance |
| Model registry authority | **YAML in git** | Reviewable; disable dual-write conflict |
| `STORE_MODEL_IN_DB` | **False** for default prod path | Prevents split-brain with YAML |
| Langfuse integration | `langfuse_otel` callback (verify exact key: `callbacks` vs success/failure for pin) | Current Langfuse + LiteLLM docs |
| App integration surface | OpenAI-compatible `/v1` + shared client wrappers | Spec |
| Package managers | Migrate to **uv** + **pnpm** | Spec mandate; scaffold locks are not sacred |
| Ops interface | `llg` CLI (Typer or equivalent) consolidating scripts | Avoid script sprawl |
| Image pin candidate | Resolve official tag for **≥ v1.92.0** + digest in compose | Latest GH release at plan time; re-verify at execute |
| Fallback default | **Off** until matrix proves safe semantic fallback | Avoid silent quality/safety shift |
| Postgres on outage | Fail readiness; remove instance from service | Prod policy; do **not** set `allow_requests_on_db_unavailable` unless VPC-only ADR |
| Langfuse on outage | Fail open on LLM path; bounded export | Prove with test |
| Privacy default | Record prompts/responses only for non-sensitive class until classification done | Minimize |
| Representative “application” | In-repo `packages/llm-client` + `examples/reference_workflow` | No external apps in this repo yet |

**Terminology:**

- **Alias** = application-facing model name.
- **Deployment / route** = LiteLLM `litellm_params.model` provider path.
- **Virtual key** = app credential issued by LiteLLM.
- **Master key** = admin only.
- **Generation** = model call observation in Langfuse from gateway.
- **Trace** = app root workflow in Langfuse.

---

# 9. Critical path and primary blocker

**Critical path:**

```text
Pin image + lock config authority
  → secrets/env contract + local stack boots with readiness
  → provision team + virtual key + one alias (llm-general → one provider)
  → smoke call + Postgres spend row + Langfuse generation
  → correlate app root trace
  → expand 4 providers
  → budgets/RPM + adversarial suite
  → cost reconciliation
  → staging hardening docs + pin digests
```

**Primary blockers (external):**

1. Availability of real provider API keys for OpenAI, Anthropic, Gemini, xAI (or explicit staged enablement).
2. Langfuse Cloud project + regional host decision (EU `https://cloud.langfuse.com` vs US `https://us.cloud.langfuse.com` vs other).
3. Stakeholder privacy classification if prompts must be recorded.

**Primary technical risk:** Trace correlation between app Langfuse SDK and LiteLLM `langfuse_otel` generations for the pinned versions—must be proven, not assumed.

---

# 10. Scope and explicit non-goals

**In scope (this milestone):**

- Production-shaped LiteLLM+Postgres (+Redis path documented/tested optionally).
- Four provider families through gateway with virtual keys.
- Stable aliases, budgets, rate limits, model ACL.
- Langfuse gateway telemetry + one reference app workflow with correlated trace.
- Integration, failure, cost reconciliation, security scanning.
- Ops docs: architecture, operate, onboard, migrate, incident, cost, privacy.
- Evidence index.

**Out of scope:**

- Custom gateway / custom observability DB.
- Full org-wide app rewrite before vertical slice.
- Self-hosted Langfuse HA.
- Multi-region active-active.
- ML-based routing / complex semantic routing.
- Full eval platform for every app.
- Prompt-management platform migration.
- Provider billing system changes.

---

# 11. Recommended architecture or approach

```text
                    ┌─────────────────────────────┐
   Apps / agents ──►│  packages/llm-client (Py/TS) │
                    │  virtual key + aliases only  │
                    └──────────────┬──────────────┘
                                   │ OpenAI-compatible
                                   ▼
                    ┌─────────────────────────────┐
                    │  LiteLLM Proxy (pinned)     │
                    │  ACL · budget · RPM · route │
                    └─┬───────────┬───────────┬───┘
                      │           │           │
               PostgreSQL      Redis*     Providers
            keys/spend/cfg   multi-repl   OA/Ant/Gem/xAI
                      │
                      └── langfuse_otel ──► Langfuse Cloud
   Apps ── Langfuse SDK (root trace, tools, retrieval, scores) ─┘

* Redis only for multi-replica / shared limits
```

**Layout mapping (adapt scaffold → target):**

| Spec artifact | Canonical path in this repo |
| --- | --- |
| Gateway infra | `infra/llm-gateway/` (`compose.yaml`, `litellm-config.yaml`, `.env.example`, `README.md`, `upgrade-notes.md`) |
| Contracts | `config/llm/model-aliases.yaml`, `metadata-contract.schema.json`, `environments/{development,staging,production}.yaml` |
| Client | `packages/llm-client/` (Python primary; TS twin or thin TS re-export) |
| Ops CLI | `packages/llg-cli/` or `src/llg/` — single entry `llg` |
| Integration tests | `tests/integration/` |
| Docs | `docs/llm-platform/*` |
| Evidence | `docs/evidence/` (gitkeep + redacted templates; no secrets) |
| Current scaffold | Migrate: root `docker-compose*.yml` → `infra/llm-gateway/`; `config/litellm_config.yaml` → gateway config; keep root README as index |

**Implementation approach:** TDD where pure logic exists (metadata validation, error mapping, config compile); integration tests gated on env flags (`LLG_LIVE=1`) so CI stays hermetic by default with a separate nightly/live workflow.

---

# 12. Rejected alternatives and why

| Alternative | Rejected because |
| --- | --- |
| Self-host Langfuse immediately | Ops/HA/backup not justified; Compose ≠ production Langfuse |
| Apps keep provider SDKs + dual credentials | Breaks non-negotiable promise |
| Master key for “simplicity” in apps | Privilege blast radius; unattributable spend |
| DB-as-sole model registry via Admin UI | Non-reviewable; drifts from git; hard rollback |
| `allow_requests_on_db_unavailable=true` by default | Violates fail-closed budget/auth promise outside locked VPC ADR |
| Floating `main-stable` in prod | Moving tag; contradicts pin requirement |
| Keep npm + pip because scaffold has lockfiles | Spec mandates uv/pnpm; scaffold is greenfield |
| Many standalone scripts forever | Spec forbids sprawl; consolidate into `llg` |
| Enable multi-provider fallbacks day one | Semantic risk (tools/structured output); prove first |
| Custom gateway | Explicit non-goal |

---

# 13. Parallel lane plan

| Lane | Name | Can start | Blocked by | Owns (paths) |
| --- | --- | --- | --- | --- |
| L1 | Discovery freeze | Immediate | — | Evidence inventory only (done for in-repo; external apps TBD) |
| L2 | Gateway config & aliases | After pin version choice | Pin decision | `infra/llm-gateway/`, `config/llm/` |
| L3 | Keys, budgets, Postgres | After stack boots | L2 boot | CLI key provisioning, env docs |
| L4 | Langfuse + metadata contract | Immediate (design); implement after pin | Pin + Langfuse project | schema, OTEL config, client tracing helpers |
| L5 | Client library + reference workflow | After aliases + metadata freeze | L2, L4 contracts | `packages/llm-client/`, examples |
| L6 | Security/privacy/ops | Immediate | Privacy class for recording | docs, secret scan CI, threat notes |
| L7 | Verification suite | Design immediate; run after L2–L5 | Live keys | `tests/integration/`, evidence |
| L8 | Docs merge & handoff | Continuous; owns final | All lanes | `docs/llm-platform/`, evidence index |

**File non-overlap rule:** L2 does not edit client; L5 does not edit Compose; L7 may only add tests + fixtures; L8 docs-only except index links.

---

# 14. Dependency graph and execution order

```text
[Pin LiteLLM version/digest] ──► [Restructure infra + env contract]
                │
                ▼
        [Local stack up + health]
                │
        ┌───────┴────────┐
        ▼                ▼
 [Aliases YAML]   [Langfuse OTEL + metadata schema]
        │                │
        └───────┬────────┘
                ▼
     [Virtual key bootstrap via llg]
                ▼
     [Vertical slice: 1 provider smoke + spend + generation]
                ▼
     [Client + reference workflow correlation]
                ▼
     [4 providers + streaming/tools matrix]
                ▼
     [Budget/RPM/ACL + adversarial + Langfuse outage]
                ▼
     [Cost reconciliation]
                ▼
     [Staging/prod hardening docs + CI live optional job]
                ▼
     [Evidence index + DoD checklist]
```

---

# 15. Detailed work packages

Each package below is implementation-ready after approval. Checkbox steps are for the executing engineer/agent.

---

### WP0 — Baseline freeze and tooling migration

**Goal:** Reproducible toolchain; clean baseline measurements.  
**Why:** Spec requires uv/pnpm; CI must match.  
**Preconditions:** Plan approved.  
**Paths:** `pyproject.toml`, `package.json`, CI, new `uv.lock`, `pnpm-lock.yaml`.  
**Owner:** L8/L6 shared.  
**Parallel:** Yes with WP1 design docs.

**Actions:**

- [ ] **Step 1:** Record baseline: `git status`, file tree, existing test command results.
- [ ] **Step 2:** Add `uv` project workflow (`uv sync --all-extras`); remove reliance on ad-hoc venv+pip in docs/CI.
- [ ] **Step 3:** Convert JS to `pnpm` (`pnpm import` or fresh lock); delete `package-lock.json` after `pnpm-lock.yaml` verified.
- [ ] **Step 4:** Update CI to `astral-sh/setup-uv` and `pnpm/action-setup`.
- [ ] **Step 5:** Run: `uv run ruff check . && uv run pytest && pnpm typecheck`.
- [ ] **Step 6:** Commit: `chore: migrate to uv and pnpm toolchains`.

**Tests:** CI green hermetic.  
**Evidence:** CI logs.  
**Rollback:** Revert commit; restore lockfiles.  
**Risks:** Windows path issues with uv—document PowerShell commands.

---

### WP1 — Current-state provider-call inventory (org + repo)

**Goal:** Evidence-backed inventory of who calls which models today.  
**Why:** Aliases must have consumers; do not invent.  
**Preconditions:** Access to consumer repos or explicit “reference-only” stakeholder decision.  
**Paths:** `docs/llm-platform/provider-call-inventory.md` (create).  
**Owner:** L1.  
**Parallel:** Yes.

**Actions:**

- [ ] Search sibling/org repos for `openai.`, `Anthropic`, `google.generativeai`, `xai`, raw `api.openai.com`, etc. (scope as available).
- [ ] If no external apps accessible: document **reference-only milestone** — inventory = this repo’s examples + intended aliases.
- [ ] Table: app → models → features (stream/tools/structured/embed) → credential source → telemetry today.
- [ ] Classify privacy tier per app.

**Completion:** Inventory doc merged; alias candidate list pruned to real consumers.  
**Risks:** Missing a consumer → broken alias change later.

---

### WP2 — Architecture, SoT, and layout migration

**Goal:** Lock YAML authority; move gateway files to `infra/llm-gateway/`.  
**Why:** Split-brain risk (`STORE_MODEL_IN_DB` + YAML).  
**Paths:** `infra/llm-gateway/**`, root compose deprecation shims, `AGENTS.md`, `README.md`.  
**Owner:** L2.  
**Depends:** WP0.

**Actions:**

- [ ] Create `infra/llm-gateway/compose.yaml` from current compose; set:
  - `LITELLM_IMAGE` **required** pin (tag + digest comment).
  - `STORE_MODEL_IN_DB=False` default.
  - `LITELLM_MODE=PRODUCTION` in non-dev overlays.
- [ ] Move config to `infra/llm-gateway/litellm-config.yaml`.
- [ ] Root `docker-compose.yml` becomes thin include or docs pointer (one canonical compose).
- [ ] Document model registry authority in `docs/llm-platform/architecture.md`.
- [ ] Validate: `docker compose -f infra/llm-gateway/compose.yaml config`.

**Config policy snippet (target):**

```yaml
litellm_settings:
  request_timeout: 600
  set_verbose: false
  json_logs: true
  drop_params: true
  callbacks: ["langfuse_otel"]   # confirm exact field for pin; align success/failure if required

general_settings:
  # master_key / database_url via env
  proxy_batch_write_at: 60
  database_connection_pool_limit: 10
  disable_error_logs: true        # prod: exceptions to logging stack, not DB bloat; also historical CVE mitigation note
  # allow_requests_on_db_unavailable: false  # keep false
```

**Rollback:** Restore root compose paths.  
**Risks:** Breaking local docs commands—update README same PR.

---

### WP3 — Pin LiteLLM release and security baseline

**Goal:** Immutable image reference.  
**Why:** Moving tags violate DoD #17; historical critical CVEs in older proxy lines.  
**Owner:** L2 + L6.  
**Depends:** WP2 structure.

**Actions:**

- [ ] Confirm Docker tag for release `v1.92.0` (or newer if released at execute time) on `ghcr.io/berriai/litellm`.
- [ ] Pull and record digest: `docker buildx imagetools inspect <image>:<tag>`.
- [ ] Set compose default:
  - `image: ghcr.io/berriai/litellm:<tag>@sha256:<digest>`
- [ ] Pin `postgres:16.x-alpine@sha256:…` and `redis:7.x-alpine@sha256:…` similarly.
- [ ] Add CI check: fail if compose image contains `latest` or un-digested `main`.
- [ ] Note upgrade path in `infra/llm-gateway/upgrade-notes.md`.

**Evidence:** `docker compose config` shows digests; CI pin check.  
**Risks:** Tag naming differs (`main-v1.92.0-stable` vs `v1.92.0`)—resolve from GHCR, do not guess in final artifacts.

---

### WP4 — Secret hierarchy and environment contract

**Goal:** Complete `.env.example` + env YAML overlays without secrets.  
**Paths:** `infra/llm-gateway/.env.example`, `config/llm/environments/*.yaml`.  
**Owner:** L3 + L6.

**Secrets (values only in secret manager / local `.env`):**

| Secret | Scope | Rotation |
| --- | --- | --- |
| `LITELLM_MASTER_KEY` | Admin | Rotatable with admin procedure |
| `LITELLM_SALT_KEY` | Encryption | **Permanent**; backup offline |
| `DATABASE_URL` / Postgres password | DB | Rotatable with app restart |
| Provider keys | Proxy only | Per provider policy |
| `LANGFUSE_PUBLIC_KEY` / `SECRET_KEY` | Telemetry | Rotatable |
| Redis password | Multi-repl | Rotatable |

**Actions:**

- [ ] Expand `.env.example` with comments for dev/staging/prod differences.
- [ ] Document secret manager mapping (generic: AWS SM / GCP SM / Doppler—pick platform at deploy).
- [ ] Salt-key recovery procedure in `docs/llm-platform/incident-recovery.md`.
- [ ] `llg secrets generate` replaces raw `scripts/generate_secrets.py` entry.

**Tests:** Secret scan CI (gitleaks or trufflehog) on PRs.  
**Failure tests:** Boot without master key → fail; wrong salt after encrypted vars exist → documented failure.

---

### WP5 — Local LiteLLM + PostgreSQL stack hardening

**Goal:** Reliable local/dev boot with health gates.  
**Owner:** L2/L3.  
**Depends:** WP3, WP4.

**Actions:**

- [ ] Health: liveness `/health/liveliness`, readiness `/health/readiness` (Postgres required).
- [ ] Compose healthchecks already present—align readiness with deploy probes.
- [ ] `llg up` / `llg down` / `llg health` CLI commands.
- [ ] Persistence test: create virtual key → restart litellm container → key still works; spend retained.

**Tests:**

- `tests/integration/test_gateway_health.py` (requires compose).
- `tests/integration/test_restart_persistence.py`.

**Commands:**

```bash
uv run llg up
uv run llg health --path /health/readiness
docker compose -f infra/llm-gateway/compose.yaml restart litellm
uv run llg health
```

**Evidence:** Logs + key id before/after restart (redact secrets).

---

### WP6 — Provider model onboarding (four families)

**Goal:** Verified provider routes for OpenAI, Anthropic, Gemini, xAI.  
**Owner:** L2.  
**Depends:** WP5 + real keys.

**Actions:**

- [ ] For each provider, confirm with **pinned** LiteLLM docs:
  - prefix (`openai/`, `anthropic/`, `gemini/`, `xai/`)
  - chat, stream, tools, structured output, embeddings support matrix
- [ ] Replace scaffold’s assumed model IDs with **verified current IDs** at execute time (do not copy outdated dates from scaffold blindly).
- [ ] Map provider keys only via `os.environ/...`.
- [ ] Document unsupported features per provider in `docs/llm-platform/provider-onboarding.md`.

**Smoke (per provider):**

```bash
uv run llg smoke --provider openai --alias openai-general
# equally for anthropic, gemini, xai
```

**Evidence per call:** alias, resolved model, request_id, LiteLLM spend row, Langfuse generation id, tokens, latency.

---

### WP7 — Stable model aliases

**Goal:** Application-facing alias contract with changelog discipline.  
**Paths:** `config/llm/model-aliases.yaml` → rendered into litellm config.  
**Owner:** L2.  
**Depends:** WP1 inventory, WP6 routes.

**Actions:**

- [ ] Implement only aliases with consumers (at minimum: four `*-general` + `llm-general` if reference needs it).
- [ ] Add `llg config render` to compile aliases → `litellm-config.yaml` or validate they stay in sync.
- [ ] Unit test: no literal `api_key` secrets; unique `model_name`; every alias has provider prefix.
- [ ] Fallback groups: default **empty**; optional later `llm-general` → ordered list after WP13.

**Alias change checklist** (doc): reason, eval, cost, latency, tools/structured, rollback, release note.

---

### WP8 — Virtual keys, teams, budgets, rate limits

**Goal:** Enforcement plane usable without Admin UI clicking.  
**Owner:** L3.  
**Depends:** WP5.

**Key hierarchy:**

```text
Master key (admin)
  └── Team: platform-dev | platform-staging | platform-prod
        └── Virtual key per application per environment
              ├── models: allow-list
              ├── max_budget + budget_duration
              ├── rpm_limit / tpm_limit
              └── metadata: { service, environment }
```

**Actions:**

- [ ] `llg keys create --team ... --models ... --max-budget ... --rpm ...`
- [ ] `llg keys revoke`
- [ ] Bootstrap script for local: creates `reference-app-dev` key; prints once; never writes secret to disk in repo.
- [ ] Tests:
  - allowed model 200
  - disallowed model denied
  - over budget fail closed
  - over rpm fail closed
  - invalid key 401
  - master key not in client examples

**API shapes (verify on pin):** `POST /key/generate`, `POST /key/delete`, spend endpoints under admin auth.

---

### WP9 — Langfuse project + OTEL gateway export

**Goal:** Every gateway call emits generation telemetry.  
**Owner:** L4.  
**Depends:** WP3, Langfuse project.

**Env (per Langfuse current docs):**

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_OTEL_HOST=https://cloud.langfuse.com   # or us.cloud / regional
# LANGFUSE_HOST may still be required depending on pin—set both if docs require
```

**Actions:**

- [ ] Confirm callback field for pin (`callbacks: ["langfuse_otel"]` vs success/failure lists)—match official docs for that version; single canonical config.
- [ ] Dev project vs prod project separation (separate keys).
- [ ] Test: successful chat → generation visible with model, tokens, latency, cost fields (or explicit “unavailable” note).
- [ ] Test: invalid Langfuse credentials → LLM still succeeds; export error observable in proxy logs (no secret leak).
- [ ] Test: Langfuse host blocked (toxiproxy or sinkhole) → bounded behavior, no memory blow-up.

**Evidence:** Redacted Langfuse trace URLs + request_ids.

---

### WP10 — Trace and metadata contract + correlation

**Goal:** App root trace and LiteLLM generation join via shared IDs.  
**Paths:** `config/llm/metadata-contract.schema.json`, client `metadata.py`/`metadata.ts`.  
**Owner:** L4/L5.  
**Depends:** WP9.

**Actions:**

- [ ] JSON Schema + Python/TS validators.
- [ ] Document propagation: Langfuse trace id → LiteLLM `metadata.trace_id` / current supported fields (`trace_user_id`, `session_id`, tags, version, release)—**verify names against pin**.
- [ ] Reference workflow:
  1. start_span root
  2. retrieval child (mock)
  3. gateway chat with metadata
  4. parse child
  5. score `request_success`
- [ ] Test `test_trace_grouping.py` asserts same `request_id` / trace linkage.

**Completion:** One screenshot **plus** API-fetched trace JSON stored redacted under `docs/evidence/`.

---

### WP11 — Shared application client (Python + TypeScript)

**Goal:** Canonical way apps call the gateway.  
**Paths:** `packages/llm-client/`.  
**Owner:** L5.  
**Depends:** WP7, WP10.

**Python surface (illustrative—adjust to final module path):**

```python
from llm_client import GatewayClient, GatewayConfig
from llm_client.metadata import RequestMetadata

client = GatewayClient(GatewayConfig.from_env())  # base_url, virtual_key only
meta = RequestMetadata(
    request_id="...",
    service="reference-app",
    feature="ping",
    environment="development",
    release="dev",
    model_alias="llm-general",
    trace_id="...",
)
resp = client.chat(model="llm-general", messages=[...], metadata=meta)
```

**Rules enforced in client:**

- Reject if `OPENAI_API_KEY` etc. set as transport key (warn/fail in prod mode).
- Never accept master key if `LLG_DISALLOW_MASTER=1` (default on).
- Map errors to contract §7.3.
- Optional Langfuse decorator helpers for root traces.

**Tests:** unit tests for metadata validation + error mapping; integration uses live gateway.

**TS:** mirror API for Node services; `pnpm` workspace package.

---

### WP12 — Representative application migration

**Goal:** Prove “no raw provider credentials” for at least one app.  
**In this repo:** `examples/reference_workflow` is the representative app.  
**External apps:** `docs/llm-platform/application-migration.md` checklist only until access granted.

**Migration steps (external template):**

1. Deploy/access gateway base URL + issue virtual key.
2. Replace provider SDK base URL + key.
3. Replace model strings with aliases.
4. Add metadata + tracing.
5. Remove provider secrets from app env.
6. Verify smoke + Langfuse + spend.
7. Document rollback (re-enable old env only via break-glass procedure).

**Completion for milestone:** Reference workflow passes DoD items 1–11 on evidence; external migrations tracked as deferred if no access.

---

### WP13 — Streaming, tools, structured output matrix

**Goal:** Feature compatibility evidence per provider/alias.  
**Owner:** L7.  
**Depends:** WP6–WP11.

**Matrix columns:** non-stream, stream, tools, structured output, timeout, cost fields.  
**Rows:** each enabled alias/provider.

**Fallback policy:** keep disabled until a pair proves tool+structured compatibility; then document one safe fallback path **or** explicit “fallbacks disabled” rationale in architecture.md (satisfies DoD #7).

---

### WP14 — Failure and recovery tests

**Goal:** Adversarial suite from agent instructions §13.  
**Owner:** L7.  
**Paths:** `tests/integration/test_failure_modes.py` (+ supporting chaos helpers).

**Minimum automated subset for CI (hermetic mocks where needed):**

- metadata schema rejects auth headers / oversize
- client rejects master key in prod mode

**Minimum live/local compose subset (`LLG_LIVE=1`):**

- Postgres down → readiness fail
- wrong salt (fresh volume scenario documented)
- missing provider key → clear error for that alias
- budget exceeded
- model ACL deny
- Langfuse unreachable
- provider timeout simulation (where feasible)
- container restart mid-suite

**Evidence:** failure matrix table in `docs/evidence/failure-matrix.md`.

---

### WP15 — Cost reconciliation

**Goal:** Bounded compare provider usage vs LiteLLM vs Langfuse.  
**Owner:** L7/L8.  
**Depends:** WP6, WP9.

**Process:**

1. Fixed prompt set (N calls per provider).
2. Capture provider usage (dashboard/API).
3. Capture LiteLLM spend API / DB.
4. Capture Langfuse observation costs.
5. Diff within tolerance (initial proposal: **±5% or ±$0.01** per call group, whichever larger; adjust after first run).
6. Document known deltas (cached tokens, reasoning tokens, failed retries).

**Deliverable:** `docs/llm-platform/cost-reconciliation.md` + latest run under `docs/evidence/`.

**Do not** claim accuracy without this run.

---

### WP16 — Staging deployment package

**Goal:** Reproducible staging beyond laptop Compose.  
**Owner:** L2/L6.  

**Actions:**

- [ ] `config/llm/environments/staging.yaml` (non-secret params).
- [ ] Manifest templates: either Compose production overlay or k8s Deployment snippets under `infra/llm-gateway/k8s/` (choose platform at execute; default provide **both** Compose prod overlay + generic k8s as reference).
- [ ] TLS via existing ingress assumption documented.
- [ ] Smoke identity: low budget, restricted models.
- [ ] Alerting hooks documented (Slack webhook optional via LiteLLM `alerting`).

---

### WP17 — Production hardening

**Goal:** Match LiteLLM production guidance for the pin.  
**Owner:** L2/L6.

**Checklist (from official prod docs + this plan):**

- [ ] Pinned digests
- [ ] `LITELLM_MODE=PRODUCTION`, JSON logs, non-verbose
- [ ] `proxy_batch_write_at: 60`, pool limits
- [ ] `request_timeout: 600` (tune per SLO)
- [ ] `num_workers: 1`, scale out pods
- [ ] Redis when replicas > 1; host/port/password not redis_url
- [ ] Salt/master in secret manager; recovery runbook
- [ ] Admin UI not public without SSO/network control
- [ ] Postgres backups + restore drill documented
- [ ] Upgrade/rollback notes tested once (prior image)

---

### WP18 — Documentation and final evidence index

**Goal:** Handoff completeness.  
**Owner:** L8.

**Create:**

```text
docs/llm-platform/
  architecture.md
  operating-guide.md
  provider-onboarding.md
  application-migration.md
  incident-recovery.md
  cost-reconciliation.md
  privacy-and-retention.md
docs/evidence/
  README.md          # index of runs
  templates/
```

**Final report:** `docs/evidence/MILESTONE-REPORT.md` with every DoD item → evidence pointer, distinguishing configured vs exercised vs verified.

---

### WP19 — Consolidated ops CLI

**Goal:** Replace script sprawl.  
**Owner:** L3/L5.

**Commands:**

```text
llg secrets generate
llg config validate
llg config render
llg up | down | logs
llg health
llg keys create | list | revoke
llg smoke --alias ...
llg reconcile-cost --run-id ...
```

Migrate `scripts/*.py` into package modules; keep thin wrappers only if needed for entry points.

---

# 16. Verification matrix

| Layer | What | Command / method | Gate |
| --- | --- | --- | --- |
| Static | Ruff, mypy, tsc, config validate, compose config, image pin check, JSON Schema | `uv run ruff`, `uv run pytest` (unit), `pnpm typecheck`, `llg config validate`, compose config, CI pin job | PR |
| Unit | Metadata schema, secret generators, error mapping, alias uniqueness | `uv run pytest tests/unit` | PR |
| Integration (hermetic) | Client against mock gateway | pytest + respx/httpx mock | PR |
| Integration (live) | Health, keys, providers, stream/tools, persistence | `LLG_LIVE=1 uv run pytest tests/integration` | Pre-release |
| Live provider | 4 providers smoke matrix | `llg smoke` | Pre-release |
| Failure | §13 suite subset | live compose + chaos | Pre-release |
| Cost | Reconciliation script | `llg reconcile-cost` | Pre-release |
| Security | gitleaks, dependency audit, no master key in examples | CI | PR |
| Human ops | UI access control, backup restore, salt backup existence | Checklist sign-off | Release |

**Separate CI workflows:**

1. `ci.yml` — hermetic always.
2. `live-smoke.yml` — manual or nightly with secrets.

---

# 17. Failure and recovery matrix

| Failure | Expected behavior | Detection | Recovery |
| --- | --- | --- | --- |
| LiteLLM down | Apps get `GatewayUnavailable`; **no** direct provider call | App metrics, uptime checks | Restart pods; failover secondary gateway only if designed |
| Postgres down | Readiness fail; instance out of LB; no pretend auth | Readiness probe | Restore DB; do not enable fail-open without ADR |
| Redis down (if enabled) | Document: fail-closed shared RPM **or** degrade cache; test chosen behavior | Probe + integration test | Fix Redis; avoid claiming multi-repl correctness until green |
| Langfuse down | LLM succeeds; export errors bounded; drop counter/log | Proxy logs/metrics | Restore Langfuse; accept telemetry gap |
| Provider 429/5xx | Retry policy then normalized error; optional explicit fallback | LiteLLM logs + Langfuse error gen | Provider status; fallback only if configured |
| Budget exceeded | Fail closed `BudgetExceeded` | 4xx distinct body | Raise budget or reduce traffic |
| Wrong salt key | Encrypted secrets unreadable; startup/admin failure | Boot errors | Restore correct salt from offline backup |
| Invalid config / missing provider key | Clear readiness or per-alias error; do not silent-skip without status | Config validate + smoke | Fix env |
| Streaming interrupt | Client surfaces error; partial trace marked error | Tests | Retry at app with new request_id |
| Key leak | Revoke virtual key; rotate provider keys if exposed; audit spend | Incident runbook | `llg keys revoke`; provider console |

---

# 18. Risks, assumptions, and unresolved questions

### Confirmed facts (repo)

- Scaffold exists with Compose, LiteLLM YAML, unit tests, CI.
- Default image is unpinned `main-stable`.
- `STORE_MODEL_IN_DB` defaults True in compose (authority conflict).
- No integration/live tests; no client package; no llm-platform docs.
- Package managers are npm/pip, not uv/pnpm.
- Latest GitHub release observed: **v1.92.0** (2026-07-12).
- `main-stable` digest observed at plan time: `sha256:9ef6f45bc0…` (moving tag—do not use as prod pin).

### Strongly supported conclusions

- Greenfield platform repo can prove DoD via reference workflow without external apps, but org-wide “no raw credentials” requires external migration work beyond this repo.
- Langfuse Cloud is correct default.
- YAML-as-SoT is safer than UI/DB dual registry for this team size.

### Assumptions

- Stakeholders accept reference-app as first vertical slice.
- Provider accounts exist or will be provided before WP6.
- Langfuse Cloud region will be chosen (EU default in scaffold).
- Prompt recording allowed for non-sensitive reference workload.

### Unresolved questions (cannot be answered by this repo alone)

1. Which external applications must migrate in milestone 1?
2. Privacy classification per workload (prompt retention)?
3. Production hosting target (ECS, EKS, VM, other) and secret manager product?
4. Exact LiteLLM Docker tag string for v1.92.0 on GHCR?
5. Whether Responses API / embeddings are required on day one?
6. Cost tolerance final number after first reconciliation run?

### Blockers

- Live credentials (providers + Langfuse).
- Hosting/secret manager decision for staging/prod WP16–17.

### Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| OTEL correlation mismatch | Disconnected traces | Spike in WP10 before broad migration |
| Model ID churn | Broken aliases | Pin model IDs; alias changelog |
| LiteLLM security regressions | Credential exposure | Digest pins; upgrade process; network isolation |
| Cost field gaps per provider | Reconciliation fail | Document unpriced models; block alias if cost required |
| Scope creep into full AI platform | Delay | Non-goals enforced by L8 |

### Rejected approaches

See §12.

### Unrelated technical debt

- Scaffold examples still teach master-key fallback messaging—replace in WP11.
- Root-level dual compose vs future infra path—clean in WP2.
- Optional Azure/Cohere/Groq env stubs—keep only if needed.

---

# 19. Final evidence and handoff requirements

Executing agents must produce `docs/evidence/MILESTONE-REPORT.md` containing:

- Files / infra / secrets refs / DB / contracts changed
- Aliases and provider mappings
- Virtual keys/teams/budgets created (**ids only**, never secret tokens)
- Commands run + static/test results
- Provider smoke, stream/tools, health, persistence
- Langfuse trace + correlation evidence
- Cost reconciliation
- Failure matrix
- Security scan results
- Ops manual checks
- Upgrade/rollback procedure executed or dry-run
- Known failures, caveats, deferred work, unproven claims
- Deviations from this plan

**Distinguish explicitly:** code exists | config exists | config deployed | integration exercised | auto-verified | manually observed | inferred | unproven.

---

# 20. Definition of done

Milestone complete only when all hold with evidence pointers:

1. All four providers called via LiteLLM with virtual keys.  
2. Representative app needs no raw provider credential.  
3. Postgres persistence survives gateway restart.  
4. Model restrictions, budgets, rate limits proven.  
5. Stable aliases documented and tested.  
6. Provider failures → normalized actionable errors.  
7. Safe fallback proven **or** explicitly disabled with rationale.  
8. Every provider call in LiteLLM usage records.  
9. Every provider call expected Langfuse telemetry.  
10. Representative E2E correlated application trace.  
11. User/session/env/feature/release attribution per contract.  
12. Prompt/response recording follows privacy policy.  
13. Langfuse outage tested, bounded.  
14. Postgres outage removes unhealthy instances (readiness).  
15. Cost reconciled within approved tolerance.  
16. Secrets absent from git, logs, fixtures, telemetry.  
17. Production artifacts pinned.  
18. Upgrade, rollback, backup, key-recovery documented.  
19. Verification evidence indexed and reproducible.  
20. No completion claim from docs/config/screenshots alone.

---

# Execution brief (start here after approval)

| Item | Detail |
| --- | --- |
| **First work** | WP0 tooling migration + WP3 image pin research + WP2 layout/SoT (`STORE_MODEL_IN_DB=false`) |
| **Parallel immediately** | L4 metadata schema draft; L6 privacy/security doc stubs; L7 test design; L1 external inventory if access exists |
| **Remain blocked** | Live provider smokes (WP6+); staging/prod deploy (WP16–17) until hosting/secrets chosen; external app migrations until inventory access |
| **Highest-risk assumption** | App Langfuse root trace and LiteLLM `langfuse_otel` generation **correlate cleanly** on the pinned versions without custom glue |
| **Exact evidence before “complete”** | Live matrix for 4 providers; virtual-key ACL/budget/RPM tests; restart persistence; correlated trace JSON; Langfuse outage test; Postgres readiness fail test; cost reconciliation table; pin/digest proof; secret scan clean; MILESTONE-REPORT filled against DoD 1–20 |

---

## Task checklist for subagent-driven execution (post-approval)

Use one subagent per WP where possible; review gates after WP3, WP8, WP10, WP14, WP15, WP18.

- [ ] WP0 Toolchain uv/pnpm + CI  
- [ ] WP1 Inventory  
- [ ] WP2 Layout + SoT  
- [ ] WP3 Image digests  
- [ ] WP4 Secrets/env  
- [ ] WP5 Stack health + persistence  
- [ ] WP6 Four providers  
- [ ] WP7 Aliases  
- [ ] WP8 Keys/budgets/RPM  
- [ ] WP9 Langfuse OTEL  
- [ ] WP10 Metadata + correlation  
- [ ] WP11 Client library  
- [ ] WP12 Reference migration  
- [ ] WP13 Stream/tools matrix  
- [ ] WP14 Failure suite  
- [ ] WP15 Cost reconciliation  
- [ ] WP16 Staging package  
- [ ] WP17 Production hardening  
- [ ] WP18 Docs + evidence index  
- [ ] WP19 `llg` CLI consolidation  
- [ ] Final DoD audit + MILESTONE-REPORT  

---

*End of plan. No implementation performed in this step.*
