"""Typer CLI entrypoint: `llg`."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import typer

from llg import __version__
from llg.compose_ops import compose_down, compose_up
from llg.generate_secrets import main as secrets_main
from llg.healthcheck import HEALTH_PATHS, check_health
from llg.keys import KeyClient, KeyClientError, default_base_url, require_master_key
from llg.paths import DEFAULT_CONFIG
from llg.validate_config import validate_config

app = typer.Typer(
    name="llg",
    help="Ops CLI for the LiteLLM + Langfuse gateway (config, secrets, stack, health, keys).",
    no_args_is_help=True,
    add_completion=False,
)

config_app = typer.Typer(help="Config validation helpers.", no_args_is_help=True)
secrets_app = typer.Typer(help="Secret generation helpers.", no_args_is_help=True)
keys_app = typer.Typer(
    help="Virtual key admin (create / list / revoke). Requires LITELLM_MASTER_KEY.",
    no_args_is_help=True,
)

app.add_typer(config_app, name="config")
app.add_typer(secrets_app, name="secrets")
app.add_typer(keys_app, name="keys")

# Module-level defaults avoid ruff B008 (function call in argument defaults).
_CONFIG_PATH_ARG = typer.Argument(
    None,
    help=f"Path to litellm config YAML (default: {DEFAULT_CONFIG})",
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"llg {__version__}")
        raise typer.Exit(0)


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """LiteLLM Langfuse Gateway ops CLI."""


@config_app.command("validate")
def config_validate(
    path: Path | None = _CONFIG_PATH_ARG,
) -> None:
    """Validate LiteLLM gateway config YAML (model_list, no literal secrets)."""
    target = path or DEFAULT_CONFIG
    errors = validate_config(target)
    if errors:
        typer.secho(f"INVALID: {target}", fg=typer.colors.RED, err=True)
        for err in errors:
            typer.echo(f"  - {err}", err=True)
        raise typer.Exit(1)
    typer.secho(f"OK: {target}", fg=typer.colors.GREEN)


@secrets_app.command("generate")
def secrets_generate(
    format: str = typer.Option(
        "env",
        "--format",
        help="Output format: env (KEY=value) or text (labeled lines).",
    ),
) -> None:
    """Generate master key, salt key, and DB passwords for .env bootstrap."""
    if format not in ("env", "text"):
        typer.secho("format must be 'env' or 'text'", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)
    code = secrets_main(["--format", format])
    raise typer.Exit(code)


@app.command("health")
def health(
    path: str = typer.Option(
        "/health/liveliness",
        "--path",
        help="Health endpoint path.",
    ),
    base_url: str = typer.Option(
        None,
        "--base-url",
        help="Proxy base URL without /v1 (default: LITELLM_BASE_URL or http://localhost:4000).",
    ),
    timeout: float = typer.Option(10.0, "--timeout", help="HTTP timeout in seconds."),
) -> None:
    """Probe LiteLLM liveliness / readiness / health endpoints."""
    if path not in HEALTH_PATHS:
        typer.secho(
            f"path must be one of: {', '.join(HEALTH_PATHS)}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

    resolved = (
        base_url
        or os.environ.get("LITELLM_BASE_URL", "http://localhost:4000").removesuffix("/v1")
    )
    code, message = check_health(resolved, path=path, timeout=timeout)
    if code == 0:
        typer.echo(message)
    else:
        typer.echo(message, err=True)
        raise typer.Exit(code)


@app.command("up")
def up(
    redis: bool = typer.Option(
        False,
        "--redis",
        help="Also start Redis via compose.redis.yaml overlay.",
    ),
    detach: bool = typer.Option(
        True,
        "--detach/--no-detach",
        "-d/-D",
        help="Run containers in the background (default: detach).",
    ),
) -> None:
    """Start LiteLLM + PostgreSQL via infra/llm-gateway/compose.yaml."""
    try:
        code = compose_up(redis=redis, detach=detach)
    except FileNotFoundError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc
    if code != 0:
        raise typer.Exit(code)


@app.command("down")
def down(
    redis: bool = typer.Option(
        False,
        "--redis",
        help="Include Redis overlay file when tearing down.",
    ),
    volumes: bool = typer.Option(
        False,
        "--volumes",
        "-v",
        help="Remove named volumes (destructive: drops Postgres data).",
    ),
) -> None:
    """Stop the gateway Compose stack."""
    try:
        code = compose_down(redis=redis, volumes=volumes)
    except FileNotFoundError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc
    if code != 0:
        raise typer.Exit(code)


def _key_client(
    base_url: str | None,
    master_key: str | None,
    timeout: float,
) -> KeyClient:
    try:
        resolved_key = require_master_key(master_key)
    except KeyClientError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(2) from exc
    return KeyClient(
        base_url=(base_url or default_base_url()).rstrip("/"),
        master_key=resolved_key,
        timeout=timeout,
    )


def _parse_models(models: str | None) -> list[str] | None:
    if models is None or models.strip() == "":
        return None
    parts = [m.strip() for m in models.split(",") if m.strip()]
    return parts or None


@keys_app.command("create")
def keys_create(
    models: str = typer.Option(
        None,
        "--models",
        help="Comma-separated model allow-list (gateway aliases).",
    ),
    max_budget: float = typer.Option(
        None,
        "--max-budget",
        help="Max spend budget in USD for this key.",
    ),
    rpm: int = typer.Option(
        None,
        "--rpm",
        help="Requests-per-minute limit (maps to rpm_limit).",
    ),
    tpm: int = typer.Option(
        None,
        "--tpm",
        help="Tokens-per-minute limit (maps to tpm_limit).",
    ),
    team_id: str = typer.Option(
        None,
        "--team-id",
        help="Optional LiteLLM team_id to attach the key to.",
    ),
    key_alias: str = typer.Option(
        None,
        "--key-alias",
        help="Human-readable key alias (shown in Admin UI / list).",
    ),
    budget_duration: str = typer.Option(
        None,
        "--budget-duration",
        help="Budget window (e.g. 30d, 1h). Optional.",
    ),
    metadata: str = typer.Option(
        None,
        "--metadata",
        help='Optional JSON object metadata (e.g. \'{"service":"ref-app","environment":"dev"}\').',
    ),
    base_url: str = typer.Option(
        None,
        "--base-url",
        help="Proxy base URL without /v1 (default: LITELLM_BASE_URL or http://localhost:4000).",
    ),
    master_key: str = typer.Option(
        None,
        "--master-key",
        help="Admin master key (default: LITELLM_MASTER_KEY). Never printed.",
        envvar="LITELLM_MASTER_KEY",
    ),
    timeout: float = typer.Option(30.0, "--timeout", help="HTTP timeout in seconds."),
    json_out: bool = typer.Option(
        False,
        "--json",
        help="Print full JSON response (includes key). Default: key token + warning.",
    ),
) -> None:
    """Create a virtual key (POST /key/generate). Prints the key once; do not commit it."""
    meta: dict[str, Any] | None = None
    if metadata:
        try:
            parsed = json.loads(metadata)
        except json.JSONDecodeError as exc:
            typer.secho(f"invalid --metadata JSON: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(2) from exc
        if not isinstance(parsed, dict):
            typer.secho("--metadata must be a JSON object", fg=typer.colors.RED, err=True)
            raise typer.Exit(2)
        meta = parsed

    client = _key_client(base_url, master_key, timeout)
    try:
        result = client.create(
            models=_parse_models(models),
            max_budget=max_budget,
            rpm=rpm,
            tpm=tpm,
            team_id=team_id,
            key_alias=key_alias,
            metadata=meta,
            budget_duration=budget_duration,
        )
    except KeyClientError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    if json_out:
        typer.echo(json.dumps(result, indent=2, default=str))
        return

    token = result.get("key") or result.get("token")
    if not token:
        typer.secho(
            "create succeeded but response had no key/token field; full body:",
            fg=typer.colors.YELLOW,
            err=True,
        )
        typer.echo(json.dumps(result, indent=2, default=str))
        raise typer.Exit(1)

    typer.secho(
        "WARNING: store this virtual key securely. It is shown once. Do not commit it.",
        fg=typer.colors.YELLOW,
        err=True,
    )
    if key_alias:
        typer.echo(f"key_alias={key_alias}", err=True)
    if result.get("token_id") or result.get("key_name"):
        # Non-secret ids only on stderr for ops notes
        for label, field in (("token_id", "token_id"), ("key_name", "key_name")):
            if result.get(field):
                typer.echo(f"{label}={result[field]}", err=True)
    typer.echo(str(token))


@keys_app.command("list")
def keys_list(
    page: int = typer.Option(1, "--page", help="Page number for /key/list."),
    size: int = typer.Option(100, "--size", help="Page size for /key/list."),
    team_id: str = typer.Option(None, "--team-id", help="Filter by team_id if supported."),
    base_url: str = typer.Option(
        None,
        "--base-url",
        help="Proxy base URL without /v1 (default: LITELLM_BASE_URL or http://localhost:4000).",
    ),
    master_key: str = typer.Option(
        None,
        "--master-key",
        help="Admin master key (default: LITELLM_MASTER_KEY). Never printed.",
        envvar="LITELLM_MASTER_KEY",
    ),
    timeout: float = typer.Option(30.0, "--timeout", help="HTTP timeout in seconds."),
) -> None:
    """List virtual keys (GET /key/list). Metadata only — not full secrets.

    If the proxy build lacks /key/list, use the Admin UI at the proxy base URL.
    """
    client = _key_client(base_url, master_key, timeout)
    try:
        result = client.list_keys(page=page, size=size, team_id=team_id)
    except KeyClientError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        if exc.status_code == 404:
            typer.secho(
                "Hint: /key/list unavailable on this proxy; use the Admin UI for key inventory.",
                fg=typer.colors.YELLOW,
                err=True,
            )
        raise typer.Exit(1) from exc
    typer.echo(json.dumps(result, indent=2, default=str))


@keys_app.command("revoke")
def keys_revoke(
    key: str = typer.Argument(..., help="Virtual key token to revoke (sk-...)."),
    mode: str = typer.Option(
        "delete",
        "--mode",
        help="delete (POST /key/delete, default) or block (POST /key/block).",
    ),
    base_url: str = typer.Option(
        None,
        "--base-url",
        help="Proxy base URL without /v1 (default: LITELLM_BASE_URL or http://localhost:4000).",
    ),
    master_key: str = typer.Option(
        None,
        "--master-key",
        help="Admin master key (default: LITELLM_MASTER_KEY). Never printed.",
        envvar="LITELLM_MASTER_KEY",
    ),
    timeout: float = typer.Option(30.0, "--timeout", help="HTTP timeout in seconds."),
    json_out: bool = typer.Option(False, "--json", help="Print full JSON response."),
) -> None:
    """Revoke a virtual key (delete or soft-block)."""
    if mode not in ("delete", "block"):
        typer.secho("mode must be 'delete' or 'block'", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)

    client = _key_client(base_url, master_key, timeout)
    try:
        result = client.revoke(key, mode=mode)
    except KeyClientError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    if json_out:
        typer.echo(json.dumps(result, indent=2, default=str))
    else:
        typer.secho(f"OK: key {mode}d", fg=typer.colors.GREEN)


def run() -> None:
    """Console-script entrypoint."""
    app()


if __name__ == "__main__":
    run()
