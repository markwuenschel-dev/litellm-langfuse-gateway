"""Generate strong secrets for LiteLLM master key, salt key, and DB passwords."""

from __future__ import annotations

import argparse
import secrets
import sys


def generate_key(prefix: str = "sk-", nbytes: int = 32) -> str:
    """Return a URL-safe secret with an optional prefix (LiteLLM-style sk-...)."""
    return f"{prefix}{secrets.token_urlsafe(nbytes)}"


def generate_password(nbytes: int = 24) -> str:
    """Return a URL-safe password without a key-style prefix."""
    return secrets.token_urlsafe(nbytes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate secrets for LiteLLM gateway bootstrap (.env values)."
    )
    parser.add_argument(
        "--format",
        choices=("text", "env"),
        default="env",
        help="text: labeled lines; env: KEY=value lines ready to paste into .env",
    )
    args = parser.parse_args(argv)

    master = generate_key()
    salt = generate_key()
    postgres = generate_password()
    redis = generate_password()

    if args.format == "env":
        print(f"LITELLM_MASTER_KEY={master}")
        print(f"LITELLM_SALT_KEY={salt}")
        print(f"POSTGRES_PASSWORD={postgres}")
        print(f"REDIS_PASSWORD={redis}")
        print(
            "\n# Store LITELLM_SALT_KEY offline and treat it as permanent.",
            file=sys.stderr,
        )
    else:
        print("LITELLM_MASTER_KEY:", master)
        print("LITELLM_SALT_KEY:  ", salt, "(permanent — do not rotate casually)")
        print("POSTGRES_PASSWORD: ", postgres)
        print("REDIS_PASSWORD:    ", redis)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
