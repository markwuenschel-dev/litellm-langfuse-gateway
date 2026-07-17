"""Tests for scripts.validate_config."""

from __future__ import annotations

from pathlib import Path

import yaml

from scripts.validate_config import REPO_ROOT, validate_config


def test_repo_config_is_valid() -> None:
    path = REPO_ROOT / "config" / "litellm_config.yaml"
    assert path.is_file()
    assert validate_config(path) == []


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
