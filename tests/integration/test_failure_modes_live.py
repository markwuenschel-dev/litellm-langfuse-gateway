"""Live-gated failure / chaos tests (WP14 / INT-005 / INT-108 / INT-110).

Skipped unless ``LLG_LIVE=1``. Budget and ACL paths are automated when master
key + stack are available.

Postgres-down and Langfuse-down are **env-gated chaos** (not permanent skips):

- ``LLG_CHAOS_POSTGRES=1`` — operator must already have stopped Postgres; test
  asserts readiness fails.
- ``LLG_CHAOS_LANGFUSE=1`` — operator must already have blocked Langfuse; test
  asserts chat still succeeds with a virtual key.

Do not claim DoD #13/#14 from hermetic runs alone. Do not enable ``LLG_CHAOS_*``
in default CI or the live-smoke workflow.
"""

from __future__ import annotations

import contextlib
import os
import uuid

import httpx
import pytest

from llg.healthcheck import check_health
from llg.keys import KeyClient, KeyClientError, default_base_url, require_master_key
from llm_client.proxy_url import openai_base, proxy_root

pytestmark = pytest.mark.skipif(
    os.environ.get("LLG_LIVE") != "1",
    reason="Live stack required (set LLG_LIVE=1)",
)

BASE_URL = proxy_root()

# Body tokens that indicate a budget/limit style rejection (LiteLLM wording varies).
# Bare 401/403/429 without these is NOT a budget pass (INT-110).
_BUDGET_BODY_TOKENS = (
    "budget",
    "spend",
    "limit",
    "exceed",
    "max_budget",
    "insufficient",
)


def _key_client() -> KeyClient:
    return KeyClient(
        base_url=default_base_url(),
        master_key=require_master_key(),
        timeout=30.0,
    )


def _chat(virtual_key: str, model: str, *, timeout: float = 45.0) -> httpx.Response:
    return httpx.post(
        f"{openai_base()}/chat/completions",
        headers={
            "Authorization": f"Bearer {virtual_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 16,
        },
        timeout=timeout,
    )


def test_readiness_ok_when_stack_healthy() -> None:
    """Baseline: readiness succeeds when Postgres-backed proxy is up."""
    code, message = check_health(BASE_URL, path="/health/readiness", timeout=15.0)
    assert code == 0, message


def test_live_budget_exceeded() -> None:
    """Key with max_budget=0 must not successfully complete a billable chat.

    Provisions a temporary virtual key via master, exercises chat once, expects
    a non-2xx response whose body carries a budget/limit signal.

    Bare 401/403/429 without budget-related body tokens is inconclusive / wrong
    failure mode and must not green (INT-110).
    """
    client = _key_client()
    alias = f"llg-budget-{uuid.uuid4().hex[:8]}"
    try:
        created = client.create(
            models=["llm-general"],
            max_budget=0.0,
            key_alias=alias,
            metadata={"service": "llg-live", "environment": "dev"},
        )
    except KeyClientError as exc:
        pytest.fail(f"key create failed (need master + stack): {exc}")

    token = created.get("key") or created.get("token")
    assert token and str(token).startswith("sk-"), created

    try:
        response = _chat(str(token), "llm-general")
    finally:
        with contextlib.suppress(KeyClientError):
            client.revoke(str(token), mode="delete")

    # Success would mean budget not enforced — fail hard.
    assert response.status_code >= 400, (
        f"expected budget rejection, got {response.status_code}: {response.text[:300]}"
    )
    body = response.text.lower()
    has_budget_signal = any(t in body for t in _BUDGET_BODY_TOKENS)
    if not has_budget_signal:
        # Auth/rate-limit without budget wording is not proof of budget enforcement.
        if response.status_code in (401, 403, 429):
            pytest.fail(
                "inconclusive budget check: status "
                f"{response.status_code} without budget-related body tokens "
                f"(not a pass): {response.text[:300]}"
            )
        pytest.fail(
            f"budget error body not recognized: {response.status_code} {response.text[:300]}"
        )


def test_live_model_acl_denied() -> None:
    """Key allowed only for openai-general must be denied for anthropic-general."""
    client = _key_client()
    alias = f"llg-acl-{uuid.uuid4().hex[:8]}"
    try:
        created = client.create(
            models=["openai-general"],
            max_budget=1.0,
            key_alias=alias,
            metadata={"service": "llg-live", "environment": "dev"},
        )
    except KeyClientError as exc:
        pytest.fail(f"key create failed (need master + stack): {exc}")

    token = created.get("key") or created.get("token")
    assert token and str(token).startswith("sk-"), created

    try:
        response = _chat(str(token), "anthropic-general")
    finally:
        with contextlib.suppress(KeyClientError):
            client.revoke(str(token), mode="delete")

    assert response.status_code in (401, 403, 404) or response.status_code >= 400, (
        f"expected ACL denial, got {response.status_code}: {response.text[:300]}"
    )
    # Must not be a successful completion body.
    assert response.status_code != 200
    body = response.text.lower()
    if response.status_code not in (401, 403):
        # Some pins use 400 with model-not-allowed wording
        assert any(
            t in body
            for t in ("model", "not allowed", "access", "permission", "unauthorized", "acl")
        ), f"unexpected ACL body: {response.text[:300]}"


def test_postgres_down_readiness_fails() -> None:
    """Operator chaos: Postgres already down; GET /health/readiness must fail.

    Enable only after inducing the outage::

        # stop postgres container, then:
        LLG_LIVE=1 LLG_CHAOS_POSTGRES=1 uv run pytest \\
          tests/integration/test_failure_modes_live.py::test_postgres_down_readiness_fails -q

    Evidence: docs/evidence/templates/failure-run.md
    """
    if os.environ.get("LLG_CHAOS_POSTGRES") != "1":
        pytest.skip(
            "Chaos not enabled: set LLG_CHAOS_POSTGRES=1 after stopping Postgres "
            "(DoD #14). Default skip is intentional; not a permanent un-escapable skip."
        )

    code, message = check_health(BASE_URL, path="/health/readiness", timeout=15.0)
    assert code != 0, (
        "expected readiness to fail with Postgres down, but it succeeded: "
        f"{message}. Confirm Postgres is stopped before LLG_CHAOS_POSTGRES=1."
    )


def test_langfuse_unreachable_llm_path_continues() -> None:
    """Operator chaos: Langfuse already unreachable; primary chat still 200.

    Enable only after blocking Langfuse (bad keys, network drop, etc.)::

        LLG_LIVE=1 LLG_CHAOS_LANGFUSE=1 LITELLM_VIRTUAL_KEY=sk-... uv run pytest \\
          tests/integration/test_failure_modes_live.py::test_langfuse_unreachable_llm_path_continues -q

    Evidence: docs/evidence/templates/failure-run.md
    """
    if os.environ.get("LLG_CHAOS_LANGFUSE") != "1":
        pytest.skip(
            "Chaos not enabled: set LLG_CHAOS_LANGFUSE=1 after blocking Langfuse "
            "(DoD #13). Default skip is intentional; not a permanent un-escapable skip."
        )

    virtual_key = (os.environ.get("LITELLM_VIRTUAL_KEY") or "").strip()
    if not virtual_key:
        pytest.fail(
            "LLG_CHAOS_LANGFUSE=1 requires LITELLM_VIRTUAL_KEY to assert chat still succeeds"
        )

    model = os.environ.get("LITELLM_MODEL", "llm-general")
    response = _chat(virtual_key, model)
    assert response.status_code == 200, (
        "expected LLM path to continue while Langfuse is unreachable; "
        f"got {response.status_code}: {response.text[:300]}"
    )
