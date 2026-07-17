"""Tests for llg.validate_config (and scripts re-export)."""

from __future__ import annotations

from pathlib import Path

import yaml

from llg.paths import REPO_ROOT
from llg.validate_config import (
    DEFAULT_ALIASES,
    STABLE_ALIASES,
    validate_config,
    validate_model_aliases,
)
from scripts.validate_config import validate_config as scripts_validate_config


def test_repo_config_is_valid() -> None:
    path = REPO_ROOT / "infra" / "llm-gateway" / "litellm-config.yaml"
    assert path.is_file()
    assert validate_config(path) == []


def test_repo_model_aliases_is_valid() -> None:
    assert DEFAULT_ALIASES.is_file()
    assert validate_model_aliases(DEFAULT_ALIASES) == []


def test_repo_config_exposes_stable_aliases() -> None:
    path = REPO_ROOT / "infra" / "llm-gateway" / "litellm-config.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    names = {e["model_name"] for e in raw["model_list"]}
    assert names >= STABLE_ALIASES


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


def test_rejects_model_without_provider_prefix(tmp_path: Path) -> None:
    path = tmp_path / "noprefix.yaml"
    path.write_text(
        yaml.dump(
            {
                "model_list": [
                    {
                        "model_name": "demo",
                        "litellm_params": {
                            "model": "gpt-4o-mini",
                            "api_key": "os.environ/OPENAI_API_KEY",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    errors = validate_config(path)
    assert any("provider prefix" in e for e in errors)


def test_rejects_nonempty_fallbacks(tmp_path: Path) -> None:
    path = tmp_path / "fb.yaml"
    path.write_text(
        yaml.dump(
            {
                "model_list": [
                    {
                        "model_name": "llm-general",
                        "litellm_params": {
                            "model": "openai/gpt-4o-mini",
                            "api_key": "os.environ/OPENAI_API_KEY",
                        },
                    }
                ],
                "router_settings": {
                    "fallbacks": [{"llm-general": ["openai-general"]}],
                },
            }
        ),
        encoding="utf-8",
    )
    errors = validate_config(path)
    assert any("fallbacks" in e for e in errors)


def _minimal_stable_aliases() -> dict:
    return {
        "aliases": {
            "llm-general": {
                "litellm_model": "openai/gpt-4o-mini",
                "api_key_env": "OPENAI_API_KEY",
            },
            "openai-general": {
                "litellm_model": "openai/gpt-4o-mini",
                "api_key_env": "OPENAI_API_KEY",
            },
            "anthropic-general": {
                "litellm_model": "anthropic/claude-haiku-4-5-20251001",
                "api_key_env": "ANTHROPIC_API_KEY",
            },
            "gemini-general": {
                "litellm_model": "gemini/gemini-2.0-flash",
                "api_key_env": "GEMINI_API_KEY",
            },
            "grok-general": {
                "litellm_model": "xai/grok-3-mini",
                "api_key_env": "XAI_API_KEY",
            },
        }
    }


def _model_list_from_aliases(aliases: dict) -> list[dict]:
    return [
        {
            "model_name": name,
            "litellm_params": {
                "model": entry["litellm_model"],
                "api_key": f"os.environ/{entry['api_key_env']}",
            },
        }
        for name, entry in aliases["aliases"].items()
    ]


def test_alias_contract_sync_ok(tmp_path: Path) -> None:
    aliases = _minimal_stable_aliases()
    aliases_path = tmp_path / "model-aliases.yaml"
    aliases_path.write_text(yaml.dump(aliases), encoding="utf-8")
    config_path = tmp_path / "litellm-config.yaml"
    config_path.write_text(
        yaml.dump({"model_list": _model_list_from_aliases(aliases)}),
        encoding="utf-8",
    )
    assert validate_config(config_path, aliases_path=aliases_path) == []


def test_alias_contract_missing_alias(tmp_path: Path) -> None:
    aliases = _minimal_stable_aliases()
    aliases_path = tmp_path / "model-aliases.yaml"
    aliases_path.write_text(yaml.dump(aliases), encoding="utf-8")
    config_path = tmp_path / "litellm-config.yaml"
    # Drop grok-general from runtime config
    models = [
        m
        for m in _model_list_from_aliases(aliases)
        if m["model_name"] != "grok-general"
    ]
    config_path.write_text(yaml.dump({"model_list": models}), encoding="utf-8")
    errors = validate_config(config_path, aliases_path=aliases_path)
    assert any("grok-general" in e and "missing" in e for e in errors)


def test_alias_contract_route_mismatch(tmp_path: Path) -> None:
    aliases = _minimal_stable_aliases()
    aliases_path = tmp_path / "model-aliases.yaml"
    aliases_path.write_text(yaml.dump(aliases), encoding="utf-8")
    models = _model_list_from_aliases(aliases)
    for m in models:
        if m["model_name"] == "llm-general":
            m["litellm_params"]["model"] = "openai/gpt-4o"
    config_path = tmp_path / "litellm-config.yaml"
    config_path.write_text(yaml.dump({"model_list": models}), encoding="utf-8")
    errors = validate_config(config_path, aliases_path=aliases_path)
    assert any("route mismatch" in e and "llm-general" in e for e in errors)


def test_validate_model_aliases_requires_stable_set(tmp_path: Path) -> None:
    path = tmp_path / "aliases.yaml"
    path.write_text(
        yaml.dump(
            {
                "aliases": {
                    "llm-general": {
                        "litellm_model": "openai/gpt-4o-mini",
                        "api_key_env": "OPENAI_API_KEY",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    errors = validate_model_aliases(path)
    assert any("missing required stable aliases" in e for e in errors)
