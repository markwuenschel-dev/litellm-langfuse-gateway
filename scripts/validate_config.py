"""Thin re-export — prefer `uv run llg config validate`.

Kept for backward compatibility with `python -m scripts.validate_config`
and existing console scripts.
"""

from __future__ import annotations

from llg.validate_config import (  # noqa: F401
    DEFAULT_CONFIG,
    REPO_ROOT,
    main,
    validate_config,
)

__all__ = ["DEFAULT_CONFIG", "REPO_ROOT", "main", "validate_config"]

if __name__ == "__main__":
    raise SystemExit(main())
