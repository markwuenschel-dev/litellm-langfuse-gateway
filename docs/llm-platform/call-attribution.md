# Call attribution — who hit the gateway?

When a generation appears in Langfuse (or spend in LiteLLM) and you do not
recognize the prompt, use these layers. **Identity is multi-signal** — raw
OpenAI-SDK clients historically sent almost none of them.

```text
                    request
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
   virtual key    model alias    metadata
   (key_alias)    (llm-general)  (service, feature, …)
         │             │             │
         └─────────────┴─────────────┘
                       │
                       ▼
              Langfuse generation
              LiteLLM spend / logs
```

## Layers (check in order)

| # | Signal | Where to look | Who sets it |
| --- | --- | --- | --- |
| 1 | **Virtual key alias** | LiteLLM Admin → Virtual Keys; spend by key | `llg keys create --key-alias myapp-dev` |
| 2 | **Key metadata** | Same key record (`service`, `environment`) | `--metadata` or auto from `--key-alias` |
| 3 | **Request metadata** | Langfuse generation metadata / LiteLLM request metadata | App: `GatewayClient` + `SERVICE_NAME` / `RequestMetadata` |
| 4 | **Model** | Alias on the generation (`llm-general`, …) | Request `model` field |
| 5 | **Time + budget** | When it ran; which key is near budget | Ops |

If **(1)** is a shared/master/placeholder key and **(3)** is missing or
`service=unattributed`, you will not know the app.

## Required app practice

### Prefer `GatewayClient` (Python)

Every `chat()` call **always** sends metadata:

- Explicit `metadata=RequestMetadata(...)`, or
- Auto from env via `RequestMetadata.from_env(model_alias=…)` when metadata is omitted

| Env | Metadata field | Default if unset |
| --- | --- | --- |
| `SERVICE_NAME` or `LLG_SERVICE` | `service` | `unattributed` |
| `FEATURE_NAME` or `LLG_FEATURE` | `feature` | `chat` |
| `ENVIRONMENT` or `LLG_ENVIRONMENT` | `environment` | `development` |
| `GIT_SHA` / `RELEASE` / `LLG_RELEASE` | `release` | `unknown` |

**Strict mode:** set `LLG_REQUIRE_ATTRIBUTION=1` to **refuse** calls with
`service=unattributed` (fail closed until `SERVICE_NAME` is set).

### Raw OpenAI SDK (Python / TypeScript)

The OpenAI SDK does **not** send the metadata contract unless you pass it:

```python
client.chat.completions.create(
    model="llm-general",
    messages=[...],
    extra_body={
        "metadata": {
            "request_id": str(uuid.uuid4()),
            "service": os.environ["SERVICE_NAME"],
            "feature": "chat",
            "environment": "development",
            "release": os.environ.get("GIT_SHA", "dev"),
            "model_alias": "llm-general",
        }
    },
)
```

Without that, Langfuse only sees proxy-level signals (key + model + prompt).

## Provision keys so spend names the owner

```powershell
uv run llg keys create `
  --models llm-general `
  --max-budget 50 `
  --rpm 120 `
  --key-alias myapp-dev `
  --metadata '{\"service\":\"myapp\",\"environment\":\"development\"}'
```

`--key-alias` is **required** (use `--allow-anonymous-key` only as break-glass).

- One key per **service × environment**.
- Never share one virtual key across unrelated apps.
- Never put the **master** key in an app (Langfuse will not tell apps apart).
- Local caller template: copy `infra/llm-gateway/.env.app.example` → `.env.app`
  (gitignored), set `SERVICE_NAME` + virtual key.

## Langfuse UI — practical filters

1. Open the generation → inspect **metadata** for `service`, `feature`, `request_id`, `model_alias`.
2. If `service` is `unattributed` → client used GatewayClient without `SERVICE_NAME`, or raw SDK without metadata.
3. Cross-check **time window** with `uv run llg keys list` (key aliases / spend).
4. App-root traces (if the app uses Langfuse SDK) should share `trace_id` / `session_id` with the contract when set.

## Interpreting the mystery call you saw

Prompt like `stable` / `dynamic` with a long essay:

| If you see | Likely source |
| --- | --- |
| `service=llg-smoke` | `uv run llg smoke` |
| `service=llg-live` / test key aliases `llg-budget-*` | Live integration tests |
| `service=unattributed` or empty metadata | Raw client / missing SERVICE_NAME |
| Key alias `myapp-dev` | That app’s virtual key |
| Master key / no alias | Admin UI, curl with master, or misconfigured app |

Platform repo hermetic CI and pin-spike **do not** call real OpenAI; live
smokes only run when `LLG_LIVE=1` on a running stack.

## Related

- [app-wiring.md](./app-wiring.md) — env + GatewayClient
- [privacy-and-retention.md](./privacy-and-retention.md) — what not to put in metadata
- Schema: `config/llm/metadata-contract.schema.json`
