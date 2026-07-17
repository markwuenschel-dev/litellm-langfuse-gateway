"""Unit tests for metadata contract validation (hermetic)."""

from __future__ import annotations

import uuid

import pytest

from llm_client.errors import MetadataValidationError
from llm_client.metadata import RequestMetadata, load_schema, validate_metadata


def _valid(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "request_id": str(uuid.uuid4()),
        "service": "reference-app",
        "feature": "ping",
        "environment": "development",
        "release": "dev",
        "model_alias": "llm-general",
    }
    base.update(overrides)
    return base


def test_validate_accepts_required_fields() -> None:
    out = validate_metadata(_valid())
    assert out["service"] == "reference-app"
    assert out["model_alias"] == "llm-general"


def test_validate_accepts_optional_fields() -> None:
    out = validate_metadata(
        _valid(
            trace_id="trace-abc",
            session_id="sess-1",
            user_id="user-pseudo",
            retry_attempt=1,
            fallback_used=False,
        )
    )
    assert out["trace_id"] == "trace-abc"
    assert out["retry_attempt"] == 1
    assert out["fallback_used"] is False


def test_missing_required() -> None:
    data = _valid()
    del data["service"]
    with pytest.raises(MetadataValidationError, match="missing required"):
        validate_metadata(data)


def test_unknown_field_rejected() -> None:
    with pytest.raises(MetadataValidationError, match="unknown metadata field"):
        validate_metadata(_valid(extra_field="nope"))


def test_request_id_must_be_uuid() -> None:
    with pytest.raises(MetadataValidationError, match="UUID"):
        validate_metadata(_valid(request_id="not-a-uuid"))


def test_environment_enum() -> None:
    with pytest.raises(MetadataValidationError, match="environment"):
        validate_metadata(_valid(environment="dev"))


def test_rejects_authorization_key() -> None:
    data = _valid()
    # Bypass typed helper — simulate hostile key injection
    hostile = dict(data)
    hostile["Authorization"] = "Bearer sk-leak"
    with pytest.raises(MetadataValidationError, match="forbidden"):
        validate_metadata(hostile)


def test_rejects_api_key_field() -> None:
    hostile = dict(_valid())
    hostile["api_key"] = "sk-something-long-enough"
    with pytest.raises(MetadataValidationError, match="forbidden"):
        validate_metadata(hostile)


def test_rejects_secret_shaped_value() -> None:
    with pytest.raises(MetadataValidationError, match="secret"):
        validate_metadata(_valid(session_id="sk-abcdefghijklmnopqrstuv"))


def test_rejects_bearer_value() -> None:
    with pytest.raises(MetadataValidationError, match="secret"):
        validate_metadata(_valid(user_id="Bearer sk-abc12345"))


def test_require_trace_id() -> None:
    with pytest.raises(MetadataValidationError, match="trace_id"):
        validate_metadata(_valid(), require_trace_id=True)
    validate_metadata(_valid(trace_id="t1"), require_trace_id=True)


def test_request_metadata_dataclass() -> None:
    meta = RequestMetadata(
        request_id=str(uuid.uuid4()),
        service="svc",
        feature="feat",
        environment="staging",
        release="1.0.0",
        model_alias="llm-general",
        trace_id="trace-1",
    )
    d = meta.to_dict()
    assert d["environment"] == "staging"
    assert "session_id" not in d


def test_schema_file_loads() -> None:
    schema = load_schema()
    assert schema["title"]
    assert "request_id" in schema["properties"]
    assert set(schema["required"]) >= {
        "request_id",
        "service",
        "feature",
        "environment",
        "release",
        "model_alias",
    }
