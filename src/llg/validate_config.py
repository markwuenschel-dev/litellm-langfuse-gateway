"""Validate LiteLLM YAML config structure used by this repository."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from llg.paths import DEFAULT_ALIASES, DEFAULT_CONFIG, REPO_ROOT

__all__ = [
    "DEFAULT_ALIASES",
    "DEFAULT_CONFIG",
    "REPO_ROOT",
    "STABLE_ALIASES",
    "load_registry_names",
    "load_stable_aliases",
    "main",
    "validate_config",
    "validate_model_aliases",
]


def _require_list(data: dict[str, Any], key: str) -> list[Any]:
    value = data.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"'{key}' must be a non-empty list")
    return value


def _load_yaml_mapping(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    """Load YAML file as a mapping; return (data, errors)."""
    if not path.is_file():
        return None, [f"Config file not found: {path}"]
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return None, [f"YAML parse error: {exc}"]
    if not isinstance(raw, dict):
        return None, ["Root document must be a mapping"]
    return raw, []


def _registry_role(entry: dict[str, Any]) -> str:
    """Return registry_role for an alias entry (default ``app``)."""
    role = entry.get("registry_role", "app")
    if role is None or role == "":
        return "app"
    return str(role)


def load_registry_names(path: Path = DEFAULT_ALIASES) -> frozenset[str]:
    """All semantic registry names (app + internal) under ``aliases:``.

    INT-117: equality uses this full set vs ``model_list`` model_name values.
    """
    raw, errors = _load_yaml_mapping(path)
    if errors or raw is None:
        return frozenset()
    aliases = raw.get("aliases")
    if not isinstance(aliases, dict) or not aliases:
        return frozenset()
    return frozenset(str(name) for name in aliases if isinstance(name, str) and name.strip())


def load_stable_aliases(path: Path = DEFAULT_ALIASES) -> frozenset[str]:
    """App-facing stable aliases = ``aliases:`` keys with registry_role app (default).

    INT-002 / INT-117: semantic write SoT is model-aliases.yaml.
    Internal registry entries (registry_role: internal) are excluded from the
    app key / virtual-key allowlist but still participate in model_list equality.
    """
    raw, errors = _load_yaml_mapping(path)
    if errors or raw is None:
        return frozenset()
    aliases = raw.get("aliases")
    if not isinstance(aliases, dict) or not aliases:
        return frozenset()
    names: set[str] = set()
    for name, entry in aliases.items():
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(entry, dict):
            continue
        if _registry_role(entry) != "app":
            continue
        names.add(name)
    return frozenset(names)


# Derived at import for callers that still import STABLE_ALIASES (scripts, tests).
# Always re-read via load_stable_aliases() when validating a non-default path.
STABLE_ALIASES: frozenset[str] = load_stable_aliases()


def validate_model_aliases(path: Path) -> list[str]:
    """Validate config/llm/model-aliases.yaml structure.

    The file itself is the stable alias set (no separate hardcoded list).
    """
    raw, errors = _load_yaml_mapping(path)
    if errors:
        return errors
    assert raw is not None

    aliases = raw.get("aliases")
    if not isinstance(aliases, dict) or not aliases:
        return ["'aliases' must be a non-empty mapping"]

    names: set[str] = set()
    for name, entry in aliases.items():
        if not isinstance(name, str) or not name.strip():
            errors.append("alias name must be a non-empty string")
            continue
        if name in names:
            errors.append(f"duplicate alias '{name}'")
        else:
            names.add(name)

        prefix = f"aliases.{name}"
        if not isinstance(entry, dict):
            errors.append(f"{prefix}: must be a mapping")
            continue

        litellm_model = entry.get("litellm_model")
        if not isinstance(litellm_model, str) or not litellm_model.strip():
            errors.append(f"{prefix}: litellm_model is required")
        elif "/" not in litellm_model:
            errors.append(
                f"{prefix}: litellm_model must include a provider prefix "
                f"(e.g. openai/...) (got {litellm_model!r})"
            )

        api_key_env = entry.get("api_key_env")
        if not isinstance(api_key_env, str) or not api_key_env.strip():
            errors.append(f"{prefix}: api_key_env is required")
        elif api_key_env.startswith("os.environ/") or "/" in api_key_env:
            errors.append(
                f"{prefix}: api_key_env must be a bare env var name (got {api_key_env!r})"
            )
        elif api_key_env.lower().startswith("sk-") or " " in api_key_env:
            errors.append(f"{prefix}: api_key_env looks like a literal secret")

        consumers = entry.get("consumers")
        if consumers is not None and (
            not isinstance(consumers, list) or not all(isinstance(c, str) for c in consumers)
        ):
            errors.append(f"{prefix}: consumers must be a list of strings when present")

        # INT-117: registry_role app|internal; internal needs exemption_rationale.
        role = _registry_role(entry)
        if role not in ("app", "internal"):
            errors.append(f"{prefix}: registry_role must be 'app' or 'internal' (got {role!r})")
        elif role == "internal":
            rationale = entry.get("exemption_rationale")
            if not isinstance(rationale, str) or not rationale.strip():
                errors.append(
                    f"{prefix}: exemption_rationale is required when registry_role is 'internal'"
                )

    if "llm-general" not in names:
        errors.append("missing required default alias 'llm-general'")

    return errors


def validate_config(
    path: Path,
    *,
    aliases_path: Path | None = None,
) -> list[str]:
    """Return a list of human-readable validation errors (empty if OK).

    Always enforces: non-empty model_list, unique model_name, litellm_params.model
    with provider prefix, and api_key only as os.environ/... (no literal keys).

    When ``aliases_path`` is provided, or when ``path`` is the repo default
    config and ``DEFAULT_ALIASES`` exists, enforces **set equality** between
    semantic registry names and ``model_list`` model_name values (INT-117):
    every registry alias is in model_list (with matching route/env), and every
    model_list entry is declared in the registry (no undeclared runtime-only routes).
    """
    errors: list[str] = []

    raw, load_errors = _load_yaml_mapping(path)
    if load_errors:
        return load_errors
    assert raw is not None

    try:
        model_list = _require_list(raw, "model_list")
    except ValueError as exc:
        errors.append(str(exc))
        model_list = []

    names: set[str] = set()
    # model_name -> (litellm model route, api_key env ref)
    routes: dict[str, tuple[str, str | None]] = {}

    for index, entry in enumerate(model_list):
        prefix = f"model_list[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix}: must be a mapping")
            continue

        model_name = entry.get("model_name")
        if not isinstance(model_name, str) or not model_name.strip():
            errors.append(f"{prefix}: model_name is required")
            model_name = None
        elif model_name in names:
            errors.append(f"{prefix}: duplicate model_name '{model_name}'")
        else:
            names.add(model_name)

        params = entry.get("litellm_params")
        if not isinstance(params, dict):
            errors.append(f"{prefix}: litellm_params mapping is required")
            continue

        model = params.get("model")
        if not isinstance(model, str) or not model.strip():
            errors.append(f"{prefix}: litellm_params.model is required")
            model = None
        elif "/" not in model:
            errors.append(
                f"{prefix}: litellm_params.model must include a provider prefix "
                f"(e.g. openai/...) (got {model!r})"
            )

        api_key = params.get("api_key")
        if api_key is None or api_key == "":
            # Optional at schema level for some deployments; no error.
            pass
        elif not isinstance(api_key, str):
            errors.append(f"{prefix}: api_key must be a string when present")
        elif not api_key.startswith("os.environ/"):
            errors.append(
                f"{prefix}: api_key must reference os.environ/... (got literal secret shape)"
            )

        if model_name is not None and model is not None:
            routes[model_name] = (
                model,
                api_key if isinstance(api_key, str) else None,
            )

    settings = raw.get("litellm_settings")
    if settings is not None and not isinstance(settings, dict):
        errors.append("litellm_settings must be a mapping when present")

    general = raw.get("general_settings")
    if general is not None and not isinstance(general, dict):
        errors.append("general_settings must be a mapping when present")

    # Fallbacks must stay off by default: reject non-empty router_settings.fallbacks
    router = raw.get("router_settings")
    if router is not None:
        if not isinstance(router, dict):
            errors.append("router_settings must be a mapping when present")
        else:
            fallbacks = router.get("fallbacks")
            if fallbacks:
                errors.append(
                    "router_settings.fallbacks must be empty/absent (fallbacks off by default)"
                )

    # Alias contract sync (repo default config, or explicit aliases_path)
    resolved_aliases = aliases_path
    if (
        resolved_aliases is None
        and path.resolve() == DEFAULT_CONFIG.resolve()
        and DEFAULT_ALIASES.is_file()
    ):
        resolved_aliases = DEFAULT_ALIASES

    if resolved_aliases is not None:
        alias_errors = validate_model_aliases(resolved_aliases)
        if alias_errors:
            for err in alias_errors:
                errors.append(f"model-aliases ({resolved_aliases.name}): {err}")
        else:
            alias_raw, _ = _load_yaml_mapping(resolved_aliases)
            assert alias_raw is not None
            aliases = alias_raw["aliases"]
            assert isinstance(aliases, dict)
            registry_names = {str(n) for n in aliases if isinstance(n, str) and n.strip()}
            # Forward: registry ⊆ model_list (with route/env match)
            for alias_name, entry in aliases.items():
                if not isinstance(entry, dict):
                    continue
                if alias_name not in names:
                    errors.append(
                        f"model_list missing stable alias '{alias_name}' "
                        f"(required by {resolved_aliases.name})"
                    )
                    continue
                expected_model = entry.get("litellm_model")
                expected_env = entry.get("api_key_env")
                actual_model, actual_key = routes.get(alias_name, ("", None))
                if (
                    isinstance(expected_model, str)
                    and actual_model
                    and actual_model != expected_model
                ):
                    errors.append(
                        f"alias '{alias_name}': litellm route mismatch "
                        f"(config has {actual_model!r}, "
                        f"aliases file has {expected_model!r})"
                    )
                if isinstance(expected_env, str) and expected_env.strip():
                    expected_ref = f"os.environ/{expected_env}"
                    if actual_key != expected_ref:
                        errors.append(
                            f"alias '{alias_name}': api_key must be "
                            f"{expected_ref!r} (got {actual_key!r})"
                        )
            # Reverse (INT-117): model_list ⊆ registry — no undeclared runtime-only routes
            for model_name in sorted(names):
                if model_name not in registry_names:
                    errors.append(
                        f"model_list has undeclared runtime-only route "
                        f"'{model_name}' (not in {resolved_aliases.name}); "
                        f"declare it under aliases: with registry_role app|internal "
                        f"(internal requires exemption_rationale)"
                    )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate LiteLLM gateway config YAML.")
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Path to config (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--aliases",
        type=Path,
        default=None,
        help=f"Path to model-aliases.yaml (default: auto when validating {DEFAULT_CONFIG.name})",
    )
    args = parser.parse_args(argv)

    errors = validate_config(args.path, aliases_path=args.aliases)
    if errors:
        print(f"INVALID: {args.path}", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"OK: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
