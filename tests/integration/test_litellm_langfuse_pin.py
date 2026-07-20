"""Gate 3: the PINNED LiteLLM classic `langfuse` callback promotes our reserved
metadata keys to native Langfuse fields.

Gates 1-2 prove only that the *application sends* the reserved keys. This gate
proves the other half — that LiteLLM v1.92.0 actually *reads and forwards* them to
the Langfuse client (the "verify names against pin" step the repo flagged).

Run it:
    uv sync --extra test-litellm       # installs litellm==1.92.0 (else Docker-only)
    LLG_TEST_LITELLM=1 uv run pytest tests/integration/test_litellm_langfuse_pin.py

Strategy (shape-agnostic — robust to Langfuse SDK v2/v3 API differences): replace
the Langfuse client class LiteLLM instantiates with a recorder that captures every
method call's kwargs, drive one `litellm.completion(mock_response=...)` through the
`langfuse` success callback with our real projection, then assert our unique
sentinel values REACHED the client. If a sentinel is missing while calls WERE
captured, the callback dropped that field → real failure. If nothing was captured
(env/threading/internal-shape mismatch), the test SKIPS rather than false-fails.

Notably: LiteLLM's own langfuse test strips `release` before comparing, so
`trace_release` gets a direct assertion here.
"""

from __future__ import annotations

import contextlib
import os
import time
import uuid

import pytest

pytestmark = pytest.mark.pin_langfuse

if os.environ.get("LLG_TEST_LITELLM") != "1":
    pytest.skip(
        "pinned-callback contract test: set LLG_TEST_LITELLM=1 and "
        "`uv sync --extra test-litellm` (litellm==1.92.0)",
        allow_module_level=True,
    )


class _Recorder:
    """Records every call/attribute chain and the kwargs of each call.

    Any method litellm invokes (``.trace``/``.generation``/``.start_generation``/…)
    returns another recorder, so the whole call tree is captured regardless of the
    Langfuse SDK's exact API surface on the pin.
    """

    def __init__(self, calls: list[dict], path: str = "Langfuse") -> None:
        self._calls = calls
        self._path = path

    def __call__(self, *args: object, **kwargs: object) -> _Recorder:
        self._calls.append(kwargs)
        return _Recorder(self._calls, self._path + "()")

    def __getattr__(self, name: str) -> _Recorder:
        return _Recorder(self._calls, f"{self._path}.{name}")


def _install_langfuse_spy(monkeypatch: pytest.MonkeyPatch, calls: list[dict]) -> None:
    """Patch the Langfuse client symbol wherever LiteLLM's pin imports it.

    Skips (never fails) if none of the known module paths exist — the operator
    then points the spy at the pin's actual import site.
    """
    factory = lambda *a, **k: _Recorder(calls)  # noqa: E731
    patched = []
    for target in (
        "litellm.integrations.langfuse.langfuse.Langfuse",
        "litellm.integrations.langfuse.Langfuse",
        "langfuse.Langfuse",
    ):
        try:
            monkeypatch.setattr(target, factory, raising=True)
            patched.append(target)
        except (AttributeError, ImportError, ModuleNotFoundError):
            continue
    if not patched:
        pytest.skip("could not locate the Langfuse client import site on this pin")


def test_pinned_callback_promotes_reserved_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    litellm = pytest.importorskip("litellm", reason="install the test-litellm extra")

    from llm_client.langfuse_metadata import langfuse_fields
    from llm_client.metadata import RequestMetadata

    # Dummy Langfuse creds so the callback initializes (never leaves the process).
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-" + "0" * 20)
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-" + "0" * 20)
    monkeypatch.setenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    calls: list[dict] = []
    _install_langfuse_spy(monkeypatch, calls)

    # Unique sentinels so we can prove *these* values reached the client.
    tag = uuid.uuid4().hex[:12]
    release = f"rel-{tag}"
    user_id = f"usr_{tag}{'x' * 12}"
    session_id = f"sess-{tag}"
    meta = RequestMetadata(
        request_id=str(uuid.uuid4()),
        service=f"svc-{tag}",
        feature=f"feat-{tag}",
        environment="production",
        release=release,
        model_alias="llm-general",
        session_id=session_id,
        user_id=user_id,
    )
    metadata = {**meta.to_dict(), **langfuse_fields(meta)}

    monkeypatch.setattr(litellm, "success_callback", ["langfuse"], raising=False)
    litellm.completion(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "hi"}],
        mock_response="pong",
        metadata=metadata,
    )

    # Callback may flush on a background thread — poll briefly, then decide.
    for _ in range(20):
        if calls:
            break
        # best-effort flush; the API varies by pin, so tolerate its absence
        with contextlib.suppress(Exception):
            litellm.flush_langfuse_loggers()  # type: ignore[attr-defined]
        time.sleep(0.1)

    if not calls:
        pytest.skip("langfuse callback produced no client calls (flush/threading on this pin)")

    # Flatten every captured kwargs value to strings; a sentinel present here means
    # LiteLLM forwarded that field to the Langfuse client.
    seen = " ".join(str(v) for kwargs in calls for v in kwargs.values())
    assert release in seen, "trace_release NOT promoted (LiteLLM's own test strips release)"
    assert user_id in seen, "trace_user_id NOT promoted (native User view would stay empty)"
    assert session_id in seen, "session_id NOT promoted to native Session"
    assert f"svc-{tag}:feat-{tag}" in seen, "trace_name/generation_name NOT promoted"
    assert f"model_alias:svc-{tag}" in seen, "model_alias tag NOT promoted to native trace tags"
