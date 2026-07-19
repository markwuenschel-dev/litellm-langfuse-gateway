"""Minimal OpenAI-SDK client pointed at the local LiteLLM gateway.

Uses a **virtual key only** — never the master key. Always sends origin
metadata so Langfuse can show which service made the call.

Provision with:
  uv run llg keys create --models llm-general --max-budget 5 --rpm 30 --key-alias my-app

Usage:
  # Prefer loading infra/llm-gateway/.env.app (SERVICE_NAME + virtual key)
  export LITELLM_VIRTUAL_KEY=sk-...
  export LITELLM_BASE_URL=http://localhost:4000/v1
  export SERVICE_NAME=myapp
  # optional: LITELLM_MODEL=llm-general
  uv run --extra clients python examples/python_client.py

Prefer ``examples/reference_workflow.py`` + ``llm_client.GatewayClient`` for
typed metadata and error mapping.
"""

from __future__ import annotations

import os
import sys
import uuid


def main() -> int:
    try:
        from openai import OpenAI
    except ImportError:
        print(
            "Install the OpenAI SDK: uv sync --extra clients  (or pip install openai)",
            file=sys.stderr,
        )
        return 1

    api_key = (os.environ.get("LITELLM_VIRTUAL_KEY") or "").strip()
    if not api_key:
        print(
            "Set LITELLM_VIRTUAL_KEY (virtual key only; master key is admin-only).\n"
            "  uv run llg keys create --models llm-general --max-budget 5 --rpm 30 "
            "--key-alias my-app\n"
            "  See docs/llm-platform/app-wiring.md and infra/llm-gateway/.env.app.example",
            file=sys.stderr,
        )
        return 1
    if not api_key.startswith("sk-"):
        print(
            "LITELLM_VIRTUAL_KEY must start with 'sk-' (got a placeholder or wrong value).\n"
            "Paste the key printed by `llg keys create`, not the variable name.",
            file=sys.stderr,
        )
        return 1

    master = (os.environ.get("LITELLM_MASTER_KEY") or "").strip()
    disallow = os.environ.get("LLG_DISALLOW_MASTER", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    if disallow and master and api_key == master:
        print(
            "LITELLM_VIRTUAL_KEY must not be the master key "
            "(set LLG_DISALLOW_MASTER=0 only for break-glass).",
            file=sys.stderr,
        )
        return 1

    service = (
        os.environ.get("SERVICE_NAME") or os.environ.get("LLG_SERVICE") or ""
    ).strip()
    if not service:
        print(
            "Set SERVICE_NAME so Langfuse can attribute this call "
            "(see docs/llm-platform/call-attribution.md).",
            file=sys.stderr,
        )
        return 1

    base_url = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000/v1")
    model = os.environ.get("LITELLM_MODEL", "llm-general")
    environment = (
        os.environ.get("ENVIRONMENT") or os.environ.get("LLG_ENVIRONMENT") or "development"
    ).strip()
    feature = (
        os.environ.get("FEATURE_NAME") or os.environ.get("LLG_FEATURE") or "chat"
    ).strip()
    release = (
        os.environ.get("GIT_SHA")
        or os.environ.get("RELEASE")
        or os.environ.get("LLG_RELEASE")
        or "dev"
    ).strip()
    request_id = str(uuid.uuid4())

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Reply with a single word: pong"}],
        max_tokens=16,
        extra_body={
            "metadata": {
                "request_id": request_id,
                "service": service,
                "feature": feature,
                "environment": environment,
                "release": release,
                "model_alias": model,
            }
        },
    )
    content = response.choices[0].message.content
    print(f"request_id={request_id} service={service} model={model}")
    print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
