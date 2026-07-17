"""Check LiteLLM proxy liveliness / readiness endpoints."""

from __future__ import annotations

import argparse
import os
import sys

import httpx


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Health-check the LiteLLM proxy.")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("LITELLM_BASE_URL", "http://localhost:4000").removesuffix("/v1"),
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
        choices=("/health/liveliness", "/health/readiness", "/health"),
        help="Health endpoint path",
    )
    args = parser.parse_args(argv)

    url = f"{args.base_url.rstrip('/')}{args.path}"
    try:
        response = httpx.get(url, timeout=args.timeout)
    except httpx.HTTPError as exc:
        print(f"FAIL {url}: {exc}", file=sys.stderr)
        return 1

    body = response.text.strip()
    if response.is_success:
        print(f"OK {url} → {response.status_code} {body[:200]}")
        return 0

    print(f"FAIL {url} → {response.status_code} {body[:500]}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
