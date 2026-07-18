"""Ops helpers for the LiteLLM + Langfuse gateway.

Prefer the consolidated CLI (`uv run llg`):

    uv run llg --help
    uv run llg config validate
    uv run llg secrets generate
    uv run llg health
    uv run llg up | down
    uv run llg keys create | list | revoke
    uv run llg smoke
    uv run llg reconcile-cost

This package only re-exports a subset (validate_config, generate_secrets,
healthcheck) for backward compatibility. smoke and reconcile-cost exist only
as `llg` subcommands — there are no scripts/* shims for them.
"""
