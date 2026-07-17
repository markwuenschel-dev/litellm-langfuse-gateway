"""Live-gated failure / chaos stubs (WP14).

Skipped unless LLG_LIVE=1. These tests document the expected live suite; several
require intentional outages and may remain xfail/skip until chaos harness exists.

Do not claim DoD #13/#14 from hermetic runs alone.
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


def test_readiness_ok_when_stack_healthy() -> None:
    """Baseline: readiness succeeds when Postgres-backed proxy is up.

    Postgres-down chaos is manual: stop postgres, expect non-zero readiness.
    Document under docs/evidence/templates/failure-run.md — not automated here
    without a chaos orchestrator.
    """
    code, message = check_health(BASE_URL, path="/health/readiness", timeout=15.0)
    assert code == 0, message


@pytest.mark.skip(reason="Manual chaos: stop Postgres, expect readiness fail — UNPROVEN automated")
def test_postgres_down_readiness_fails() -> None:
    """Stub: operator stops postgres; GET /health/readiness must fail."""
    raise NotImplementedError("chaos harness not in-repo")


@pytest.mark.skip(reason="Manual chaos: block Langfuse; chat must still succeed — UNPROVEN automated")
def test_langfuse_unreachable_llm_path_continues() -> None:
    """Stub: Langfuse OTEL host unreachable; primary chat still 200."""
    raise NotImplementedError("chaos harness not in-repo")


@pytest.mark.skip(reason="Needs tiny-budget virtual key + spend — UNPROVEN without live key setup")
def test_live_budget_exceeded() -> None:
    """Stub: key with max_budget exhausted returns budget error."""
    raise NotImplementedError("provision key via llg keys create --max-budget")


@pytest.mark.skip(reason="Needs ACL-restricted virtual key — UNPROVEN without live key setup")
def test_live_model_acl_denied() -> None:
    """Stub: key without model access is denied."""
    raise NotImplementedError("provision key via llg keys create --models …")
