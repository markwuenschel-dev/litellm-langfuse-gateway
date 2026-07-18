"""Thin re-export — prefer `uv run llg secrets generate`.

Kept for backward compatibility with `python scripts/generate_secrets.py`
and existing console scripts.
"""

from __future__ import annotations

from llg.generate_secrets import generate_key, generate_password, main  # noqa: F401

__all__ = ["generate_key", "generate_password", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
