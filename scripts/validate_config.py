"""Validate LiteLLM YAML config structure used by this repository."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "infra" / "llm-gateway" / "litellm-config.yaml"


def _require_list(data: dict[str, Any], key: str) -> list[Any]:
    value = data.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"'{key}' must be a non-empty list")
    return value


def validate_config(path: Path) -> list[str]:
    """Return a list of human-readable validation errors (empty if OK)."""
    errors: list[str] = []

    if not path.is_file():
        return [f"Config file not found: {path}"]

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return [f"YAML parse error: {exc}"]

    if not isinstance(raw, dict):
        return ["Root document must be a mapping"]

    try:
        model_list = _require_list(raw, "model_list")
    except ValueError as exc:
        errors.append(str(exc))
        model_list = []

    names: set[str] = set()
    for index, entry in enumerate(model_list):
        prefix = f"model_list[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix}: must be a mapping")
            continue

        model_name = entry.get("model_name")
        if not isinstance(model_name, str) or not model_name.strip():
            errors.append(f"{prefix}: model_name is required")
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

        api_key = params.get("api_key")
        if isinstance(api_key, str) and api_key and not api_key.startswith("os.environ/"):
            errors.append(
                f"{prefix}: api_key must reference os.environ/... (got literal secret shape)"
            )

    settings = raw.get("litellm_settings")
    if settings is not None and not isinstance(settings, dict):
        errors.append("litellm_settings must be a mapping when present")

    general = raw.get("general_settings")
    if general is not None and not isinstance(general, dict):
        errors.append("general_settings must be a mapping when present")

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
    args = parser.parse_args(argv)

    errors = validate_config(args.path)
    if errors:
        print(f"INVALID: {args.path}", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"OK: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
