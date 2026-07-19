"""Normalize LiteLLM proxy base URLs (ops root vs OpenAI-compatible /v1)."""

from __future__ import annotations

import os

__all__ = [
    "DEFAULT_PROXY_ROOT",
    "DEFAULT_OPENAI_BASE",
    "proxy_root",
    "openai_base",
]

DEFAULT_PROXY_ROOT = "http://localhost:4000"
DEFAULT_OPENAI_BASE = "http://localhost:4000/v1"


def proxy_root(url: str | None = None) -> str:
    """Proxy origin for admin/health routes — no trailing slash, no ``/v1``.

    Accepts values with or without ``/v1`` (common dual dialect for LITELLM_BASE_URL).
    """
    raw = (
        url if url is not None else os.environ.get("LITELLM_BASE_URL", DEFAULT_PROXY_ROOT)
    ).strip()
    if not raw:
        raw = DEFAULT_PROXY_ROOT
    root = raw.rstrip("/")
    if root.endswith("/v1"):
        root = root[: -len("/v1")].rstrip("/")
    return root or DEFAULT_PROXY_ROOT


def openai_base(url: str | None = None) -> str:
    """OpenAI-compatible base for chat completions — ends with ``/v1``."""
    root = proxy_root(url)
    return f"{root}/v1"
