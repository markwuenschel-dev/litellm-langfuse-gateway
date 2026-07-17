"""Unit tests for GatewayClient (httpx mocked; no live stack)."""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
import pytest

from llm_client import (
    BudgetExceeded,
    GatewayAuthError,
    GatewayClient,
    GatewayConfig,
    GatewayConfigError,
    GatewayRateLimited,
    GatewayTimeout,
    GatewayUnavailable,
    ModelAccessDenied,
    ProviderUnavailable,
    RequestMetadata,
)
from llm_client.client import disallow_master_key, is_likely_master_key
from llm_client.errors import map_http_error


def _meta(**kwargs: Any) -> RequestMetadata:
    base = dict(
        request_id=str(uuid.uuid4()),
        service="test-svc",
        feature="unit",
        environment="development",
        release="test",
        model_alias="llm-general",
    )
    base.update(kwargs)
    return RequestMetadata(**base)


def _transport(handler: Any) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def test_disallow_master_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLG_DISALLOW_MASTER", raising=False)
    assert disallow_master_key() is True
    monkeypatch.setenv("LLG_DISALLOW_MASTER", "0")
    assert disallow_master_key() is False
    monkeypatch.setenv("LLG_DISALLOW_MASTER", "false")
    assert disallow_master_key() is False
    monkeypatch.setenv("LLG_DISALLOW_MASTER", "1")
    assert disallow_master_key() is True


def test_from_env_requires_virtual_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LITELLM_VIRTUAL_KEY", raising=False)
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-master-admin")
    with pytest.raises(GatewayConfigError, match="LITELLM_VIRTUAL_KEY"):
        GatewayConfig.from_env()


def test_from_env_rejects_master_key_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-master-admin")
    monkeypatch.setenv("LITELLM_VIRTUAL_KEY", "sk-master-admin")
    monkeypatch.delenv("LLG_DISALLOW_MASTER", raising=False)
    with pytest.raises(GatewayConfigError, match="MASTER_KEY"):
        GatewayConfig.from_env()


def test_from_env_allows_master_when_disallow_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-master-admin")
    monkeypatch.setenv("LITELLM_VIRTUAL_KEY", "sk-master-admin")
    monkeypatch.setenv("LLG_DISALLOW_MASTER", "0")
    cfg = GatewayConfig.from_env()
    assert cfg.virtual_key == "sk-master-admin"
    assert cfg.disallow_master is False


def test_from_env_rejects_provider_key_as_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-provider")
    monkeypatch.setenv("LITELLM_VIRTUAL_KEY", "sk-openai-provider")
    with pytest.raises(GatewayConfigError, match="OPENAI_API_KEY"):
        GatewayConfig.from_env()


def test_from_env_normalizes_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_VIRTUAL_KEY", "sk-virt")
    monkeypatch.setenv("LITELLM_BASE_URL", "http://localhost:4000")
    cfg = GatewayConfig.from_env()
    assert cfg.base_url.endswith("/v1")


def test_chat_success_with_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "choices": [{"message": {"role": "assistant", "content": "pong"}}],
            },
        )

    cfg = GatewayConfig(
        base_url="http://proxy.test/v1",
        virtual_key="sk-virtual",
        disallow_master=True,
    )
    client = GatewayClient(cfg, transport=_transport(handler))
    meta = _meta(trace_id="trace-xyz")
    result = client.chat(
        model="llm-general",
        messages=[{"role": "user", "content": "ping"}],
        metadata=meta,
    )
    client.close()

    assert result["choices"][0]["message"]["content"] == "pong"
    assert captured["auth"] == "Bearer sk-virtual"
    assert captured["url"].endswith("/chat/completions")
    assert captured["body"]["model"] == "llm-general"
    assert captured["body"]["metadata"]["service"] == "test-svc"
    assert captured["body"]["metadata"]["trace_id"] == "trace-xyz"
    assert captured["body"]["metadata"]["model_alias"] == "llm-general"


def test_chat_auth_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"error": {"message": "Authentication Error, Invalid proxy server token"}},
        )

    cfg = GatewayConfig(base_url="http://proxy.test/v1", virtual_key="sk-bad")
    client = GatewayClient(cfg, transport=_transport(handler))
    with pytest.raises(GatewayAuthError) as exc_info:
        client.chat(model="llm-general", messages=[{"role": "user", "content": "x"}])
    client.close()
    assert exc_info.value.status_code == 401


def test_chat_budget_exceeded() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error": {"message": "Budget has been exceeded: max budget 1.0"}},
        )

    cfg = GatewayConfig(base_url="http://proxy.test/v1", virtual_key="sk-v")
    client = GatewayClient(cfg, transport=_transport(handler))
    with pytest.raises(BudgetExceeded):
        client.chat(model="llm-general", messages=[{"role": "user", "content": "x"}])
    client.close()


def test_chat_model_access_denied() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"error": {"message": "key not allowed to access model llm-general"}},
        )

    cfg = GatewayConfig(base_url="http://proxy.test/v1", virtual_key="sk-v")
    client = GatewayClient(cfg, transport=_transport(handler))
    with pytest.raises(ModelAccessDenied):
        client.chat(model="llm-general", messages=[{"role": "user", "content": "x"}])
    client.close()


def test_chat_rate_limited() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={"error": {"message": "Crossed rpm limit for key"}},
        )

    cfg = GatewayConfig(base_url="http://proxy.test/v1", virtual_key="sk-v")
    client = GatewayClient(cfg, transport=_transport(handler))
    with pytest.raises(GatewayRateLimited):
        client.chat(model="llm-general", messages=[{"role": "user", "content": "x"}])
    client.close()


def test_chat_provider_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            502,
            json={"error": {"message": "OpenAIException: upstream provider error"}},
        )

    cfg = GatewayConfig(base_url="http://proxy.test/v1", virtual_key="sk-v")
    client = GatewayClient(cfg, transport=_transport(handler))
    with pytest.raises(ProviderUnavailable):
        client.chat(model="llm-general", messages=[{"role": "user", "content": "x"}])
    client.close()


def test_chat_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    cfg = GatewayConfig(base_url="http://proxy.test/v1", virtual_key="sk-v", timeout=0.01)
    client = GatewayClient(cfg, transport=_transport(handler))
    with pytest.raises(GatewayTimeout):
        client.chat(model="llm-general", messages=[{"role": "user", "content": "x"}])
    client.close()


def test_chat_connect_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    cfg = GatewayConfig(base_url="http://proxy.test/v1", virtual_key="sk-v")
    client = GatewayClient(cfg, transport=_transport(handler))
    with pytest.raises(GatewayUnavailable):
        client.chat(model="llm-general", messages=[{"role": "user", "content": "x"}])
    client.close()


def test_map_http_error_table() -> None:
    assert isinstance(map_http_error(401, "invalid key"), GatewayAuthError)
    assert isinstance(map_http_error(403, "not allowed to access model foo"), ModelAccessDenied)
    assert isinstance(map_http_error(429, "rpm limit"), GatewayRateLimited)
    assert isinstance(map_http_error(503, "service unavailable"), GatewayUnavailable)


def test_is_likely_master_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-m")
    assert is_likely_master_key("sk-m") is True
    assert is_likely_master_key("sk-other") is False
