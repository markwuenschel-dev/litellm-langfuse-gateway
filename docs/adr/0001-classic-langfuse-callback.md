# ADR 0001 — Classic `langfuse` success/failure callback

## Status

Accepted (2026-07)

## Context

LiteLLM supports multiple Langfuse integration paths. On pin **v1.92.0**,
`langfuse_otel` initialized but did not reliably produce generations in the
Langfuse Cloud UI for this stack. The classic `langfuse` SDK callback produced
visible generation traces with the same `LANGFUSE_*` credentials when the host
matched the project region (US vs EU).

## Decision

Use classic callbacks in `litellm-config.yaml`:

```yaml
success_callback: ["langfuse"]
failure_callback: ["langfuse"]
```

`LANGFUSE_HOST` / `LANGFUSE_OTEL_HOST` must match the Langfuse project region.
LLM path must not fail if Langfuse is down.

## Consequences

- Operators set Cloud keys + correct region host; no self-hosted Langfuse by default.
- Changing to otel-only requires re-proof on the current pin and a new ADR.
