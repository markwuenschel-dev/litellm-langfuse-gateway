"""Unit tests for virtual key admin client and CLI (httpx mocked; no live stack)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from typer.testing import CliRunner

from llg.cli import app
from llg.keys import (
    KeyClient,
    KeyClientError,
    require_master_key,
    sanitize_proxy_error_body,
    validate_key_models,
)

runner = CliRunner()

MASTER = "sk-test-master-never-print"
BASE = "http://proxy.test:4000"


def _transport(handler: Any) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def test_require_master_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LITELLM_MASTER_KEY", raising=False)
    with pytest.raises(KeyClientError, match="LITELLM_MASTER_KEY"):
        require_master_key(None)


def test_require_master_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", MASTER)
    assert require_master_key(None) == MASTER


def test_validate_key_models_known_alias_ok() -> None:
    """INT-105: known stable alias passes without network."""
    validate_key_models(["llm-general"])
    validate_key_models(["openai-general", "anthropic-general"])
    validate_key_models(None)
    validate_key_models([])


def test_validate_key_models_unknown_rejected() -> None:
    """INT-105: unknown alias rejected before any HTTP call."""
    with pytest.raises(KeyClientError, match="unknown model alias") as exc_info:
        validate_key_models(["not-a-real-alias"])
    assert "not-a-real-alias" in str(exc_info.value)
    assert exc_info.value.status_code is None


def test_create_rejects_unknown_models_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INT-105: KeyClient.create never calls httpx for unknown aliases."""
    mock_request = MagicMock()
    monkeypatch.setattr(httpx, "request", mock_request)
    client = KeyClient(base_url=BASE, master_key=MASTER)
    with pytest.raises(KeyClientError, match="unknown model alias"):
        client.create(models=["totally-fake-model"])
    mock_request.assert_not_called()


def test_create_posts_generate_body(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["auth"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "key": "sk-virtual-once",
                "key_alias": "ref-app-dev",
                "models": ["openai-general"],
                "max_budget": 5.0,
                "rpm_limit": 30,
            },
        )

    monkeypatch.setattr(
        httpx,
        "request",
        lambda *a, **k: httpx.Client(transport=_transport(handler)).request(*a, **k),
    )

    client = KeyClient(base_url=BASE, master_key=MASTER)
    result = client.create(
        models=["openai-general"],
        max_budget=5.0,
        rpm=30,
        key_alias="ref-app-dev",
        team_id="team-dev",
    )

    assert result["key"] == "sk-virtual-once"
    assert captured["method"] == "POST"
    assert captured["url"] == f"{BASE}/key/generate"
    assert captured["auth"] == f"Bearer {MASTER}"
    assert captured["body"] == {
        "models": ["openai-general"],
        "max_budget": 5.0,
        "rpm_limit": 30,
        "key_alias": "ref-app-dev",
        "team_id": "team-dev",
    }
    # Master key must not appear in response payload
    assert MASTER not in json.dumps(result)


def test_create_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Unauthorized")

    monkeypatch.setattr(
        httpx,
        "request",
        lambda *a, **k: httpx.Client(transport=_transport(handler)).request(*a, **k),
    )
    client = KeyClient(base_url=BASE, master_key=MASTER)
    with pytest.raises(KeyClientError, match="401") as exc_info:
        client.create(models=["llm-general"])
    assert exc_info.value.status_code == 401


def test_sanitize_redacts_sk_secret() -> None:
    """INT-111: secret-shaped tokens never appear in sanitized body."""
    raw = "error: invalid key sk-secretvalue for user; Bearer tok-abc123"
    out = sanitize_proxy_error_body(raw)
    assert "sk-secretvalue" not in out
    assert "Bearer tok-abc123" not in out
    assert "[REDACTED]" in out


def test_key_client_error_body_does_not_leak_sk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INT-111: KeyClientError message must not contain sk-* from proxy body."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            text='{"error":"upstream failed with key sk-secretvalue"}',
        )

    monkeypatch.setattr(
        httpx,
        "request",
        lambda *a, **k: httpx.Client(transport=_transport(handler)).request(*a, **k),
    )
    client = KeyClient(base_url=BASE, master_key=MASTER)
    with pytest.raises(KeyClientError) as exc_info:
        client.create(models=["llm-general"])
    msg = str(exc_info.value)
    assert "sk-secretvalue" not in msg
    assert "500" in msg
    assert "/key/generate" in msg
    assert "[REDACTED]" in msg


