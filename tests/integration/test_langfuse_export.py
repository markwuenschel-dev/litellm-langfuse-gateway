"""Langfuse OTEL export checks.

Hermetic: asserts gateway config wires langfuse_otel callbacks and env docs.
Unit coverage for "client does not require LANGFUSE_*" lives in
``tests/unit/test_llm_client.py`` (GatewayClient succeeds with those env vars unset).

Live (LLG_LIVE=1): optional chat that should succeed even if Langfuse is misconfigured
(export must not break the LLM path). Full generation visibility still needs a real
Langfuse project and manual dashboard check — not asserted here.

Real outage / export-failure simulation is **manual** (e.g. wrong LANGFUSE_* on the
proxy, network drop to OTEL host). Automated live tests only check that chat returns
choices when the stack is up; they do not inject a Langfuse outage.
"""

from __future__ import annotations

import os

import pytest
import yaml

from llg.paths import REPO_ROOT

CONFIG_PATH = REPO_ROOT / "infra" / "llm-gateway" / "litellm-config.yaml"


def test_langfuse_otel_callbacks_in_config() -> None:
    """WP9 hermetic: pin-era success/failure callbacks include langfuse_otel."""
    assert CONFIG_PATH.is_file(), f"missing {CONFIG_PATH}"
    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    settings = data.get("litellm_settings") or {}
    success = settings.get("success_callback") or []
    failure = settings.get("failure_callback") or []
    callbacks = settings.get("callbacks") or []
    assert "langfuse_otel" in success or "langfuse_otel" in callbacks, (
        "expected langfuse_otel in success_callback or callbacks"
    )
    assert "langfuse_otel" in failure or "langfuse_otel" in callbacks, (
        "expected langfuse_otel in failure_callback or callbacks"
    )


def test_langfuse_env_documented_in_example() -> None:
    """Env template documents public/secret host + optional OTEL host."""
    example = REPO_ROOT / "infra" / "llm-gateway" / ".env.example"
    text = example.read_text(encoding="utf-8")
    for key in (
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_HOST",
        "LANGFUSE_OTEL_HOST",
    ):
        assert key in text, f"{key} missing from .env.example"


@pytest.mark.skipif(
    os.environ.get("LLG_LIVE") != "1",
    reason="Live stack required (set LLG_LIVE=1)",
)
def test_live_chat_does_not_require_langfuse_for_success() -> None:
    """Optional live: chat with virtual key succeeds regardless of Langfuse keys.

    Set LITELLM_VIRTUAL_KEY (and stack up with a provider key for the alias).
    Does not assert Langfuse dashboard visibility.

    **Manual only:** simulating a real Langfuse outage (bad keys on the *proxy*,
    blocked OTEL host) is out of scope for this gated test — run that by hand
    and confirm chat still succeeds while export fails separately.
    """
    import uuid

    from llm_client import GatewayClient, GatewayConfig, RequestMetadata

    if not os.environ.get("LITELLM_VIRTUAL_KEY"):
        pytest.skip("LITELLM_VIRTUAL_KEY not set")

    cfg = GatewayConfig.from_env()
    with GatewayClient(cfg) as client:
        meta = RequestMetadata(
            request_id=str(uuid.uuid4()),
            service="llg-integration",
            feature="langfuse-export-probe",
            environment="development",
            release="live-test",
            model_alias=os.environ.get("LITELLM_MODEL", "llm-general"),
            trace_id=f"live-{uuid.uuid4()}",
        )
        result = client.chat(
            model=meta.model_alias,
            messages=[{"role": "user", "content": "Reply with one word: pong"}],
            metadata=meta,
            max_tokens=16,
        )
    assert result.get("choices"), result
