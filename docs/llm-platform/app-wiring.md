# App wiring: call the gateway from your product

**Goal:** Apps use **only** `LITELLM_BASE_URL` + `LITELLM_VIRTUAL_KEY` (and stable aliases). Provider keys and the LiteLLM master key stay on the proxy.

```text
Your app
  → LITELLM_BASE_URL (/v1) + LITELLM_VIRTUAL_KEY
  → model: llm-general (or other alias)
  → optional metadata + app Langfuse root trace
  ▼
LiteLLM Proxy
  → ACL / budget / RPM → providers
  → Langfuse generations (proxy callback)
  → Postgres spend
```

Related: [application-migration.md](./application-migration.md) (inventory + cutover), [architecture.md](./architecture.md), [privacy-and-retention.md](./privacy-and-retention.md).

---

## 1. Environment contract

**Template:** [`infra/llm-gateway/.env.app.example`](../../infra/llm-gateway/.env.app.example)

| Variable | App? | Notes |
| --- | --- | --- |
| `LITELLM_BASE_URL` | **Yes** | e.g. `http://localhost:4000/v1` or staging URL |
| `LITELLM_VIRTUAL_KEY` | **Yes** | Must start with `sk-`; from `llg keys create` |
| `LITELLM_MODEL` | Optional | Default `llm-general` |
| `LLG_DISALLOW_MASTER` | Optional | Default on — refuse master key as app key |
| `SERVICE_NAME` / `ENVIRONMENT` / `GIT_SHA` | **Strongly recommended** | Call origin in Langfuse (`GatewayClient` auto-sends metadata). See [call-attribution.md](./call-attribution.md) |
| `LLG_REQUIRE_ATTRIBUTION` | Optional | If `1`, refuse chat when `service` is unattributed |
| Provider API keys | **No** | Proxy Compose `.env` only |
| `LITELLM_MASTER_KEY` | **No** | Admin / `llg keys` only |
| `LITELLM_SALT_KEY` | **No** | Proxy encryption only |

**Common footgun:** setting `LITELLM_VIRTUAL_KEY` to the literal name of the variable or a non-`sk-` placeholder. LiteLLM will return auth errors (`expected to start with 'sk-'`).

---

## 2. Provision a virtual key (once per app × environment)

Operator shell (master key loaded for admin only — not into the app):

```powershell
cd <worktree-or-repo-root>

# Load master key for this shell only (example)
Get-Content .\infra\llm-gateway\.env | ForEach-Object {
  if ($_ -match '^\s*LITELLM_MASTER_KEY=(.+)$') {
    $env:LITELLM_MASTER_KEY = $matches[1].Trim().Trim('"').Trim("'")
  }
}
$env:LITELLM_BASE_URL = "http://localhost:4000"

uv run llg keys create `
  --models llm-general `
  --max-budget 50 `
  --rpm 120 `
  --key-alias myapp-dev `
  --metadata '{\"service\":\"myapp\",\"environment\":\"development\"}'
```

**Conventions**

| Practice | Why |
| --- | --- |
| One key per **service × environment** | Blast radius + spend attribution |
| Start with **`llm-general` only** | Avoid ACL denials; widen when needed |
| `--key-alias service-env` | Readable in Admin UI |
| Copy printed key once into app secrets | Never commit it |

Widen models only when the app must call them:

```text
--models llm-general,openai-general,gemini-general,grok-general,anthropic-general
```

Put the new key in the **app** env (or `.env.app` locally), not as a substitute for provider keys on the proxy.

---

## 3. Python (preferred: `GatewayClient`)

### Install from this repo

```powershell
# From your app, path-depend on this platform repo (adjust path)
uv add --editable ../litellm-langfuse-gateway
# or in the platform worktree itself:
uv sync --all-extras
```

Package provides: `llm_client.GatewayClient`, `RequestMetadata`, typed errors.

### Copy-paste

```python
import os

from llm_client import GatewayClient, GatewayConfig, GatewayError

