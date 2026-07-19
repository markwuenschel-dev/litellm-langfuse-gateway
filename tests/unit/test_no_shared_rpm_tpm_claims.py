"""INT-101: forbid advertising shared rpm/tpm outside allowlisted historical paths.

ADR 0004: Redis overlay is service-only on the current pin. Product/ops docs must
not claim shared virtual-key rpm/tpm when Redis is present or replicas > 1.
"""

from __future__ import annotations

import re
from pathlib import Path

from llg.paths import REPO_ROOT

# Case-insensitive product-claim phrases (ADR 0004 non-advertising rule).
FORBIDDEN = re.compile(r"shared\s+rpm|shared\s+tpm", re.IGNORECASE)

# Tight allowlist: ADR policy text, historical evidence, spike harnesses,
# archived plans, and frozen SDD review packages (not live ops SoT).
_ALLOWLIST_PREFIXES: tuple[str, ...] = (
    "docs/adr/",
    "docs/evidence/",
    "docs/superpowers/",
    ".superpowers/",
    "tests/runtime_pin/",
    "tests/unit/test_no_shared_rpm_tpm_claims.py",
)

_SCAN_SUFFIXES = {".md", ".yaml", ".yml", ".py", ".toml", ".txt", ".json"}


def _is_allowlisted(rel: str) -> bool:
    norm = rel.replace("\\", "/")
    return any(norm == p or norm.startswith(p) for p in _ALLOWLIST_PREFIXES)


def _iter_scan_files() -> list[Path]:
    skip_dirs = {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".tox",
    }
    files: list[Path] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _SCAN_SUFFIXES:
            continue
        rel_parts = path.relative_to(REPO_ROOT).parts
        if any(part in skip_dirs for part in rel_parts):
            continue
        files.append(path)
    return files


def test_no_shared_rpm_tpm_product_claims() -> None:
    """Fail if non-allowlisted docs/ops advertise shared rpm/tpm (ADR 0004)."""
    offenders: list[str] = []
    for path in _iter_scan_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        if _is_allowlisted(rel):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if FORBIDDEN.search(line):
                offenders.append(f"{rel}:{i}: {line.strip()}")
    assert offenders == [], (
        "ADR 0004: do not advertise shared rpm/tpm outside ADR/evidence/spike/plan "
        "allowlist:\n" + "\n".join(offenders)
    )
