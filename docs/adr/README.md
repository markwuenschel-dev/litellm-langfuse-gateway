# Architecture Decision Records

Lightweight ADRs for irreversible or high-cost policy flips in this repo.

| ADR | Title | Status |
| --- | --- | --- |
| [0001](0001-classic-langfuse-callback.md) | Classic `langfuse` callback (not otel-only) | Accepted |
| [0002](0002-yaml-model-registry-sot.md) | YAML model registry is production SoT | Accepted |
| [0003](0003-fallbacks-off-by-default.md) | Multi-provider fallbacks off by default | Accepted |
| [0004](0004-redis-service-not-shared-limits.md) | Redis overlay is service-only on current pin | Accepted |
| [0005](0005-environments-yaml-docs-only.md) | environments/*.yaml are docs-only checklists | Accepted |
| [0006](0006-alias-authority-chain.md) | Alias SoT: model-aliases write + litellm-config runtime | Accepted |

## When to add an ADR

- Flipping model-registry SoT (YAML ↔ Admin UI/DB)
- Enabling multi-provider fallbacks
- Claiming distributed Redis control-state / shared virtual-key limits
- Changing Langfuse callback stack (classic vs otel-only)
- App contract changes that break virtual-key / alias consumers

Template: copy an existing ADR and keep the decision, context, consequences sections.
