# observability/langfuse

Version-controlled Langfuse Cloud dashboard artifacts for this gateway.

- `dashboards/` — portable dashboard/widget **JSON**, produced by exporting a board
  built in the Langfuse console (NOT hand-authored). The dashboard/widget APIs are
  explicitly **unstable**, so the committed **JSON export is the stable artifact**;
  any CLI/API automation is an optional, version-pinned layer on top.
- `evidence/` — redacted proof that a dashboard imports and its widgets group
  correctly on the pinned stack.

## How to add a dashboard

Follow the safe sequence in `docs/llm-platform/langfuse-dashboards.md`:
**build in UI → export JSON → commit here → prove import into another project.**

Acceptance = *portable JSON import succeeds*, not "our API client stays compatible."

## Do not

- Do **not** hand-author files in `dashboards/` and present them as exports — a
  fabricated "export" can fail import or be mistaken for a validated artifact.
- Do **not** commit unredacted identifiers, prompts, or secrets in `evidence/`.
- Do **not** rely on grouping by `userId`/`sessionId` (Metrics v2 forbids it —
  filter-only). Use native Users/Sessions views. See ADR 0007.
