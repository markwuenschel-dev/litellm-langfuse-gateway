# Upgrade notes — LLM gateway

Stub for image pins, LiteLLM release bumps, and breaking config changes (WP3+).

## Current

- Stack path: `infra/llm-gateway/`
- Model registry SoT: `litellm-config.yaml` (`STORE_MODEL_IN_DB=False`)
- Image: `LITELLM_IMAGE` env override; default tag `ghcr.io/berriai/litellm:main-stable` (unpinned digest — WP3)

## Planned (WP3)

- Pin LiteLLM image to a specific release tag **and** digest
- CI check: fail on `latest` or undigested floating `main` tags
- Record chosen pin and any required config deltas here

## How to record a pin

1. Choose release (see LiteLLM releases / security advisories).
2. Set `LITELLM_IMAGE` in deploy env (tag + `@sha256:…`).
3. Note date, previous image, and any `litellm-config.yaml` changes in a dated section below.

## Changelog

| Date | Note |
| --- | --- |
| 2026-07-17 | Layout migration to `infra/llm-gateway/`; YAML SoT; `STORE_MODEL_IN_DB` default false |
