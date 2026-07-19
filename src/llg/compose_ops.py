"""Docker Compose helpers for the gateway stack."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from llg.paths import COMPOSE_FILE, COMPOSE_REDIS_FILE, GATEWAY_DIR, REPO_ROOT

__all__ = [
    "compose_down",
    "compose_up",
    "warn_if_root_env_without_gateway",
]


def _docker_compose_cmd() -> list[str]:
    if shutil.which("docker") is None:
        raise FileNotFoundError("docker not found on PATH; install Docker to use llg up/down")
    return ["docker", "compose"]


def warn_if_root_env_without_gateway() -> None:
    """Warn when a root .env exists but the canonical gateway .env does not.

    Does not read, copy, or infer values from the root file. Canonical path is
    always infra/llm-gateway/.env. Root docker-compose.yml is an include shim;
    from repo root, prefer --env-file infra/llm-gateway/.env or `llg up`.
    """
    root_env = REPO_ROOT / ".env"
    gateway_env = GATEWAY_DIR / ".env"
    if root_env.is_file() and not gateway_env.is_file():
        print(
            "warning: found repo-root .env but missing infra/llm-gateway/.env\n"
            "  Canonical proxy env is infra/llm-gateway/.env "
            "(root docker-compose.yml is an include shim).\n"
            "  Create: cp infra/llm-gateway/.env.example infra/llm-gateway/.env\n"
            "  llg does not load or copy the root .env.",
            file=sys.stderr,
        )


def _compose_files(redis_service: bool = False) -> list[Path]:
    files = [COMPOSE_FILE]
    if redis_service:
        files.append(COMPOSE_REDIS_FILE)
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(f"Compose file not found: {path}")
    return files


def run_compose(
    *compose_args: str,
    redis_service: bool = False,
    check: bool = True,
) -> int:
    """Run `docker compose -f ... <args>` with project dir = gateway infra."""
    cmd = _docker_compose_cmd()
    for path in _compose_files(redis_service=redis_service):
        cmd.extend(["-f", str(path)])
    cmd.extend(compose_args)

    print("+", " ".join(cmd), file=sys.stderr)
    result = subprocess.run(cmd, cwd=str(GATEWAY_DIR), check=False)
    if check and result.returncode != 0:
        return result.returncode
    return result.returncode


def compose_up(*, redis_service: bool = False, detach: bool = True) -> int:
    warn_if_root_env_without_gateway()
    args = ["up"]
    if detach:
        args.append("-d")
    return run_compose(*args, redis_service=redis_service)


def compose_down(*, redis_service: bool = False, volumes: bool = False) -> int:
    args = ["down"]
    if volumes:
        args.append("-v")
    return run_compose(*args, redis_service=redis_service)
