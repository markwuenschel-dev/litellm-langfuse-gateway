"""Unit tests for LITELLM_BASE_URL dual-dialect normalization."""

from __future__ import annotations

import pytest

from llm_client.proxy_url import openai_base, proxy_root


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, "http://localhost:4000"),
        ("", "http://localhost:4000"),
        ("http://localhost:4000", "http://localhost:4000"),
        ("http://localhost:4000/", "http://localhost:4000"),
        ("http://localhost:4000/v1", "http://localhost:4000"),
        ("http://localhost:4000/v1/", "http://localhost:4000"),
        ("https://gw.example.com/v1", "https://gw.example.com"),
    ],
)
def test_proxy_root(raw: str | None, expected: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LITELLM_BASE_URL", raising=False)
    if raw is None:
        assert proxy_root() == expected
    else:
        assert proxy_root(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, "http://localhost:4000/v1"),
        ("http://localhost:4000", "http://localhost:4000/v1"),
        ("http://localhost:4000/v1", "http://localhost:4000/v1"),
        ("https://gw.example.com", "https://gw.example.com/v1"),
        ("https://gw.example.com/v1/", "https://gw.example.com/v1"),
    ],
)
def test_openai_base(raw: str | None, expected: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LITELLM_BASE_URL", raising=False)
    if raw is None:
        assert openai_base() == expected
    else:
        assert openai_base(raw) == expected


def test_from_env_dialect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_BASE_URL", "http://proxy:4000/v1")
    assert proxy_root() == "http://proxy:4000"
    assert openai_base() == "http://proxy:4000/v1"
