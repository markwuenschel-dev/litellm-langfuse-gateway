"""Tests for llg.validate_config (and scripts re-export)."""

from __future__ import annotations

from pathlib import Path

import yaml

from llg.paths import REPO_ROOT
from llg.validate_config import validate_config
from scripts.validate_config import validate_config as scripts_validate_config


def test_repo_config_is_valid() -> None:
    path = REPO_ROOT / "infra" / "llm-gateway" / "litellm-config.yaml"
    assert path.is_file()
    assert validate_config(path) == []


def test_scripts_reexport_same_result() -> None:
    path = REPO_ROOT / "infra" / "llm-gateway" / "litellm-config.yaml"
    assert scripts_validate_config(path) == validate_config(path)


def test_missing_file() -> None:
    errors = validate_config(Path("/nonexistent/litellm_config.yaml"))
    assert errors
    assert "not found" in errors[0].lower()


def test_rejects_literal_api_key(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        yaml.dump(
            {
                "model_list": [
                    {
                        "model_name": "demo",
                        "litellm_params": {
                            "model": "openai/gpt-4o-mini",
                            "api_key": "sk-literal-secret",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    errors = validate_config(path)
    assert any("os.environ" in e for e in errors)


def test_rejects_duplicate_model_names(tmp_path: Path) -> None:
    path = tmp_path / "dup.yaml"
    path.write_text(
        yaml.dump(
            {
                "model_list": [
                    {
                        "model_name": "gpt-4o-mini",
                        "litellm_params": {
                            "model": "openai/gpt-4o-mini",
                            "api_key": "os.environ/OPENAI_API_KEY",
                        },
                    },
                    {
                        "model_name": "gpt-4o-mini",
                        "litellm_params": {
                            "model": "openai/gpt-4o-mini",
                            "api_key": "os.environ/OPENAI_API_KEY",
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    errors = validate_config(path)
    assert any("duplicate" in e for e in errors)
