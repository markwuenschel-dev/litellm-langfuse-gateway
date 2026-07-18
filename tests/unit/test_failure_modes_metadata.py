"""Hermetic failure-mode tests: metadata rejects + client error mapping (WP14).

No live stack. Live chaos rows are documented in docs/evidence/failure-matrix.md
and stubbed under tests/integration/test_failure_modes_live.py.
"""

from __future__ import annotations

import uuid

import httpx
import pytest

from llm_client import (
    BudgetExceeded,
    GatewayClient,
    GatewayConfig,
    GatewayUnavailable,
)
from llm_client.errors import map_http_error
from llm_client.metadata import validate_metadata


def _valid(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "request_id": str(uuid.uuid4()),
        "service": "failure-suite",
        "feature": "unit",
        "environment": "development",
        "release": "test",
        "model_alias": "llm-general",
    }
    base.update(overrides)
    return base


# --- Metadata: auth headers, forbidden keys, oversize ---


@pytest.mark.parametrize(
    "key",
    [
        "Authorization",
        "authorization",
        "api_key",
        "api-key",
        "x_api_key",
        "secret",
        "password",
        "cookie",
        "bearer",
        "master_key",
        "virtual_key",
        "litellm_master",
        "access_token",
    ],
)
def test_metadata_rejects_forbidden_auth_like_keys(key: str) -> None:
    hostile = dict(_valid())
    hostile[key] = "should-not-pass"
    with pytest.raises(Exception, match="forbidden|unknown") as exc_info:
        validate_metadata(hostile)
    # Prefer forbidden for secret-shaped key names; unknown if pattern misses
    msg = str(exc_info.value).lower()
    assert "forbidden" in msg or "unknown" in msg


def test_metadata_rejects_authorization_header_value_shape() -> None:
    with pytest.raises(Exception, match="secret|Authorization"):
        validate_metadata(_valid(session_id="Bearer sk-abcdefghijklmnop"))


def test_metadata_rejects_oversize_string_fields() -> None:
    with pytest.raises(Exception, match="max length"):
        validate_metadata(_valid(service="s" * 129))
    with pytest.raises(Exception, match="max length"):
        validate_metadata(_valid(feature="f" * 129))
    with pytest.raises(Exception, match="max length"):
        validate_metadata(_valid(user_id="u" * 129))
    with pytest.raises(Exception, match="max length"):
        validate_metadata(_valid(cost_center="c" * 129))


def test_metadata_rejects_sk_shaped_values() -> None:
    with pytest.raises(Exception, match="secret"):
        validate_metadata(_valid(tenant_id="sk-proj-abcdefghijklmnop"))


# --- Client: connection errors and budget mapping ---


def test_gateway_unavailable_on_connect_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    cfg = GatewayConfig(base_url="http://proxy.test/v1", virtual_key="sk-virtual")
    client = GatewayClient(cfg, transport=httpx.MockTransport(handler))
    with pytest.raises(GatewayUnavailable, match="unavailable"):
        client.chat(
            model="llm-general",
            messages=[{"role": "user", "content": "ping"}],
        )
    client.close()


def test_gateway_unavailable_on_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.NetworkError("network down")

    cfg = GatewayConfig(base_url="http://proxy.test/v1", virtual_key="sk-virtual")
    client = GatewayClient(cfg, transport=httpx.MockTransport(handler))
    with pytest.raises(GatewayUnavailable):
        client.chat(
            model="llm-general",
            messages=[{"role": "user", "content": "ping"}],
        )
    client.close()


def test_budget_exceeded_mapping_from_http_body() -> None:
    err = map_http_error(400, "Budget has been exceeded: max budget 1.0")
    assert isinstance(err, BudgetExceeded)

    err403 = map_http_error(403, "crossed budget limit for key")
    assert isinstance(err403, BudgetExceeded)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error": {"message": "exceeded max budget for this key"}},
        )

    cfg = GatewayConfig(base_url="http://proxy.test/v1", virtual_key="sk-v")
    client = GatewayClient(cfg, transport=httpx.MockTransport(handler))
    with pytest.raises(BudgetExceeded):
        client.chat(model="llm-general", messages=[{"role": "user", "content": "x"}])
    client.close()


def test_budget_exceeded_status_402() -> None:
    err = map_http_error(402, "payment required / budget")
    assert isinstance(err, BudgetExceeded)
