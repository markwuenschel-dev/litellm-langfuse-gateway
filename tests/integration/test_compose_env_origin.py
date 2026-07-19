"""Prove root docker-compose include is forced to gateway env via --env-file.

Root ``docker-compose.yml`` is an include shim. Compose still loads project
``.env`` from the working directory, so a root ``.env`` would otherwise win
for ``${VAR}`` interpolation. The supported root-shim invocation is:

    docker compose --env-file infra/llm-gateway/.env -f docker-compose.yml …

``uv run llg up`` is correct without that flag because it uses
``cwd = infra/llm-gateway``.

Requires Docker. Not ``LLG_LIVE`` (no providers).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from llg.paths import GATEWAY_DIR, REPO_ROOT

ROOT_COMPOSE = REPO_ROOT / "docker-compose.yml"
ROOT_ENV = REPO_ROOT / ".env"
GATEWAY_ENV = GATEWAY_DIR / ".env"

# Distinct non-secret sentinels — must not match each other.
ROOT_SENTINEL = "sk-env-origin-from-ROOT-not-gateway"
GATEWAY_SENTINEL = "sk-env-origin-from-GATEWAY-not-root"

pytestmark = [
    pytest.mark.skipif(shutil.which("docker") is None, reason="docker not on PATH"),
    pytest.mark.skipif(
        os.environ.get("LLG_COMPOSE_ENV_ORIGIN") == "0",
        reason="LLG_COMPOSE_ENV_ORIGIN=0 disables this test",
    ),
]


def _docker_ok() -> bool:
    try:
        r = subprocess.run(
            ["docker", "info"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _env_body(master_key: str) -> str:
    # Include DATABASE_URL (required by compose after INT-011) with the same
    # sentinel as master so origin assertions still work on one variable surface.
    return (
        f"LITELLM_MASTER_KEY={master_key}\n"
        f"LITELLM_SALT_KEY=sk-env-origin-salt-test-only\n"
        f"POSTGRES_PASSWORD=env-origin-postgres-test\n"
        f"DATABASE_URL=postgresql://litellm:env-origin-postgres-test@postgres:5432/{master_key}\n"
    )


def _clean_subprocess_env() -> dict[str, str]:
    """Drop host secrets so compose config must come from --env-file / .env files."""
    env = os.environ.copy()
    for key in (
        "LITELLM_MASTER_KEY",
        "LITELLM_SALT_KEY",
        "POSTGRES_PASSWORD",
        "DATABASE_URL",
        "REDIS_PASSWORD",
    ):
        env.pop(key, None)
    return env


@pytest.fixture
def dual_env_sentinels() -> None:
    """Write distinct root vs gateway .env files; restore previous state after."""
    if not _docker_ok():
        pytest.skip("docker daemon not available")

    backups: list[tuple[Path, bytes | None]] = []
    for path in (ROOT_ENV, GATEWAY_ENV):
        prev = path.read_bytes() if path.is_file() else None
        backups.append((path, prev))

    try:
        ROOT_ENV.write_text(_env_body(ROOT_SENTINEL), encoding="utf-8")
        GATEWAY_ENV.write_text(_env_body(GATEWAY_SENTINEL), encoding="utf-8")
        yield
    finally:
        for path, prev in backups:
            if prev is None:
                if path.is_file():
                    path.unlink()
            else:
                path.write_bytes(prev)


def test_root_compose_with_env_file_uses_gateway(dual_env_sentinels: None) -> None:
    """Supported root-shim invocation: --env-file gateway wins over root .env."""
    assert ROOT_COMPOSE.is_file()
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(GATEWAY_ENV),
            "-f",
            str(ROOT_COMPOSE),
            "config",
        ],
        cwd=str(REPO_ROOT),
        env=_clean_subprocess_env(),
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"compose config failed:\nstdout={result.stdout[:500]}\nstderr={result.stderr[:500]}"
    )
    out = result.stdout
    assert GATEWAY_SENTINEL in out, (
        "expected gateway .env sentinel when using --env-file infra/llm-gateway/.env"
    )
    assert ROOT_SENTINEL not in out, (
        "root .env sentinel leaked despite --env-file gateway — origin contract broken"
    )


def test_root_compose_without_env_file_prefers_root_cwd_env(
    dual_env_sentinels: None,
) -> None:
    """Documented footgun: bare root compose loads cwd .env (root), not gateway.

    This proves why docs require --env-file or llg up (cwd=gateway).
    """
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(ROOT_COMPOSE),
            "config",
        ],
        cwd=str(REPO_ROOT),
        env=_clean_subprocess_env(),
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr[:500]
    out = result.stdout
    assert ROOT_SENTINEL in out, (
        "expected root cwd .env to win without --env-file (Compose default); "
        "if this fails, update docs/tests for new Compose behavior"
    )
    assert GATEWAY_SENTINEL not in out


def test_warn_if_root_env_without_gateway(capsys: pytest.CaptureFixture[str]) -> None:
    """llg warns when root .env exists and gateway .env is missing; does not invent files."""
    from llg.compose_ops import warn_if_root_env_without_gateway

    backups: list[tuple[Path, bytes | None]] = []
    for path in (ROOT_ENV, GATEWAY_ENV):
        prev = path.read_bytes() if path.is_file() else None
        backups.append((path, prev))

    try:
        if GATEWAY_ENV.is_file():
            GATEWAY_ENV.unlink()
        ROOT_ENV.write_text("# root only placeholder\n", encoding="utf-8")
        warn_if_root_env_without_gateway()
        err = capsys.readouterr().err
        assert "infra/llm-gateway/.env" in err
        assert "does not load" in err or "not load" in err
        assert not GATEWAY_ENV.is_file(), "warn must not create gateway .env"
    finally:
        for path, prev in backups:
            if prev is None:
                if path.is_file():
                    path.unlink()
            else:
                path.write_bytes(prev)
