# Application migration guide

Move first-party apps from direct provider SDKs (or ad-hoc keys) onto the LiteLLM OpenAI-compatible gateway with virtual keys and the metadata contract.

**Wiring how-to (copy-paste, env, verification):** see **[app-wiring.md](./app-wiring.md)** first.

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
3. **Provision a virtual key** per app × environment (see [app-wiring.md](./app-wiring.md) §2).
4. **Point the client** at the gateway ([app-wiring.md](./app-wiring.md) §3–4):
   - Python: `src/llm_client.GatewayClient` + `RequestMetadata`, or OpenAI SDK with `base_url` + virtual key.
   - TypeScript: OpenAI SDK `baseURL` + virtual key (`examples/ts_client.ts`).
5. **Attach metadata** (required fields: `request_id`, `service`, `feature`, `environment`, `release`, `model_alias`). Schema: `config/llm/metadata-contract.schema.json`.
6. **Instrument Langfuse** at the app layer for multi-step workflows (root trace, tools, retrieval). The **proxy** already exports each generation via the classic `langfuse` success/failure callback — do not dual-write the same generation unless deliberate.
7. **Remove provider keys** from the app secret set once traffic is verified through the gateway.
8. **Prove** with the [verification checklist](./app-wiring.md#7-verification-checklist-app-is-wired) (Langfuse trace + key spend).

## Reference path (in-repo)

| Artifact | Role |
| --- | --- |
| [app-wiring.md](./app-wiring.md) | **Primary** wiring runbook |
| `infra/llm-gateway/.env.app.example` | App-only env template |
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
