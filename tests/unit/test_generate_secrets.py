"""Tests for llg.generate_secrets (and scripts re-export)."""

from __future__ import annotations

from urllib.parse import unquote

from llg.generate_secrets import database_url, generate_key, generate_password, main
from scripts.generate_secrets import generate_key as scripts_generate_key


def test_generate_key_prefix() -> None:
    key = generate_key()
    assert key.startswith("sk-")
    assert len(key) > 10


def test_scripts_reexport_callable() -> None:
    key = scripts_generate_key()
    assert key.startswith("sk-")


def test_generate_password_no_sk_prefix_required() -> None:
    password = generate_password()
    assert len(password) >= 16


def test_database_url_encodes_special_password() -> None:
    url = database_url(password="p@ss:w/rd#1")
    assert "p@ss" not in url  # raw specials must not appear unencoded
    assert "p%40ss" in url or "%40" in url
    assert "postgres:5432" in url
    # Recoverable via unquote of password segment
    userinfo = url.split("://", 1)[1].split("@", 1)[0]
    _, enc_pw = userinfo.split(":", 1)
    assert unquote(enc_pw) == "p@ss:w/rd#1"


def test_main_env_format(capsys) -> None:  # type: ignore[no-untyped-def]
    code = main(["--format", "env"])
    assert code == 0
    out = capsys.readouterr().out
    assert "LITELLM_MASTER_KEY=sk-" in out
    assert "LITELLM_SALT_KEY=sk-" in out
    assert "POSTGRES_PASSWORD=" in out
    assert "DATABASE_URL=postgresql://" in out