def test_list_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url).startswith(f"{BASE}/key/list")
        return httpx.Response(
            200,
            json={"keys": [{"key_alias": "a", "spend": 0.0}], "page": 1},
        )

    monkeypatch.setattr(
        httpx,
        "request",
        lambda *a, **k: httpx.Client(transport=_transport(handler)).request(*a, **k),
    )
    client = KeyClient(base_url=BASE, master_key=MASTER)
    data = client.list_keys()
    assert isinstance(data, dict)
    assert data["keys"][0]["key_alias"] == "a"


def test_revoke_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"deleted_keys": ["sk-virtual-once"]})

    monkeypatch.setattr(
        httpx,
        "request",
        lambda *a, **k: httpx.Client(transport=_transport(handler)).request(*a, **k),
    )
    client = KeyClient(base_url=BASE, master_key=MASTER)
    result = client.revoke("sk-virtual-once", mode="delete")
    assert captured["url"] == f"{BASE}/key/delete"
    assert captured["body"] == {"keys": ["sk-virtual-once"]}
    assert result["deleted_keys"] == ["sk-virtual-once"]


def test_revoke_block(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"blocked": True})

    monkeypatch.setattr(
        httpx,
        "request",
        lambda *a, **k: httpx.Client(transport=_transport(handler)).request(*a, **k),
    )
    client = KeyClient(base_url=BASE, master_key=MASTER)
    result = client.revoke("sk-virtual-once", mode="block")
    assert captured["url"] == f"{BASE}/key/block"
    assert captured["body"] == {"key": "sk-virtual-once"}
    assert result["blocked"] is True


def test_cli_keys_help() -> None:
    result = runner.invoke(app, ["keys", "--help"])
    assert result.exit_code == 0
    assert "create" in result.stdout
    assert "list" in result.stdout
    assert "revoke" in result.stdout


def test_cli_create_prints_key_once_not_master(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"key": "sk-virtual-cli", "key_alias": "demo"})

    monkeypatch.setattr(
        httpx,
        "request",
        lambda *a, **k: httpx.Client(transport=_transport(handler)).request(*a, **k),
    )
    monkeypatch.setenv("LITELLM_MASTER_KEY", MASTER)

    result = runner.invoke(
        app,
        [
            "keys",
            "create",
            "--models",
            "openai-general,anthropic-general",
            "--max-budget",
            "10",
            "--rpm",
            "60",
            "--key-alias",
            "demo",
            "--base-url",
            BASE,
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "sk-virtual-cli" in result.stdout
    assert MASTER not in result.stdout
    assert MASTER not in result.stderr
    assert "WARNING" in result.stderr or "WARNING" in result.stdout


def test_cli_create_missing_master(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LITELLM_MASTER_KEY", raising=False)
    result = runner.invoke(
        app, ["keys", "create", "--models", "llm-general", "--key-alias", "need-master"]
    )
    assert result.exit_code == 2
    assert "LITELLM_MASTER_KEY" in (result.stdout + result.stderr)


def test_cli_create_requires_key_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", MASTER)
    result = runner.invoke(app, ["keys", "create", "--models", "llm-general", "--base-url", BASE])
    assert result.exit_code == 2
    assert "--key-alias" in (result.stdout + result.stderr)


def test_cli_create_rejects_unknown_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INT-105: CLI wires --models through the same stable-alias validation."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", MASTER)
    mock_request = MagicMock()
    monkeypatch.setattr(httpx, "request", mock_request)
    result = runner.invoke(
        app,
        [
            "keys",
            "create",
            "--models",
            "not-a-real-alias",
            "--key-alias",
            "demo",
            "--base-url",
            BASE,
        ],
    )
    assert result.exit_code == 1, result.stdout + result.stderr
    assert "unknown model alias" in (result.stdout + result.stderr)
    mock_request.assert_not_called()


def test_cli_revoke(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/key/delete" in str(request.url)
        return httpx.Response(200, json={"deleted_keys": ["sk-x"]})

    monkeypatch.setattr(
        httpx,
        "request",
        lambda *a, **k: httpx.Client(transport=_transport(handler)).request(*a, **k),
    )
    monkeypatch.setenv("LITELLM_MASTER_KEY", MASTER)
    result = runner.invoke(
        app,
        ["keys", "revoke", "sk-x", "--base-url", BASE],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "OK" in result.stdout or "OK" in result.stderr
    assert MASTER not in result.stdout
    assert MASTER not in result.stderr
