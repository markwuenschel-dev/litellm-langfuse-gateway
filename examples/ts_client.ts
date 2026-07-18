/**
 * Minimal OpenAI SDK client pointed at the local LiteLLM gateway.
 *
 * Uses a **virtual key only** — never the master key.
 *
 * Usage:
 *   export LITELLM_VIRTUAL_KEY=sk-...
 *   export LITELLM_BASE_URL=http://localhost:4000/v1
 *   pnpm install
 *   pnpm run example:ts
 */

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

  const baseURL = process.env.LITELLM_BASE_URL ?? "http://localhost:4000/v1";
  const model = process.env.LITELLM_MODEL ?? "llm-general";

  const client = new OpenAI({ apiKey, baseURL });
  const response = await client.chat.completions.create({
    model,
    messages: [{ role: "user", content: "Reply with a single word: pong" }],
    max_tokens: 16,
  });

  console.log(response.choices[0]?.message?.content ?? "");
}

main().catch((err: unknown) => {
  console.error(err);
  process.exit(1);
});
