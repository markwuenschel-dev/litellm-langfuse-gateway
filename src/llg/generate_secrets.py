"""Generate strong secrets for LiteLLM master key, salt key, and DB passwords."""

from __future__ import annotations

import argparse
import secrets
import sys
from urllib.parse import quote_plus

__all__ = ["generate_key", "generate_password", "database_url", "main"]


def generate_key(prefix: str = "sk-", nbytes: int = 32) -> str:
    """Return a URL-safe secret with an optional prefix (LiteLLM-style sk-...)."""
    return f"{prefix}{secrets.token_urlsafe(nbytes)}"


def generate_password(nbytes: int = 24) -> str:
    """Return a URL-safe password without a key-style prefix."""
    return secrets.token_urlsafe(nbytes)


def database_url(
    *,
    user: str = "litellm",
    password: str,
    host: str = "postgres",
    port: int = 5432,
    db: str = "litellm",
) -> str:
    """Build a Postgres URL with URL-encoded password (safe for special characters)."""
    return f"postgresql://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{quote_plus(db)}"


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
    parser.add_argument(
        "--postgres-user",
        default="litellm",
        help="POSTGRES_USER for DATABASE_URL (default: litellm)",
    )
    parser.add_argument(
        "--postgres-db",
        default="litellm",
        help="POSTGRES_DB for DATABASE_URL (default: litellm)",
    )
    args = parser.parse_args(argv)

    master = generate_key()
    salt = generate_key()
    postgres = generate_password()
    redis = generate_password()
    db_url = database_url(user=args.postgres_user, password=postgres, db=args.postgres_db)

    if args.format == "env":
        print(f"LITELLM_MASTER_KEY={master}")
        print(f"LITELLM_SALT_KEY={salt}")
        print(f"POSTGRES_USER={args.postgres_user}")
        print(f"POSTGRES_PASSWORD={postgres}")
        print(f"POSTGRES_DB={args.postgres_db}")
        print(f"DATABASE_URL={db_url}")
        print(f"REDIS_PASSWORD={redis}")
        print(
            "\n# Store LITELLM_SALT_KEY offline and treat it as permanent.\n"
            "# DATABASE_URL uses a URL-encoded password — required by compose.",
            file=sys.stderr,
        )
    else:
        print("LITELLM_MASTER_KEY:", master)
        print("LITELLM_SALT_KEY:  ", salt, "(permanent — do not rotate casually)")
        print("POSTGRES_PASSWORD: ", postgres)
        print("DATABASE_URL:      ", db_url, "(password URL-encoded)")
        print("REDIS_PASSWORD:    ", redis)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
