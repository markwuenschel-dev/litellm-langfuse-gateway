"""Check LiteLLM proxy liveliness / readiness endpoints."""

from __future__ import annotations

import argparse
import sys

import httpx

__all__ = ["main", "check_health"]

HEALTH_PATHS = ("/health/liveliness", "/health/readiness", "/health")


def check_health(
    base_url: str,
    path: str = "/health/liveliness",
    timeout: float = 10.0,
) -> tuple[int, str]:
    """Hit a health endpoint. Return (exit_code, message)."""
    url = f"{base_url.rstrip('/')}{path}"
    try:
        response = httpx.get(url, timeout=timeout)
    except httpx.HTTPError as exc:
        return 1, f"FAIL {url}: {exc}"

    body = response.text.strip()
    if response.is_success:
        return 0, f"OK {url} → {response.status_code} {body[:200]}"

    return 1, f"FAIL {url} → {response.status_code} {body[:500]}"


def main(argv: list[str] | None = None) -> int:
    from llm_client.proxy_url import proxy_root

    parser = argparse.ArgumentParser(description="Health-check the LiteLLM proxy.")
    parser.add_argument(
        "--base-url",
        default=proxy_root(),
        help="Proxy base URL without /v1 (default: http://localhost:4000)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds",
    )
    parser.add_argument(
        "--path",
        default="/health/liveliness",
        choices=HEALTH_PATHS,
        help="Health endpoint path",
    )
    args = parser.parse_args(argv)

    code, message = check_health(args.base_url, path=args.path, timeout=args.timeout)
    if code == 0:
        print(message)
    else:
        print(message, file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
