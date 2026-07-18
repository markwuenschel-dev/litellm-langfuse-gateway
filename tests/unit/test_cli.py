"""Unit tests for the llg Typer CLI (no live stack)."""

from __future__ import annotations

import re

from typer.testing import CliRunner

from llg.cli import app
from llg.paths import DEFAULT_CONFIG

runner = CliRunner()

# Rich/Typer help on CI may emit ANSI; strip for stable substring asserts.
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _plain(text: str) -> str:
    return _ANSI.sub("", text)


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    out = _plain(result.stdout)
    assert "config" in out
    assert "secrets" in out
    assert "health" in out
    assert "up" in out
    assert "down" in out
    assert "keys" in out


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "llg" in _plain(result.stdout)


def test_config_validate_default() -> None:
    result = runner.invoke(app, ["config", "validate"])
    assert result.exit_code == 0, result.stdout + result.stderr
    out = _plain(result.stdout)
    assert "OK:" in out
    assert DEFAULT_CONFIG.name in out or "litellm-config.yaml" in out


def test_config_validate_missing(tmp_path) -> None:  # type: ignore[no-untyped-def]
    missing = tmp_path / "nope.yaml"
    result = runner.invoke(app, ["config", "validate", str(missing)])
    assert result.exit_code == 1
    combined = _plain(result.stdout + result.stderr)
    assert "INVALID" in combined


def test_secrets_generate_env() -> None:
    result = runner.invoke(app, ["secrets", "generate", "--format", "env"])
    assert result.exit_code == 0
    out = _plain(result.stdout)
    assert "LITELLM_MASTER_KEY=sk-" in out
    assert "LITELLM_SALT_KEY=sk-" in out
    assert "POSTGRES_PASSWORD=" in out


def test_health_help() -> None:
    result = runner.invoke(app, ["health", "--help"])
    assert result.exit_code == 0
    out = _plain(result.stdout)
    # Rich may wrap flag names; accept either form
    assert "--path" in out or "path" in out.lower()


def test_smoke_skips_without_llg_live(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("LLG_LIVE", raising=False)
    result = runner.invoke(app, ["smoke", "--alias", "llm-general"])
    assert result.exit_code == 0
    combined = _plain(result.stdout + result.stderr)
    assert "SKIP" in combined or "LLG_LIVE" in combined


def test_smoke_base_url_still_rejects_master_key(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """--base-url must not bypass from_env master/provider equality checks."""
    monkeypatch.setenv("LLG_LIVE", "1")
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-master-admin-test")
    monkeypatch.setenv("LITELLM_VIRTUAL_KEY", "sk-master-admin-test")
    monkeypatch.delenv("LLG_DISALLOW_MASTER", raising=False)
    result = runner.invoke(
        app,
        ["smoke", "--alias", "llm-general", "--base-url", "http://proxy.test:4000/v1"],
    )
    assert result.exit_code == 2
    combined = _plain(result.stdout + result.stderr)
    assert "config error" in combined.lower() or "MASTER" in combined


def test_smoke_base_url_still_rejects_provider_key(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """--base-url must not bypass provider-key equality checks from from_env."""
    monkeypatch.setenv("LLG_LIVE", "1")
    monkeypatch.setenv("LITELLM_VIRTUAL_KEY", "sk-openai-provider-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-provider-secret")
    monkeypatch.delenv("LITELLM_MASTER_KEY", raising=False)
    monkeypatch.delenv("LLG_DISALLOW_MASTER", raising=False)
    result = runner.invoke(
        app,
        ["smoke", "--alias", "llm-general", "--base-url", "http://proxy.test:4000/v1"],
    )
    assert result.exit_code == 2
    combined = result.stdout + result.stderr
    assert "config error" in combined.lower() or "OPENAI" in combined


def test_reconcile_cost_stub_without_live(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("LLG_LIVE", raising=False)
    result = runner.invoke(app, ["reconcile-cost", "--run-id", "unit-test"])
    assert result.exit_code == 0
    combined = result.stdout + result.stderr
    assert "UNPROVEN" in combined or "reconcile" in combined.lower()
    assert "unit-test" in combined


def test_help_lists_smoke_and_reconcile() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "smoke" in result.stdout
    assert "reconcile-cost" in result.stdout