client = GatewayClient(GatewayConfig.from_env())
model = os.environ.get("LITELLM_MODEL", "llm-general")
# Set SERVICE_NAME in the app env — chat() auto-attaches RequestMetadata.from_env
# when metadata is omitted. Prefer an explicit name over the unattributed default.

try:
    with client:
        result = client.chat(
            model=model,
            messages=[{"role": "user", "content": "Hello"}],
            # optional: metadata=RequestMetadata(...) for feature/trace overrides
        )
    print(result["choices"][0]["message"]["content"])
except GatewayError as exc:
    # See failure table below — do not fall back to raw provider keys
    raise
```

### Alternative: raw OpenAI SDK

Raw SDK clients **do not** send origin fields unless you pass them. Always set
`SERVICE_NAME` and include `metadata` (or use `GatewayClient`, which does this
for you). See [call-attribution.md](./call-attribution.md).

```python
import os
import uuid
from openai import OpenAI

model = os.environ.get("LITELLM_MODEL", "llm-general")
service = os.environ["SERVICE_NAME"]  # required for attribution

client = OpenAI(
    api_key=os.environ["LITELLM_VIRTUAL_KEY"],
    base_url=os.environ.get("LITELLM_BASE_URL", "http://localhost:4000/v1"),
)
client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "Hello"}],
    extra_body={
        "metadata": {
            "request_id": str(uuid.uuid4()),
            "service": service,
            "feature": "chat",
            "environment": os.environ.get("ENVIRONMENT", "development"),
            "release": os.environ.get("GIT_SHA", "dev"),
            "model_alias": model,
        }
    },
)
```

Runnable samples: `examples/reference_workflow.py` (full shape), `examples/python_client.py` (minimal + metadata).

---

## 4. TypeScript

```ts
import OpenAI from "openai";

const apiKey = process.env.LITELLM_VIRTUAL_KEY?.trim();
if (!apiKey?.startsWith("sk-")) {
  throw new Error("LITELLM_VIRTUAL_KEY must be a virtual key starting with sk-");
}

const client = new OpenAI({
  apiKey,
  baseURL: process.env.LITELLM_BASE_URL ?? "http://localhost:4000/v1",
});

const model = process.env.LITELLM_MODEL ?? "llm-general";

