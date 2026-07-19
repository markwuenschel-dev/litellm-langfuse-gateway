# Slice Contract — INT-117 (bounded alias equality)

**Queue:** production-flywheel · PR #10  
**Design lane:** A (bounded contract grill)

## Grill decision (ratified)

**May a production `model_list` contain a runtime-only model route?**  
**No** arbitrary/undeclared runtime-only routes.

Contract upgrades from:

```text
semantic aliases ⊆ runtime model_list   (forward only)
```

to:

```text
semantic registry names = runtime model_list model_name set   (equality)
```

Future internal/eval routes must be **declared** in `model-aliases.yaml` with
`registry_role: internal` and non-empty `exemption_rationale` — never as
orphans in `model_list` alone.

## Rejected

- General config renderer (ADR 0006 settled; reopen ownership later)
- “Consumers enforcement” as real consumer graph (annotation-only today)
- Blind reverse orphan without an equality policy

## Behavior

1. When alias sync runs: every `model_list[].model_name` must appear under `aliases:`.
2. Every `aliases:` key must still appear in `model_list` with matching route/env (existing).
3. Optional `registry_role`: `app` (default) | `internal`.
4. `internal` requires `exemption_rationale` (non-empty string).
5. `load_stable_aliases()` returns **app** names only (default when role omitted) for key provision / app contract.
6. Equality uses the **full** registry name set (app + internal).

## Out of scope

- Config renderer
- Real consumers graph
- Auto-generating litellm-config from aliases

## Verification

```text
uv run pytest tests/unit/test_validate_config.py -q
uv run llg config validate
```

## Capture

- ADR 0006 amendment (equality + internal role)
- model-aliases.yaml header comment
