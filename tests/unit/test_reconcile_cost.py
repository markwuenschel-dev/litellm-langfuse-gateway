"""INT-116: file-backed cost reconciliation engine (S1′)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from llg.cli import app
from llg.paths import REPO_ROOT
from llg.reconcile_cost import (
    LoadError,
    load_run,
    pair_within,
    reconcile,
)

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "cost_recon"
runner = CliRunner()


def test_pair_within_doc_prime() -> None:
    within, diff, limit, rel = pair_within(
        Decimal("0.12"),
        Decimal("0.125"),
        relative=Decimal("0.05"),
        absolute=Decimal("0.01"),
    )
    assert within is True
    assert diff == Decimal("0.005")
    assert limit == Decimal("0.01")  # absolute floor wins over 5% of 0.125
    assert rel == Decimal("0.005") / Decimal("0.125")


def test_pair_zero_zero_relative_null() -> None:
    within, _diff, _limit, rel = pair_within(
        Decimal("0"),
        Decimal("0"),
        relative=Decimal("0.05"),
        absolute=Decimal("0.01"),
    )
    assert within is True
    assert rel is None


def test_load_and_reconcile_within_fixture() -> None:
    run = load_run(FIXTURES / "within.yaml")
    result = reconcile(run)
    assert result.exit_code == 0
    assert result.complete is True
    assert result.within_tolerance is True
    assert result.reason_code == "within_tolerance"
    assert len(result.groups) == 1
    assert result.groups[0].status == "within"
    assert len(result.groups[0].pairs) == 3
    assert all(p.within for p in result.groups[0].pairs)


def test_load_and_reconcile_outside_fixture() -> None:
    run = load_run(FIXTURES / "outside.yaml")
    result = reconcile(run)
    assert result.exit_code == 1
    assert result.complete is True
    assert result.within_tolerance is False
    assert result.reason_code == "outside_tolerance"
    assert result.groups[0].status == "outside"
    assert any(not p.within for p in result.groups[0].pairs)


def test_all_zero_amounts_exit_2(tmp_path: Path) -> None:
    data = yaml.safe_load((FIXTURES / "within.yaml").read_text(encoding="utf-8"))
    for src in data["groups"][0]["sources"]:
        src["amount"] = "0"
    path = tmp_path / "zero.yaml"
    path.write_text(yaml.dump(data), encoding="utf-8")
    result = reconcile(load_run(path))
    assert result.exit_code == 2
    assert result.reason_code == "unproven_zero_cost_group"


def test_missing_langfuse_not_green(tmp_path: Path) -> None:
    data = yaml.safe_load((FIXTURES / "within.yaml").read_text(encoding="utf-8"))
    data["groups"][0]["sources"] = [
        s for s in data["groups"][0]["sources"] if s["source_role"] != "langfuse"
    ]
    path = tmp_path / "two.yaml"
    path.write_text(yaml.dump(data), encoding="utf-8")
    result = reconcile(load_run(path))
    assert result.exit_code == 2
    assert result.complete is False


def test_unequal_periods_exit_2(tmp_path: Path) -> None:
    data = yaml.safe_load((FIXTURES / "within.yaml").read_text(encoding="utf-8"))
    data["groups"][0]["sources"][1]["period"]["end"] = "2026-07-19T02:00:00Z"
    path = tmp_path / "period.yaml"
    path.write_text(yaml.dump(data), encoding="utf-8")
    result = reconcile(load_run(path))
    assert result.exit_code == 2


def test_bare_float_amount_rejected(tmp_path: Path) -> None:
    data = yaml.safe_load((FIXTURES / "within.yaml").read_text(encoding="utf-8"))
    # Force bare float through YAML dump of a float
    data["groups"][0]["sources"][0]["amount"] = 0.125
    path = tmp_path / "float.yaml"
    path.write_text(yaml.dump(data), encoding="utf-8")
    with pytest.raises(LoadError, match="quoted decimal string"):
        load_run(path)


def test_negative_amount_rejected(tmp_path: Path) -> None:
    data = yaml.safe_load((FIXTURES / "within.yaml").read_text(encoding="utf-8"))
    data["groups"][0]["sources"][0]["amount"] = "-0.01"
    path = tmp_path / "neg.yaml"
    path.write_text(yaml.dump(data), encoding="utf-8")
    with pytest.raises(LoadError) as exc:
        load_run(path)
    assert exc.value.code == "negative_amount"


def test_dashboard_url_alone_rejected(tmp_path: Path) -> None:
    data = yaml.safe_load((FIXTURES / "within.yaml").read_text(encoding="utf-8"))
    data["groups"][0]["sources"][0]["evidence_ref"] = "https://platform.openai.com/usage"
    path = tmp_path / "dash.yaml"
    path.write_text(yaml.dump(data), encoding="utf-8")
    with pytest.raises(LoadError, match="retained export"):
        load_run(path)


def test_required_roles_cannot_drop_core(tmp_path: Path) -> None:
    data = yaml.safe_load((FIXTURES / "within.yaml").read_text(encoding="utf-8"))
    data["required_source_roles"] = ["provider", "litellm"]
    path = tmp_path / "roles.yaml"
    path.write_text(yaml.dump(data), encoding="utf-8")
    with pytest.raises(LoadError, match="langfuse"):
        load_run(path)


def test_cli_guide_no_run_file_exit_2() -> None:
    result = runner.invoke(app, ["reconcile-cost"])
    assert result.exit_code == 2
    assert "--run-file" in (result.stdout + result.stderr)
    assert "LLG_LIVE" not in (result.stdout + result.stderr)


def test_cli_run_file_within_exit_0_without_llg_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLG_LIVE", raising=False)
    result = runner.invoke(app, ["reconcile-cost", "--run-file", str(FIXTURES / "within.yaml")])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "within_tolerance" in result.stdout
    assert "provider" in result.stdout


def test_cli_run_file_outside_exit_1() -> None:
    result = runner.invoke(app, ["reconcile-cost", "--run-file", str(FIXTURES / "outside.yaml")])
    assert result.exit_code == 1
    assert "outside" in result.stdout


def test_cli_json_mode() -> None:
    result = runner.invoke(
        app,
        ["reconcile-cost", "--run-file", str(FIXTURES / "within.yaml"), "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["exit_code"] == 0
    assert payload["run_id"] == "fixture-within-2026-07-19"
    assert len(payload["groups"][0]["pairs"]) == 3


def test_cli_no_run_id_flag() -> None:
    # Fixed wide width so Rich does not wrap/truncate `--run-file` out of the
    # help text at CI's default 80 columns (option name must stay a substring).
    result = runner.invoke(app, ["reconcile-cost", "--help"], env={"COLUMNS": "200"})
    assert result.exit_code == 0
    assert "--run-id" not in result.stdout
    assert "--run-file" in result.stdout
