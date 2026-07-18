"""Reference vertical-slice workflow (WP12).

Demonstrates:
  1. Virtual-key-only gateway client (no master key, no provider keys)
  2. Bounded metadata contract (request_id, service, feature, env, release, alias, trace_id)
  3. Mockable Langfuse-style root/child hooks (no hard dependency on langfuse SDK)
  4. Default alias: llm-general

Usage:
  export LITELLM_VIRTUAL_KEY=sk-...          # required — create via: uv run llg keys create
  export LITELLM_BASE_URL=http://localhost:4000/v1
  # optional: LITELLM_MODEL=llm-general (default)
  uv run python examples/reference_workflow.py

Live stack required for a real completion. Without LITELLM_VIRTUAL_KEY the script exits 1.
"""

from __future__ import annotations

import os
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MockSpan:
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    children: list[MockSpan] = field(default_factory=list)
    status: str = "unset"
    output: Any = None

    def end(self, *, status: str = "ok", output: Any = None) -> None:
        self.status = status
        self.output = output


@dataclass
class MockTrace:
    """Stand-in for a Langfuse root trace (swap for real SDK in production apps)."""

    trace_id: str
    name: str
    metadata: dict[str, Any]
    spans: list[MockSpan] = field(default_factory=list)
    scores: list[dict[str, Any]] = field(default_factory=list)

    def start_span(self, name: str, **attributes: Any) -> MockSpan:
        span = MockSpan(name=name, attributes=dict(attributes))
        self.spans.append(span)
        return span

    def score(self, name: str, value: float, **kwargs: Any) -> None:
        self.scores.append({"name": name, "value": value, **kwargs})


def _start_root(*, service: str, feature: str, environment: str, release: str) -> MockTrace:
    return MockTrace(
        trace_id=f"trace-{uuid.uuid4()}",
        name=f"{service}:{feature}",
        metadata={
            "service": service,
            "feature": feature,
            "environment": environment,
            "release": release,
        },
    )


def run_workflow(
    *,
    client: Any | None = None,
    model: str = "llm-general",
    dry_run: bool = False,
) -> int:
    """Execute the reference workflow. Pass a mock client for hermetic demos."""
    from llm_client import GatewayClient, GatewayConfig, GatewayError, RequestMetadata

    request_id = str(uuid.uuid4())
    service = os.environ.get("LLG_SERVICE", "reference-app")
    feature = "ping"
    environment = os.environ.get("LLG_ENVIRONMENT", "development")
    release = os.environ.get("LLG_RELEASE", "dev")

    if environment not in {"development", "staging", "production"}:
        print(f"Invalid LLG_ENVIRONMENT={environment!r}", file=sys.stderr)
        return 1

    trace = _start_root(
        service=service,
        feature=feature,
        environment=environment,
        release=release,
    )

    # 1) Retrieval child (mock)
    retrieve = trace.start_span("retrieval", source="mock")
    retrieve.end(status="ok", output={"docs": 0})

    # 2) Gateway chat with metadata
    generation = trace.start_span("gateway.chat", model=model)
    meta = RequestMetadata(
        request_id=request_id,
        service=service,
        feature=feature,
        environment=environment,
        release=release,
        model_alias=model,
        trace_id=trace.trace_id,
        workflow_type="reference_ping",
    )

    if dry_run:
        generation.end(status="ok", output={"dry_run": True, "metadata": meta.to_dict()})
        trace.score("request_success", 1.0, comment="dry_run")
        print(f"dry_run request_id={request_id} trace_id={trace.trace_id} model={model}")
        return 0

    own_client = False
    if client is None:
        try:
            cfg = GatewayConfig.from_env()
        except GatewayError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        client = GatewayClient(cfg)
        own_client = True

    try:
        result = client.chat(
            model=model,
            messages=[{"role": "user", "content": "Reply with a single word: pong"}],
            metadata=meta,
            max_tokens=16,
            require_trace_id=True,
        )
        content = (
            (result.get("choices") or [{}])[0].get("message", {}).get("content")
            if isinstance(result, dict)
            else None
        )
        generation.end(status="ok", output={"content": content})
        # 3) Parse child
        parse = trace.start_span("parse")
        parse.end(status="ok", output={"parsed": content})
        # 4) Score
        trace.score("request_success", 1.0)
        print(content or result)
        print(
            f"# correlation request_id={request_id} trace_id={trace.trace_id}",
            file=sys.stderr,
        )
        return 0
    except GatewayError as exc:
        generation.end(status="error", output={"error": str(exc)})
        trace.score("request_success", 0.0, comment=type(exc).__name__)
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        if own_client:
            client.close()


def main() -> int:
    model = os.environ.get("LITELLM_MODEL", "llm-general")
    dry = os.environ.get("LLG_DRY_RUN") == "1"
    return run_workflow(model=model, dry_run=dry)


if __name__ == "__main__":
    raise SystemExit(main())
