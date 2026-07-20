# evidence/

Redacted proof that a committed dashboard works on the pinned stack. Capture per
`docs/evidence/templates/langfuse-correlation.md` (redacted IDs only — no prompts,
no secrets, no reversible identifiers).

Minimum evidence per dashboard (Gate 5, ADR 0007):

- Portable JSON **imports** successfully (into a second project).
- ≥1 **cost** widget groups correctly by `service:`.
- ≥1 **latency** widget groups correctly by `feature:`.
- **Release** comparison is populated (`trace_release`).
- Home can be set to the imported dashboard.
- User/session top-N widgets included **only** if live-proven (Metrics v2 group-by limit).

Also record the upstream verification this depends on:
- Gate 3 (`tests/integration/test_litellm_langfuse_pin.py`) result on pin v1.92.0.
- Live Cloud read-API check that tags/user/session/release/names/model/cost/latency appear.
