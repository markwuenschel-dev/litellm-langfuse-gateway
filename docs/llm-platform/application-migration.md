# Application migration guide (WP18)

Move first-party apps from direct provider SDKs (or ad-hoc keys) onto the LiteLLM OpenAI-compatible gateway with virtual keys and the metadata contract.

## Target shape

```text
App
  → LITELLM_BASE_URL (/v1) + LITELLM_VIRTUAL_KEY
  → model: stable alias (llm-general, …)
  → metadata: RequestMetadata / contract fields
  → optional: Langfuse app root trace (trace_id shared)
```

**Do not:** ship provider API keys or `LITELLM_MASTER_KEY` in app runtime env.

## Migration steps

1. **Inventory** current provider calls (model IDs, stream/tools/embeddings, secrets location). Use `docs/llm-platform/provider-call-inventory.md` as a template.
2. **Pick aliases** from `config/llm/model-aliases.yaml`. Prefer `llm-general` for default chat; use `*-general` only for deliberate provider A/B or smokes.
3. **Provision a virtual key** per app × environment:
   ```bash
   uv run llg keys create \
     --models llm-general \
     --max-budget 50 \
     --rpm 120 \
     --key-alias myapp-staging \
     --metadata '{"service":"myapp","environment":"staging"}'
   ```
4. **Point the client** at the gateway:
   - Python: `src/llm_client.GatewayClient` + `RequestMetadata`, or OpenAI SDK with `base_url` + virtual key.
   - TypeScript: OpenAI SDK `baseURL` + virtual key (`examples/ts_client.ts`).
5. **Attach metadata** (required fields: `request_id`, `service`, `feature`, `environment`, `release`, `model_alias`). Schema: `config/llm/metadata-contract.schema.json`.
6. **Instrument Langfuse** at the app layer for workflows (root trace, tools, retrieval). Do not dual-write the same generation LiteLLM already exports via `langfuse_otel` unless deliberate.
7. **Remove provider keys** from the app secret set once traffic is verified through the gateway.
8. **Prove** with a staging smoke (`LLG_LIVE=1`) and redacted evidence if claiming production readiness.

## Reference path (in-repo)

| Artifact | Role |
| --- | --- |
| `examples/reference_workflow.py` | End-to-end shape: virtual key, alias, metadata |
| `src/llm_client/` | Hardened client + error contract |
| `examples/python_client.py` / `ts_client.ts` | Minimal OpenAI-compatible samples |

## Compatibility notes

| Concern | Guidance |
| --- | --- |
| Stream / tools / structured | Check `provider-compatibility-matrix.md` — cells are **unproven** until live |
| Fallbacks | **Disabled** by default (semantic risk); fail closed or app-level retry |
| Gateway down | No silent direct-provider bypass; surface `GatewayUnavailable` |
| Master key | `LLG_DISALLOW_MASTER` default on in `GatewayClient` |
| Embeddings / images / audio | Not part of the initial alias set; add only with a consumer + onboarding PR |

## External apps

This repository is a **platform** repo. Org-wide “no raw provider credentials” requires inventory and migration of external consumers outside this tree. Track those apps in your org inventory; the reference workflow only proves the platform path.
