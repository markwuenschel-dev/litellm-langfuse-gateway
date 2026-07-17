"""Tests for scripts.generate_secrets."""

from __future__ import annotations

from scripts.generate_secrets import generate_key, generate_password, main


def test_generate_key_prefix() -> None:
    key = generate_key()
    assert key.startswith("sk-")
    assert len(key) > 10


def test_generate_password_no_sk_prefix_required() -> None:
    password = generate_password()
    assert len(password) >= 16


def test_main_env_format(capsys) -> None:  # type: ignore[no-untyped-def]
    code = main(["--format", "env"])
    assert code == 0
    out = capsys.readouterr().out
    assert "LITELLM_MASTER_KEY=sk-" in out
    assert "LITELLM_SALT_KEY=sk-" in out
    assert "POSTGRES_PASSWORD=" in out
