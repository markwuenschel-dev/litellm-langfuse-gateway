# dashboards/

Committed **exported** Langfuse dashboard JSON lands here — one file per board:

- `production-home.json`
- `cost-and-capacity.json`
- `quality-and-releases.json` (only if Langfuse **scores** exist)

These are **not present yet**: they are created by the build → export → commit → verify
sequence in `docs/llm-platform/langfuse-dashboards.md`. Each file must be a genuine
export from the Langfuse console, not hand-authored (the export schema is
version-specific and unstable — a fabricated file can fail import).

Blueprint (what each board should contain, and its groupable dimensions):
`docs/llm-platform/langfuse-dashboards.md`. Policy: ADR 0007.
