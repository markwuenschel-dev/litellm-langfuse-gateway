# Langfuse dashboards (blueprint + operating guide)

How to turn the enriched telemetry (ADR 0007) into legible, sliceable Langfuse
dashboards. Langfuse is **Cloud** (ADR 0001): dashboards are built in the Cloud
console and shipped as **version-controlled JSON** under `observability/langfuse/`.

> Prerequisite: the native dimensions from ADR 0007 (`tags`, `trace_user_id`,
> `trace_release`, `trace_name`/`generation_name`) must be flowing. Until Gate 3
> (`tests/integration/test_litellm_langfuse_pin.py`) and a live Cloud check pass,
> some breakdowns below are **UNPROVEN** — do not treat this as verified.

## Groupable dimensions (what the widgets can slice by)

| Dimension | From | Group-by? |
| --- | --- | --- |
| Native provided **model** | LiteLLM generation | ✅ |
| `model_alias:` tag | gateway alias | ✅ (filter/group) |
| `env:` / `service:` / `feature:` tags | contract | ✅ |
| **release** | `trace_release` | ✅ |
| trace / generation **name** | `service:feature` | ✅ |
| **user** / **session** | `trace_user_id` / `session_id` | ⚠️ **filter-only** in Metrics API v2 — NOT group-by |

Cost, latency (incl. p95), tokens, and time-to-first-token are native generation
metrics. See [Metrics API v2](https://langfuse.com/docs/metrics/features/metrics-api).

## Three focused dashboards (avoid one cluttered board)

### 1. `production-home.json` (set as Home)
- **Top (stat):** total cost · request/generation count · p95 latency · error count.
- **Mid (time series):** cost by `service:` · p95 latency by `feature:` · cost by native model.
- **Bottom:** cost by release · latency by release · recent error observations (table).

### 2. `cost-and-capacity.json`
- Cost by native model · cost by `model_alias:` · cost by `service:` · cost by `feature:`.
- Input/output tokens over time · time-to-first-token by model · cache-hit (only if reliable).

### 3. `quality-and-releases.json` — **only if score data exists**
- Avg quality score by release · score distribution by `feature:` · cost-vs-quality by model.
- Error/refusal count by `feature:` · experiment-variant compare (`experiment_variant`).
- ⚠️ Do **not** ship this board implying quality monitoring exists just because
  observability data does — it requires real Langfuse **scores**.

### User / session views (conditional)
Metrics v2 forbids grouping by `userId`/`sessionId`. Default to the **native Users**
and **Sessions** views (already populated once `trace_user_id`/`session_id` flow).
Add "top-N users/sessions by cost" widgets **only** after live-proving the builder
supports the bounded query — set an explicit row limit + time range, never display
reversible identifiers.

## Build → export → commit → verify (the safe sequence)

1. Build the dashboard once in the Langfuse Cloud console ([custom dashboards](https://langfuse.com/docs/metrics/features/custom-dashboards)).
2. Export the validated widget/dashboard **JSON**.
3. Commit it to `observability/langfuse/dashboards/<name>.json`.
4. Prove it **imports** into another project (this is the acceptance criterion — the
   dashboard APIs are explicitly unstable, so do not depend on a custom API client).
5. Optionally add a pinned apply script — `pnpm dlx langfuse-cli@<pinned-version>`
   (never unpinned `npx`). Pin the CLI version in the script.
6. Capture redacted evidence under `observability/langfuse/evidence/` (see
   `docs/evidence/templates/langfuse-correlation.md`).

## Related
- ADR 0007 — reserved-key mapping, release-vs-version, cardinality, pin verification.
- `docs/llm-platform/call-attribution.md` — practical filters.
- `docs/llm-platform/privacy-and-retention.md` — pseudonymous user attribution.
