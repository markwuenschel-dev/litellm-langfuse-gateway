# ADR 0005 — `config/llm/environments/*.yaml` are docs-only checklists

## Status

Accepted (2026-07) — INT-006

## Context

`development.yaml` / `staging.yaml` / `production.yaml` described redis_required,
logging posture, and mode flags, but nothing in `src/` or CI loaded them.
Operators could treat them as live contracts while runtime always used
`litellm-config.yaml` + Compose env.

## Decision

**Demote** these files to **human ops checklists** (non-secret intent only):

- Not loaded by LiteLLM, `llg`, or Compose as configuration.
- Not enforced by CI beyond “files exist and parse as YAML with an `environment:` key.”
- Runtime posture remains: `litellm-config.yaml`, Compose, and secret-manager / `.env`.

Enforcing them as a second runtime SoT would require a deliberate render/wire
project (out of scope). Prefer one live config surface.

## Consequences

- Docs and file headers must say “docs only / not runtime.”
- A hermetic test fails if `src/` starts importing these paths as live config.
- Future “enforce environments YAML” needs a new ADR and a single load path.
