"""Repository and compose path helpers."""

from __future__ import annotations

from pathlib import Path

# src/llg/paths.py → parents: llg, src, repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
GATEWAY_DIR = REPO_ROOT / "infra" / "llm-gateway"
DEFAULT_CONFIG = GATEWAY_DIR / "litellm-config.yaml"
DEFAULT_ALIASES = REPO_ROOT / "config" / "llm" / "model-aliases.yaml"
COMPOSE_FILE = GATEWAY_DIR / "compose.yaml"
COMPOSE_REDIS_FILE = GATEWAY_DIR / "compose.redis.yaml"
