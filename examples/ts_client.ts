/**
 * Minimal OpenAI SDK client pointed at the local LiteLLM gateway.
 *
 * Uses a **virtual key only** — never the master key.
 * Always sends origin metadata so Langfuse can show which service called.
 *
 * Usage:
 *   export LITELLM_VIRTUAL_KEY=sk-...
 *   export LITELLM_BASE_URL=http://localhost:4000/v1
 *   export SERVICE_NAME=myapp
 *   pnpm install
 *   pnpm run example:ts
 */

import { randomUUID } from "node:crypto";
import OpenAI from "openai";

function disallowMaster(): boolean {
  const raw = process.env.LLG_DISALLOW_MASTER;
  if (raw === undefined || raw.trim() === "") return true;
  return !["0", "false", "no", "off"].includes(raw.trim().toLowerCase());
}

async function main(): Promise<void> {
  const apiKey = (process.env.LITELLM_VIRTUAL_KEY ?? "").trim();
  if (!apiKey) {
    console.error(
      "Set LITELLM_VIRTUAL_KEY (virtual key only; master key is admin-only).\n" +
        "See docs/llm-platform/app-wiring.md and infra/llm-gateway/.env.app.example",
    );
    process.exit(1);
  }
  if (!apiKey.startsWith("sk-")) {
    console.error(
      "LITELLM_VIRTUAL_KEY must start with 'sk-' (placeholder or wrong value).\n" +
        "Paste the key from `llg keys create`, not the variable name.",
    );
    process.exit(1);
  }

  const master = (process.env.LITELLM_MASTER_KEY ?? "").trim();
  if (disallowMaster() && master && apiKey === master) {
    console.error(
      "LITELLM_VIRTUAL_KEY must not be the master key (LLG_DISALLOW_MASTER).",
    );
    process.exit(1);
  }

  const service = (
    process.env.SERVICE_NAME ??
    process.env.LLG_SERVICE ??
    ""
  ).trim();
  if (!service) {
    console.error(
      "Set SERVICE_NAME so Langfuse can attribute this call " +
        "(see docs/llm-platform/call-attribution.md).",
    );
    process.exit(1);
  }

  const baseURL = process.env.LITELLM_BASE_URL ?? "http://localhost:4000/v1";
  const model = process.env.LITELLM_MODEL ?? "llm-general";
  const environment =
    process.env.ENVIRONMENT ?? process.env.LLG_ENVIRONMENT ?? "development";
  const feature =
    process.env.FEATURE_NAME ?? process.env.LLG_FEATURE ?? "chat";
  const release =
    process.env.GIT_SHA ??
    process.env.RELEASE ??
    process.env.LLG_RELEASE ??
    "dev";
  const requestId = randomUUID();

  const client = new OpenAI({ apiKey, baseURL });
  const response = await client.chat.completions.create({
    model,
    messages: [{ role: "user", content: "Reply with a single word: pong" }],
    max_tokens: 16,
    // LiteLLM accepts metadata on the request body for Langfuse / logging
    // @ts-expect-error OpenAI types may not list metadata
    metadata: {
      request_id: requestId,
      service,
      feature,
      environment,
      release,
      model_alias: model,
    },
  });

  console.log(`request_id=${requestId} service=${service} model=${model}`);
  console.log(response.choices[0]?.message?.content ?? "");
}

main().catch((err: unknown) => {
  console.error(err);
  process.exit(1);
});
