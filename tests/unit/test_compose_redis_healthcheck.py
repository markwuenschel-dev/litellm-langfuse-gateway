"""INT-115: Redis healthcheck must not put password on redis-cli argv."""

from __future__ import annotations

import yaml

from llg.paths import GATEWAY_DIR

COMPOSE_REDIS = GATEWAY_DIR / "compose.redis.yaml"


def test_redis_healthcheck_does_not_use_cli_password_flag() -> None:
    raw = yaml.safe_load(COMPOSE_REDIS.read_text(encoding="utf-8"))
    redis = raw["services"]["redis"]
    assert redis.get("environment", {}).get("REDISCLI_AUTH"), (
        "prefer REDISCLI_AUTH so redis-cli never needs -a"
    )
    hc_test = redis["healthcheck"]["test"]
    # Password on argv is visible in ps; healthcheck must be redis-cli ping only.
    assert hc_test == ["CMD", "redis-cli", "ping"]
    assert "-a" not in hc_test
