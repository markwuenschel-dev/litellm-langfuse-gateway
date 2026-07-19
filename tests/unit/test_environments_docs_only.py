"""INT-006: environments/*.yaml are docs-only — not a second runtime SoT."""

from __future__ import annotations

import yaml

from llg.paths import REPO_ROOT

ENV_DIR = REPO_ROOT / "config" / "llm" / "environments"
SRC_DIR = REPO_ROOT / "src"


def test_environment_files_exist_and_parse() -> None:
    for name in ("development", "staging", "production"):
        path = ENV_DIR / f"{name}.yaml"
        assert path.is_file(), path
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(raw, dict)
        assert raw.get("environment") == name


def test_environment_headers_say_docs_only() -> None:
    for path in ENV_DIR.glob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        assert "docs-only" in text.lower() or "NOT loaded" in text, path


def test_src_does_not_load_environments_yaml() -> None:
    """Fail if application/ops code starts treating environments YAML as live config."""
    needle = "config/llm/environments"
    offenders: list[str] = []
    for path in SRC_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if needle in text or needle.replace("/", "\\") in text:
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == [], f"src must not load environments YAML: {offenders}"
