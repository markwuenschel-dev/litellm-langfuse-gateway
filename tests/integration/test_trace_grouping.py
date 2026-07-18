"""Trace / request_id correlation stubs.

Hermetic: metadata contract carries request_id + trace_id for correlation.
Live (LLG_LIVE=1): exercises chat with both ids; full Langfuse API join is deferred
until a project + credentials are available for automated fetch.
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

from llm_client import GatewayClient, GatewayConfig, RequestMetadata


def test_metadata_carries_correlation_ids() -> None:
    """Hermetic: request_id and trace_id round-trip into the chat body."""
    request_id = str(uuid.uuid4())
    trace_id = f"trace-{uuid.uuid4()}"
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-corr",
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            },
        )

    cfg = GatewayConfig(base_url="http://proxy.test/v1", virtual_key="sk-virtual")
    client = GatewayClient(cfg, transport=httpx.MockTransport(handler))
    meta = RequestMetadata(
        request_id=request_id,
        service="reference-app",
        feature="trace-grouping",
        environment="development",
        release="test",
        model_alias="llm-general",
        trace_id=trace_id,
    )
    client.chat(
        model="llm-general",
        messages=[{"role": "user", "content": "hi"}],
        metadata=meta,
    )
    client.close()
    assert captured["body"]["metadata"]["request_id"] == request_id
    assert captured["body"]["metadata"]["trace_id"] == trace_id


@pytest.mark.skipif(
    os.environ.get("LLG_LIVE") != "1",
    reason="Live stack required (set LLG_LIVE=1)",
)
def test_live_chat_with_correlation_metadata() -> None:
    """Optional live: send correlated metadata; assert OpenAI-shaped response.

    Does not fetch Langfuse traces (needs project API + credentials).
    """
    if not os.environ.get("LITELLM_VIRTUAL_KEY"):
        pytest.skip("LITELLM_VIRTUAL_KEY not set")

    request_id = str(uuid.uuid4())
    trace_id = f"live-trace-{uuid.uuid4()}"
    model = os.environ.get("LITELLM_MODEL", "llm-general")
    cfg = GatewayConfig.from_env()
    with GatewayClient(cfg) as client:
        result = client.chat(
            model=model,
            messages=[{"role": "user", "content": "Reply: ok"}],
            metadata=RequestMetadata(
                request_id=request_id,
                service="llg-integration",
                feature="trace-grouping",
                environment="development",
                release="live-test",
                model_alias=model,
                trace_id=trace_id,
            ),
            max_tokens=16,
        )
    assert result.get("choices")
    # Correlation keys for operators correlating proxy logs / Langfuse UI
    assert request_id
    assert trace_id
