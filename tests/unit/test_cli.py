"""Unit tests for the llg Typer CLI (no live stack)."""

from __future__ import annotations

from typer.testing import CliRunner

from llg.cli import app
from llg.paths import DEFAULT_CONFIG

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "config" in result.stdout
    assert "secrets" in result.stdout
    assert "health" in result.stdout
    assert "up" in result.stdout
    assert "down" in result.stdout
    assert "keys" in result.stdout


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "llg" in result.stdout


def test_config_validate_default() -> None:
    result = runner.invoke(app, ["config", "validate"])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "OK:" in result.stdout
    assert DEFAULT_CONFIG.name in result.stdout or "litellm-config.yaml" in result.stdout


def test_config_validate_missing(tmp_path) -> None:  # type: ignore[no-untyped-def]
    missing = tmp_path / "nope.yaml"
    result = runner.invoke(app, ["config", "validate", str(missing)])
    assert result.exit_code == 1
    assert "INVALID" in result.stdout or "INVALID" in result.stderr


def test_secrets_generate_env() -> None:
    result = runner.invoke(app, ["secrets", "generate", "--format", "env"])
    assert result.exit_code == 0
    assert "LITELLM_MASTER_KEY=sk-" in result.stdout
    assert "LITELLM_SALT_KEY=sk-" in result.stdout
    assert "POSTGRES_PASSWORD=" in result.stdout


def test_health_help() -> None:
    result = runner.invoke(app, ["health", "--help"])
    assert result.exit_code == 0
    assert "--path" in result.stdout


def test_smoke_skips_without_llg_live(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("LLG_LIVE", raising=False)
    result = runner.invoke(app, ["smoke", "--alias", "llm-general"])
    assert result.exit_code == 0
    combined = result.stdout + result.stderr
    assert "SKIP" in combined or "LLG_LIVE" in combined


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
