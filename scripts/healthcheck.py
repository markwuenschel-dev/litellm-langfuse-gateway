"""Thin re-export — prefer `uv run llg health`.

Kept for backward compatibility with `python scripts/healthcheck.py`
and existing console scripts.
"""

from __future__ import annotations

from llg.healthcheck import check_health, main  # noqa: F401

__all__ = ["check_health", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
