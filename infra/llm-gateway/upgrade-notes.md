# Upgrade notes — LLM gateway

Image pins, LiteLLM release bumps, and breaking config changes.

## Current pins (2026-07-17)

| Service | Ref (tag + multi-arch index digest) | Resolved version notes |
| --- | --- | --- |
| LiteLLM | `ghcr.io/berriai/litellm:v1.92.0@sha256:9ef6f45bc0104940571765e610c52a1d761b5ec85efcd193795281086ee61277` | GH release `v1.92.0` (2026-07-12). Tag discovery: `v1.92.0` exists on GHCR; `main-v1.92.0` / `main-v1.92.0-stable` **not found**. |
| Postgres | `postgres:16-alpine@sha256:57c72fd2a128e416c7fcc499958864df5301e940bca0a56f58fddf30ffc07777` | Manifest label `16.14-alpine3.24` |
| Redis | `redis:7-alpine@sha256:6ab0b6e7381779332f97b8ca76193e45b0756f38d4c0dcda72dbb3c32061ab99` | Manifest label `7.4.9-alpine` |

- Model registry SoT: `litellm-config.yaml` (`STORE_MODEL_IN_DB=False`)
- Override LiteLLM only via `LITELLM_IMAGE` (must stay `repo:tag@sha256:…`)
- CI: compose job enforces every `image:` line includes `@sha256:` and rejects floating `latest` / unpinned `main` / `main-stable`

## How to bump an image pin

1. **Choose target**
   - LiteLLM: pick a **stable** GitHub release ≥ current pin (`gh release list -R BerriAI/litellm`). Prefer non-`dev` / non-`rc` tags.
   - Postgres/Redis: prefer minor patch on the same major track (`16-alpine`, `7-alpine`) unless a major move is intentional.
2. **Resolve the real registry tag** (do not invent names):
   ```bash
   docker buildx imagetools inspect ghcr.io/berriai/litellm:vX.Y.Z
   # If missing, try documented GHCR variants from LiteLLM release notes — never invent.
   docker buildx imagetools inspect postgres:16-alpine
   docker buildx imagetools inspect redis:7-alpine
   ```
3. **Record the multi-arch index digest** (top-level `Digest:` from imagetools, not a single-platform manifest):
   ```bash
   docker buildx imagetools inspect <image>:<tag> --format "{{.Manifest.Digest}}"
   ```
4. **Edit compose**
   - `infra/llm-gateway/compose.yaml` — `postgres` + default `LITELLM_IMAGE`
   - `infra/llm-gateway/compose.redis.yaml` — `redis`
   - Form: `image: repo:tag@sha256:<64-hex>` (or `${LITELLM_IMAGE:-repo:tag@sha256:…}`)
5. **Validate**
   ```bash
   # dummy env
   set LITELLM_MASTER_KEY=sk-x LITELLM_SALT_KEY=sk-y POSTGRES_PASSWORD=x REDIS_PASSWORD=x  # bash: export …
   docker compose -f infra/llm-gateway/compose.yaml config --quiet
   docker compose -f infra/llm-gateway/compose.yaml -f infra/llm-gateway/compose.redis.yaml config --quiet
   ```
6. **Document** this file (table + changelog row): date, previous digest, new digest, reason, config deltas.
7. **Roll out** staging first; keep prior pin for rollback via `LITELLM_IMAGE=…@sha256:old`.

### Rollback

Set `LITELLM_IMAGE` (or revert the compose default) to the previous `tag@sha256:…` from the changelog. Do not roll back by switching to floating `main-stable` / `latest`.

## Forbidden production defaults

- `latest`
- Floating `main` or unpinned `main-stable` (moving tags)
- Tag-only refs without `@sha256:…` in `infra/llm-gateway/compose*.yaml`

## Changelog

| Date | Note |
| --- | --- |
| 2026-07-17 | **WP3:** Pin LiteLLM `v1.92.0`, Postgres `16-alpine`, Redis `7-alpine` by multi-arch digest; CI pin check; replace default `main-stable` |
| 2026-07-17 | Layout migration to `infra/llm-gateway/`; YAML SoT; `STORE_MODEL_IN_DB` default false |
