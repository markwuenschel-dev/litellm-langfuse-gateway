"""Docker Compose helpers for the gateway stack."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from llg.paths import COMPOSE_FILE, COMPOSE_REDIS_FILE, GATEWAY_DIR

__all__ = ["compose_down", "compose_up"]


def _docker_compose_cmd() -> list[str]:
    if shutil.which("docker") is None:
        raise FileNotFoundError("docker not found on PATH; install Docker to use llg up/down")
    return ["docker", "compose"]


def _compose_files(redis: bool = False) -> list[Path]:
    files = [COMPOSE_FILE]
    if redis:
        files.append(COMPOSE_REDIS_FILE)
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(f"Compose file not found: {path}")
    return files


def run_compose(
    *compose_args: str,
    redis: bool = False,
    check: bool = True,
) -> int:
    """Run `docker compose -f ... <args>` with project dir = gateway infra."""
    cmd = _docker_compose_cmd()
    for path in _compose_files(redis=redis):
        cmd.extend(["-f", str(path)])
    cmd.extend(compose_args)

    print("+", " ".join(cmd), file=sys.stderr)
    result = subprocess.run(cmd, cwd=str(GATEWAY_DIR), check=False)
    if check and result.returncode != 0:
        return result.returncode
    return result.returncode


def compose_up(*, redis: bool = False, detach: bool = True) -> int:
    args = ["up"]
    if detach:
        args.append("-d")
    return run_compose(*args, redis=redis)


def compose_down(*, redis: bool = False, volumes: bool = False) -> int:
    args = ["down"]
    if volumes:
        args.append("-v")
    return run_compose(*args, redis=redis)
