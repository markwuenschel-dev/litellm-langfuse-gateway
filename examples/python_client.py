"""Minimal OpenAI-SDK client pointed at the local LiteLLM gateway.

Usage:
  export LITELLM_VIRTUAL_KEY=sk-...   # or LITELLM_MASTER_KEY for bootstrap only
  export LITELLM_BASE_URL=http://localhost:4000/v1
  pip install openai
  python examples/python_client.py
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    try:
        from openai import OpenAI
    except ImportError:
        print("Install the OpenAI SDK: pip install openai", file=sys.stderr)
        return 1

    api_key = os.environ.get("LITELLM_VIRTUAL_KEY") or os.environ.get("LITELLM_MASTER_KEY")
    if not api_key:
        print(
            "Set LITELLM_VIRTUAL_KEY (preferred) or LITELLM_MASTER_KEY in the environment.",
            file=sys.stderr,
        )
        return 1

    base_url = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000/v1")
    model = os.environ.get("LITELLM_MODEL", "llm-general")

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Reply with a single word: pong"}],
        max_tokens=16,
    )
    content = response.choices[0].message.content
    print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
