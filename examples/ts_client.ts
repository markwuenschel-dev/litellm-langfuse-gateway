/**
 * Minimal OpenAI SDK client pointed at the local LiteLLM gateway.
 *
 * Usage:
 *   export LITELLM_VIRTUAL_KEY=sk-...
 *   export LITELLM_BASE_URL=http://localhost:4000/v1
 *   npm install
 *   npm run example:ts
 */

import OpenAI from "openai";

async function main(): Promise<void> {
  const apiKey =
    process.env.LITELLM_VIRTUAL_KEY ?? process.env.LITELLM_MASTER_KEY;
  if (!apiKey) {
    console.error(
      "Set LITELLM_VIRTUAL_KEY (preferred) or LITELLM_MASTER_KEY in the environment.",
    );
    process.exit(1);
  }

  const baseURL = process.env.LITELLM_BASE_URL ?? "http://localhost:4000/v1";
  const model = process.env.LITELLM_MODEL ?? "gpt-4o-mini";

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
