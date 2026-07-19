# ADR 0003 — Multi-provider fallbacks off by default

## Status

Accepted (2026-07)

## Context

LiteLLM router fallbacks can hide provider outages and mix stream/tools/structured
behavior across models. Compatibility is not proven for default aliases.

## Decision

Fallbacks remain **commented / empty** in `litellm-config.yaml` until each hop is
an explicit alias with a consumer and stream/tools/structured evidence exists
(see plan WP13 / provider-compatibility matrix).

## Consequences

- Failures surface as provider/gateway errors rather than silent model swaps.
- Enabling fallbacks is a product decision + ADR + evidence, not a quiet config flip.
