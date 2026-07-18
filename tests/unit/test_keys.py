"""Unit tests for virtual key admin client and CLI (httpx mocked; no live stack)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from llg.cli import app
from llg.keys import KeyClient, KeyClientError, require_master_key

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
        client.create(models=["x"])
    assert exc_info.value.status_code == 401


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
    result = runner.invoke(app, ["keys", "create", "--models", "x"])
    assert result.exit_code == 2
    assert "LITELLM_MASTER_KEY" in (result.stdout + result.stderr)


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
