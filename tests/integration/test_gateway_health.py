"""Live gateway health probes.

Skipped unless LLG_LIVE=1 so default CI / local unit runs stay offline.
Requires a running stack: `uv run llg up` (or docker compose).
"""

from __future__ import annotations

import os

import pytest

from llg.healthcheck import check_health

pytestmark = pytest.mark.skipif(
    os.environ.get("LLG_LIVE") != "1",
    reason="Live stack required (set LLG_LIVE=1)",
)

BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000").removesuffix("/v1")


def test_liveliness() -> None:
    code, message = check_health(BASE_URL, path="/health/liveliness", timeout=15.0)
    assert code == 0, message


def test_readiness_requires_postgres() -> None:
    """Readiness should succeed only when Postgres-backed proxy is up."""
    code, message = check_health(BASE_URL, path="/health/readiness", timeout=15.0)
    assert code == 0, message


def test_health_root() -> None:
    code, message = check_health(BASE_URL, path="/health", timeout=15.0)
    assert code == 0, message
