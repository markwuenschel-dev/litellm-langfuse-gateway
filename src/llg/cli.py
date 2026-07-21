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
    help=(
        "Canonical ops CLI for the LiteLLM + Langfuse gateway "
        "(config, secrets, stack, health, keys, smoke, reconcile-cost). "
        "scripts/* are thin wrappers only."
    ),
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
_RECONCILE_RUN_FILE = typer.Option(
    None,
    "--run-file",
    help="Path to YAML reconciliation run artifact (machine input). No network I/O.",
    exists=False,
    dir_okay=False,
    readable=True,
)
_RECONCILE_JSON = typer.Option(
    False,
    "--json",
    help="Emit exactly one structured result/error object on stdout (diagnostics on stderr).",
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

    from llm_client.proxy_url import proxy_root

    resolved = proxy_root(base_url)
    code, message = check_health(resolved, path=path, timeout=timeout)
    if code == 0:
        typer.echo(message)
    else:
        typer.echo(message, err=True)
        raise typer.Exit(code)


@app.command("up")
def up(
    redis_service: bool = typer.Option(
        False,
        "--redis-service",
        help=(
            "Also start the Redis *container* via compose.redis.yaml. "
            "Service only: does not configure shared Router state, caching, "
            "or virtual-key limits (no distributed-limit claim on this pin)."
        ),
    ),
    detach: bool = typer.Option(
        True,
        "--detach/--no-detach",
        "-d/-D",
        help="Run containers in the background (default: detach).",
    ),
) -> None:
    """Start LiteLLM + PostgreSQL via infra/llm-gateway/compose.yaml.

    Env file: infra/llm-gateway/.env only (never repo-root .env).
    """
    try:
        code = compose_up(redis_service=redis_service, detach=detach)
    except FileNotFoundError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc
    if code != 0:
        raise typer.Exit(code)


@app.command("down")
def down(
    redis_service: bool = typer.Option(
        False,
        "--redis-service",
        help="Include Redis service overlay when tearing down.",
    ),
    volumes: bool = typer.Option(
        False,
        "--volumes",
        "-v",
        help=(
            "Remove named volumes (destructive: drops Postgres data, which "
            "silently orphans every minted virtual key — consumer .envs keep "
            "the string but requests fail 401 token_not_found_in_db; re-mint "
            "with `llg keys create` after)."
        ),
    ),
) -> None:
    """Stop the gateway Compose stack."""
    try:
        code = compose_down(redis_service=redis_service, volumes=volumes)
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
        help=(
            "Comma-separated model allow-list of stable gateway aliases "
            "(from config/llm/model-aliases.yaml, e.g. llm-general)."
        ),
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
        help=(
            "Human-readable key alias (Admin UI / spend). Required unless "
            "--allow-anonymous-key. Use service-env e.g. myapp-dev."
        ),
    ),
    budget_duration: str = typer.Option(
        None,
        "--budget-duration",
        help="Budget window (e.g. 30d, 1h). Optional.",
    ),
    metadata: str = typer.Option(
        None,
        "--metadata",
        help=(
            'JSON object stored on the key (e.g. \'{"service":"myapp","environment":"dev"}\'). '
            "Defaults from --key-alias when omitted."
        ),
    ),
    allow_anonymous_key: bool = typer.Option(
        False,
        "--allow-anonymous-key",
        help="Allow create without --key-alias (not recommended; spend will not name the owner).",
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
    if not (key_alias or "").strip() and not allow_anonymous_key:
        typer.secho(
            "error: --key-alias is required so spend and Admin UI name the owner.\n"
            "  Example: --key-alias myapp-dev\n"
            "  Break-glass only: --allow-anonymous-key",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

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
    elif key_alias:
        # Default key metadata so Admin UI / spend lists show ownership.
        meta = {"service": key_alias, "environment": "development"}
    else:
        typer.secho(
            "warning: anonymous key — spend will not name an owner. "
            "Set SERVICE_NAME on every caller.",
            fg=typer.colors.YELLOW,
            err=True,
        )

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
    typer.echo(
        "Attribution: set SERVICE_NAME in the app env and prefer GatewayClient "
        "(always sends metadata). See docs/llm-platform/call-attribution.md",
        err=True,
    )
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


@app.command("smoke")
def smoke(
    alias: str = typer.Option(
        "llm-general",
        "--alias",
        help="Gateway model alias to smoke (e.g. llm-general, openai-general).",
    ),
    base_url: str = typer.Option(
        None,
        "--base-url",
        help="Proxy base URL (default: LITELLM_BASE_URL or http://localhost:4000/v1).",
    ),
    timeout: float = typer.Option(60.0, "--timeout", help="HTTP timeout in seconds."),
) -> None:
    """Live provider smoke via GatewayClient. Skips without LLG_LIVE=1.

    Requires LITELLM_VIRTUAL_KEY (not master) and a running stack with provider keys.
    Live smokes are UNPROVEN in hermetic CI; evidence: docs/evidence/.
    """
    if os.environ.get("LLG_LIVE") != "1":
        typer.secho(
            "SKIP: live smoke requires LLG_LIVE=1, a running gateway, "
            "LITELLM_VIRTUAL_KEY, and provider credentials.\n"
            "Hermetic CI does not run provider smokes. "
            "See docs/llm-platform/provider-compatibility-matrix.md and docs/evidence/.",
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(0)

    try:
        from llm_client import GatewayClient, GatewayConfig, RequestMetadata
    except ImportError as exc:
        typer.secho(f"llm_client not available: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    import uuid

    try:
        # Always load via from_env so master/provider key equality checks apply
        # even when --base-url overrides the transport endpoint.
        cfg = GatewayConfig.from_env(timeout=timeout)
        if base_url:
            from dataclasses import replace

            from llm_client.proxy_url import openai_base

            cfg = replace(cfg, base_url=openai_base(base_url))
    except Exception as exc:
        typer.secho(f"config error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2) from exc

    meta = RequestMetadata(
        request_id=str(uuid.uuid4()),
        service="llg-smoke",
        feature="smoke",
        environment="development",
        release="llg-smoke",
        model_alias=alias,
    )
    try:
        with GatewayClient(cfg) as client:
            result = client.chat(
                model=alias,
                messages=[{"role": "user", "content": "Reply with the single word: pong"}],
                metadata=meta,
                # Gemini 2.5/3.x thinking models can burn a small max_tokens budget
                # before any visible content is produced (content ends up null).
                max_tokens=256,
            )
    except Exception as exc:
        typer.secho(f"FAIL smoke alias={alias}: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    content = ""
    try:
        raw = result["choices"][0]["message"]["content"]
        content = "" if raw is None else str(raw)
    except (KeyError, IndexError, TypeError):
        content = str(result)[:200]
    if not content.strip():
        typer.secho(
            f"FAIL smoke alias={alias}: empty message content "
            f"(HTTP OK but no text — often max_tokens too low for thinking models)",
            fg=typer.colors.RED,
            err=True,
        )
        typer.echo(f"request_id={meta.request_id}")
        raise typer.Exit(1)
    typer.secho(f"OK smoke alias={alias}", fg=typer.colors.GREEN)
    typer.echo(f"request_id={meta.request_id}")
    typer.echo(f"content_preview={content[:120]!r}")


@app.command("reconcile-cost")
def reconcile_cost(
    run_file: Path | None = _RECONCILE_RUN_FILE,
    as_json: bool = _RECONCILE_JSON,
) -> None:
    """File-backed cost reconciliation (INT-116 / S1′).

    Without --run-file: print process guide and exit 2 (incomplete).

    With --run-file: validate YAML + run pure engine (no LLG_LIVE required).
    Exit 0 = complete + within tolerance; 1 = complete + outside; 2 = incomplete/invalid.

    Process: docs/llm-platform/cost-reconciliation.md
    Human template (not parser input): docs/evidence/templates/cost-recon.md
    """
    from llg.reconcile_cost import LoadError, format_human, format_json, load_run, reconcile

    if run_file is None:
        typer.echo("llg reconcile-cost — process guide (INT-116 / S1′)")
        typer.echo("")
        typer.echo(
            "Machine input: YAML run file with provider + litellm + langfuse amounts "
            "(Decimal strings), equal UTC half-open periods, retained evidence_ref per source."
        )
        typer.echo("Usage:")
        typer.echo("  uv run llg reconcile-cost --run-file path/to/run.yaml")
        typer.echo("  uv run llg reconcile-cost --run-file path/to/run.yaml --json")
        typer.echo("")
        typer.echo("See: docs/llm-platform/cost-reconciliation.md")
        typer.echo("Evidence template (human narrative): docs/evidence/templates/cost-recon.md")
        typer.secho(
            "INCOMPLETE: no --run-file. This command does not invent numbers. Exit 2.",
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(2)

    try:
        run = load_run(run_file)
        result = reconcile(run)
    except LoadError as exc:
        if as_json:
            payload = {
                "ok": False,
                "error": str(exc),
                "reason_code": exc.code,
                "exit_code": 2,
            }
            typer.echo(json.dumps(payload, indent=2, sort_keys=True))
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
        else:
            typer.secho(f"INVALID run file: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2) from exc

    if as_json:
        typer.echo(format_json(result), nl=False)
        if result.exit_code != 0:
            typer.secho(
                f"reconcile-cost reason={result.reason_code} exit={result.exit_code}",
                fg=typer.colors.YELLOW if result.exit_code == 1 else typer.colors.RED,
                err=True,
            )
    else:
        typer.echo(format_human(result), nl=False)
    raise typer.Exit(result.exit_code)


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
