"""Tests for llg.validate_config (and scripts re-export)."""

from __future__ import annotations

from pathlib import Path

import yaml

from llg.paths import DEFAULT_ALIASES as PATHS_DEFAULT_ALIASES
from llg.paths import REPO_ROOT
from llg.validate_config import (
    DEFAULT_ALIASES,
    load_stable_aliases,
    validate_config,
    validate_model_aliases,
)
from scripts.validate_config import validate_config as scripts_validate_config


def test_default_aliases_is_paths_sot() -> None:
    """INT-113: validate_config re-exports paths.DEFAULT_ALIASES (single SoT)."""
    assert DEFAULT_ALIASES is PATHS_DEFAULT_ALIASES
    assert DEFAULT_ALIASES == REPO_ROOT / "config" / "llm" / "model-aliases.yaml"


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
    stable = load_stable_aliases()
    assert stable  # derived from model-aliases.yaml
    assert names >= stable


def test_ibkr_collab_haiku_alias_uses_gateway_anthropic_route() -> None:
    aliases = yaml.safe_load(DEFAULT_ALIASES.read_text(encoding="utf-8"))["aliases"]
    haiku = aliases["haiku-4.5"]
    assert haiku["litellm_model"] == "anthropic/claude-haiku-4-5-20251001"
    assert haiku["api_key_env"] == "ANTHROPIC_API_KEY"
    assert "ibkr-auto-trader-collab" in haiku["consumers"]

    config = yaml.safe_load(
        (REPO_ROOT / "infra" / "llm-gateway" / "litellm-config.yaml").read_text(encoding="utf-8")
    )
    routes = {item["model_name"]: item["litellm_params"] for item in config["model_list"]}
    assert routes["haiku-4.5"] == {
        "model": "anthropic/claude-haiku-4-5-20251001",
        "api_key": "os.environ/ANTHROPIC_API_KEY",
    }


def test_stable_aliases_derived_from_yaml_not_hardcoded() -> None:
    """INT-002: adding an alias in YAML expands the derived set."""
    stable = load_stable_aliases()
    assert "llm-general" in stable
    assert "grok-general" in stable
    # Source is the file keys — same length as aliases map
    raw = yaml.safe_load(DEFAULT_ALIASES.read_text(encoding="utf-8"))
    assert stable == frozenset(raw["aliases"].keys())


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
    models = [m for m in _model_list_from_aliases(aliases) if m["model_name"] != "grok-general"]
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


def test_alias_contract_undeclared_runtime_only_route(tmp_path: Path) -> None:
    """INT-117: model_list entry not in registry → equality failure."""
    aliases = _minimal_stable_aliases()
    aliases_path = tmp_path / "model-aliases.yaml"
    aliases_path.write_text(yaml.dump(aliases), encoding="utf-8")
    models = _model_list_from_aliases(aliases)
    models.append(
        {
            "model_name": "shadow-eval-only",
            "litellm_params": {
                "model": "openai/gpt-4o-mini",
                "api_key": "os.environ/OPENAI_API_KEY",
            },
        }
    )
    config_path = tmp_path / "litellm-config.yaml"
    config_path.write_text(yaml.dump({"model_list": models}), encoding="utf-8")
    errors = validate_config(config_path, aliases_path=aliases_path)
    assert any("undeclared runtime-only" in e and "shadow-eval-only" in e for e in errors)


def test_internal_registry_role_requires_rationale(tmp_path: Path) -> None:
    path = tmp_path / "aliases.yaml"
    path.write_text(
        yaml.dump(
            {
                "aliases": {
                    "llm-general": {
                        "litellm_model": "openai/gpt-4o-mini",
                        "api_key_env": "OPENAI_API_KEY",
                    },
                    "eval-shadow": {
                        "litellm_model": "openai/gpt-4o-mini",
                        "api_key_env": "OPENAI_API_KEY",
                        "registry_role": "internal",
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    errors = validate_model_aliases(path)
    assert any("exemption_rationale" in e and "eval-shadow" in e for e in errors)


def test_internal_role_in_equality_not_in_stable_aliases(tmp_path: Path) -> None:
    """Internal names participate in equality; excluded from app stable set."""
    from llg.validate_config import load_registry_names, load_stable_aliases

    aliases = {
        "aliases": {
            "llm-general": {
                "litellm_model": "openai/gpt-4o-mini",
                "api_key_env": "OPENAI_API_KEY",
            },
            "eval-shadow": {
                "litellm_model": "openai/gpt-4o-mini",
                "api_key_env": "OPENAI_API_KEY",
                "registry_role": "internal",
                "exemption_rationale": "offline eval harness only",
            },
        }
    }
    aliases_path = tmp_path / "model-aliases.yaml"
    aliases_path.write_text(yaml.dump(aliases), encoding="utf-8")
    config_path = tmp_path / "litellm-config.yaml"
    config_path.write_text(
        yaml.dump({"model_list": _model_list_from_aliases(aliases)}),
        encoding="utf-8",
    )
    assert validate_config(config_path, aliases_path=aliases_path) == []
    assert load_stable_aliases(aliases_path) == frozenset({"llm-general"})
    assert load_registry_names(aliases_path) == frozenset({"llm-general", "eval-shadow"})


def test_validate_model_aliases_requires_llm_general(tmp_path: Path) -> None:
    """INT-002: file is the set; only required fixed name is llm-general."""
    path = tmp_path / "aliases.yaml"
    path.write_text(
        yaml.dump(
            {
                "aliases": {
                    "openai-general": {
                        "litellm_model": "openai/gpt-4o-mini",
                        "api_key_env": "OPENAI_API_KEY",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    errors = validate_model_aliases(path)
    assert any("llm-general" in e for e in errors)


def test_validate_model_aliases_accepts_file_as_full_set(tmp_path: Path) -> None:
    path = tmp_path / "aliases.yaml"
    path.write_text(
        yaml.dump(
            {
                "aliases": {
                    "llm-general": {
                        "litellm_model": "openai/gpt-4o-mini",
                        "api_key_env": "OPENAI_API_KEY",
                        "consumers": ["examples"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    assert validate_model_aliases(path) == []
    assert load_stable_aliases(path) == frozenset({"llm-general"})
