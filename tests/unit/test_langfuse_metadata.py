"""Gate 1: LiteLLM→Langfuse projection semantics (hermetic).

Proves only what the projection *derives* — NOT that LiteLLM promotes the keys
(that is Gate 3, tests/integration/test_litellm_langfuse_pin.py).
"""

from __future__ import annotations

import uuid

from llm_client.langfuse_metadata import LANGFUSE_RESERVED_KEYS, langfuse_fields
from llm_client.metadata import ALLOWED_FIELDS, RequestMetadata


def _meta(**overrides: object) -> RequestMetadata:
    base: dict[str, object] = {
        "request_id": str(uuid.uuid4()),
        "service": "checkout",
        "feature": "chat",
        "environment": "production",
        "release": "1.4.2",
        "model_alias": "llm-general",
    }
    base.update(overrides)
    return RequestMetadata(**base)  # type: ignore[arg-type]


def test_operation_name_used_for_trace_and_generation() -> None:
    fields = langfuse_fields(_meta())
    assert fields["trace_name"] == "checkout:chat"
    assert fields["generation_name"] == "checkout:chat"


def test_uses_trace_release_not_version() -> None:
    """Langfuse `release` (deployment) != `version` (component). release -> trace_release."""
    fields = langfuse_fields(_meta(release="abc123"))
    assert fields["trace_release"] == "abc123"
    assert "version" not in fields
    assert "trace_version" not in fields


def test_trace_user_id_only_when_user_id_present() -> None:
    assert "trace_user_id" not in langfuse_fields(_meta())
    with_user = langfuse_fields(_meta(user_id="usr_" + "a" * 16))
    assert with_user["trace_user_id"] == "usr_" + "a" * 16


def test_tags_exact_and_ordered() -> None:
    fields = langfuse_fields(_meta())
    assert fields["tags"] == [
        "env:production",
        "service:checkout",
        "feature:chat",
        "model_alias:llm-general",
    ]


def test_model_alias_tag_not_bare_model() -> None:
    """Gateway alias is distinct from Langfuse's native provided-model dimension."""
    tags = langfuse_fields(_meta())["tags"]
    assert "model_alias:llm-general" in tags
    assert not any(t.startswith("model:") for t in tags)


def test_tags_exclude_high_cardinality_identifiers() -> None:
    """Never tag request/release/session/user/trace identifiers (cardinality + bloat)."""
    meta = _meta(
        session_id="sess-xyz",
        user_id="usr_" + "b" * 16,
        trace_id="trace-xyz",
    )
    joined = " ".join(langfuse_fields(meta)["tags"])
    for high_card in (meta.request_id, meta.release, "sess-xyz", meta.user_id, "trace-xyz"):
        assert high_card not in joined


def test_reserved_keys_disjoint_from_contract() -> None:
    """Collision invariant: the attribution contract must never emit a reserved key,
    or the projection merge in client.py would shadow/collide (guarded there)."""
    assert LANGFUSE_RESERVED_KEYS.isdisjoint(ALLOWED_FIELDS)


def test_emitted_keys_are_all_reserved() -> None:
    """Everything the projection emits is a declared reserved key (guard coverage)."""
    assert set(langfuse_fields(_meta(user_id="usr_" + "c" * 16))).issubset(LANGFUSE_RESERVED_KEYS)
