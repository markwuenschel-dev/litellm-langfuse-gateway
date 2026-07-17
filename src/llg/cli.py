"""Typer CLI entrypoint: `llg`."""

from __future__ import annotations

import os
from pathlib import Path

import typer

from llg import __version__
from llg.compose_ops import compose_down, compose_up
from llg.generate_secrets import main as secrets_main
from llg.healthcheck import HEALTH_PATHS, check_health
from llg.paths import DEFAULT_CONFIG
from llg.validate_config import validate_config

app = typer.Typer(
    name="llg",
    help="Ops CLI for the LiteLLM + Langfuse gateway (config, secrets, stack, health).",
    no_args_is_help=True,
    add_completion=False,
)

config_app = typer.Typer(help="Config validation helpers.", no_args_is_help=True)
secrets_app = typer.Typer(help="Secret generation helpers.", no_args_is_help=True)

app.add_typer(config_app, name="config")
app.add_typer(secrets_app, name="secrets")

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


def run() -> None:
    """Console-script entrypoint."""
    app()


if __name__ == "__main__":
    run()