const response = await client.chat.completions.create({
  model,
  messages: [{ role: "user", content: "Hello" }],
  // Required for call attribution (LiteLLM → Langfuse). Prefer a real SERVICE_NAME.
  // @ts-expect-error OpenAI types may not list metadata
  metadata: {
    request_id: crypto.randomUUID(),
    service: process.env.SERVICE_NAME ?? "myapp",
    feature: "chat",
    environment: process.env.ENVIRONMENT ?? "development",
    release: process.env.GIT_SHA ?? "dev",
    model_alias: model,
  },
});
```

Runnable sample: `examples/ts_client.ts` (`pnpm run example:ts`).

---

## 5. Metadata and Langfuse

### Gateway generations (already on)

The proxy exports each completion to Langfuse (classic `langfuse` success/failure callback). You do **not** need to re-log the same generation in app code.

### Call attribution (who hit the gateway?)

**Full guide:** [call-attribution.md](./call-attribution.md)

`GatewayClient.chat()` **always** attaches metadata (explicit or from env). Raw
OpenAI SDK calls do not unless you pass `metadata` / `extra_body`.

### Required metadata (when using `RequestMetadata` / contract)

| Field | Purpose |
| --- | --- |
| `request_id` | Correlate logs and traces |
| `service` | App name |
| `feature` | Feature / route |
| `environment` | `development` / `staging` / `production` |
| `release` | Git SHA or version |
| `model_alias` | Alias requested |

Schema: `config/llm/metadata-contract.schema.json`.

### Native Langfuse dimensions (dashboards)

`GatewayClient` additionally derives **reserved keys** the classic `langfuse`
callback promotes to native Langfuse fields, so dashboards can group/filter
natively (not just read a metadata blob):

| Contract field | → native Langfuse | Note |
| --- | --- | --- |
| service + feature | `trace_name` / `generation_name` (`service:feature`) | readable observation names |
| release | `trace_release` | **not** `version` (release = deployment; version = component) |
| user_id | `trace_user_id` | native User view; **pseudonymous `usr_<opaque>` only** |
| session_id | native Session | flows under its own key |
| env/service/feature/model_alias | `tags` | low-cardinality filter/group; never tag ids |

This is automatic with `GatewayClient`. **Raw SDK callers must send these keys
themselves** (reference examples above) — reference parity, not enforced. See
`docs/llm-platform/langfuse-dashboards.md` and ADR 0007.

### Optional app-level Langfuse root

For multi-step workflows (retrieval → tools → model), create a **root** trace in the app and pass identifiers that LiteLLM/Langfuse can attach (e.g. `trace_id`, `session_id`, `user_id` per contract). Do not dual-write the completion itself unless you have a deliberate reason.

App Langfuse keys (if any) are separate from proxy keys; never put secret keys in browsers.

### Privacy

Do not put secrets, raw auth headers, or unnecessary PII in metadata. See [privacy-and-retention.md](./privacy-and-retention.md).

---

## 6. Failure behavior (app-facing)

| Error (`llm_client`) | Meaning | App should |
| --- | --- | --- |
| `GatewayAuthError` | Bad/revoked virtual key | Fix config; do not use master key |
| `ModelAccessDenied` | Key ACL blocked the alias | Widen key models or change alias |
| `BudgetExceeded` | Spend cap hit | Alert; raise budget or stop |
| `GatewayRateLimited` | RPM/TPM on gateway | Backoff / queue |
| `ProviderUnavailable` | Upstream provider after retries | Retry later; user-visible error |
| `GatewayUnavailable` | Proxy down / network | Fail, queue, or degrade **without** LLM — **no** silent `OPENAI_API_KEY` bypass |
| `GatewayTimeout` | Timed out | Retry with new `request_id` if safe |
| `GatewayConfigError` | Missing env / policy | Fix deploy config |

**Non-negotiable:** gateway failure must not silently reintroduce raw provider credentials in the app.

---

## 7. Verification checklist (“app is wired”)

| # | Check | How |
| --- | --- | --- |
| 1 | App env has base URL + virtual key only | Config review |
| 2 | Virtual key starts with `sk-` | Reject placeholders |
| 3 | No provider keys / master key in app | Grep deploy secrets |
| 4 | Model is a stable alias | Code review |
| 5 | Call returns 200 via gateway | App logs / smoke |
| 6 | Generation appears in Langfuse | Cloud UI (same region/project as proxy) |
| 7 | Spend moves on that virtual key | LiteLLM Admin UI `http://localhost:4000/ui` |

**Local prove (reference app):**

```powershell
$env:LLG_LIVE = "1"
$env:LITELLM_VIRTUAL_KEY = "sk-..."   # real virtual key
$env:LITELLM_BASE_URL = "http://localhost:4000/v1"
uv run python examples/reference_workflow.py
```

Then confirm a new trace in Langfuse and spend on the key in the Admin UI.

---

## 8. Aliases apps may use

Source of truth: `config/llm/model-aliases.yaml`.

| Alias | Typical use |
| --- | --- |
| `llm-general` | **Default product chat** |
| `openai-general` | Explicit OpenAI |
| `anthropic-general` | Explicit Anthropic |
| `gemini-general` | Explicit Gemini |
| `grok-general` | Explicit xAI/Grok |

Prefer `llm-general` unless you need a specific provider.

---

## 5-step quick start

1. Stack up: `uv run llg up` (or compose under `infra/llm-gateway/`).
2. Create key: `uv run llg keys create --models llm-general --max-budget 50 --rpm 120 --key-alias myapp-dev`.
3. Copy `infra/llm-gateway/.env.app.example` → app env; set virtual key + base URL.
4. Call with `GatewayClient` or OpenAI SDK (`base_url` / `baseURL` + virtual key).
5. Verify Langfuse trace + key spend.

That’s app wiring.
