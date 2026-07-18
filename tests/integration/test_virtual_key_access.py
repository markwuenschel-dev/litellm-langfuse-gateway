"""Live virtual-key create/use/revoke probes.

Skipped unless LLG_LIVE=1. Requires a running stack with Postgres and
LITELLM_MASTER_KEY set (same value the proxy was started with).
"""

from __future__ import annotations

import os

import httpx
import pytest

from llg.keys import KeyClient, KeyClientError, default_base_url, require_master_key

pytestmark = pytest.mark.skipif(
    os.environ.get("LLG_LIVE") != "1",
    reason="Live stack required (set LLG_LIVE=1)",
)

BASE_URL = default_base_url()


def _client() -> KeyClient:
    return KeyClient(
        base_url=BASE_URL,
        master_key=require_master_key(),
        timeout=30.0,
    )


def test_create_list_revoke_roundtrip() -> None:
    client = _client()
    created = client.create(
        models=["openai-general"],
        max_budget=1.0,
        rpm=10,
        key_alias="llg-live-test-key",
        metadata={"service": "llg-integration", "environment": "dev"},
    )
    token = created.get("key") or created.get("token")
    assert token, f"no key in response: {created}"
    assert str(token).startswith("sk-")

    # List may be unavailable on some builds — soft-check.
    try:
        listed = client.list_keys()
        assert listed is not None
    except KeyClientError as exc:
        if exc.status_code != 404:
            raise

    revoked = client.revoke(str(token), mode="delete")
    assert isinstance(revoked, dict)


def test_invalid_key_rejected() -> None:
    """Requests with a garbage virtual key must not succeed as authenticated."""
    url = f"{BASE_URL}/v1/models"
    response = httpx.get(
        url,
        headers={"Authorization": "Bearer sk-definitely-not-a-real-key"},
        timeout=15.0,
    )
    # Proxy should reject (401/403); never treat as success with full catalog.
    assert response.status_code in (401, 403), (
        f"expected auth failure, got {response.status_code}: {response.text[:300]}"
    )
