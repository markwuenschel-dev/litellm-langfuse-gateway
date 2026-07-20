"""INT-014 / INT-109: JSON Schema structural SoT must lockstep pure-Python constants.

Deeper than field names: required sets, types, maxLength, minLength, integer
bounds, additionalProperties. Secret/forbidden-key rules are pure-Python only
(schema description prose) — documented in metadata.py module docstring.
"""

from __future__ import annotations

from llm_client.metadata import (
    ALLOWED_FIELDS,
    ENVIRONMENTS,
    MAX_STRING_LEN,
    OPTIONAL_FIELDS,
    REQUIRED_FIELDS,
    RETRY_ATTEMPT_MAX,
    RETRY_ATTEMPT_MIN,
    load_schema,
)


def test_schema_required_matches_python() -> None:
    schema = load_schema()
    assert set(schema["required"]) == REQUIRED_FIELDS


def test_schema_properties_match_allowed_fields() -> None:
    schema = load_schema()
    props = set(schema["properties"].keys())
    assert props == ALLOWED_FIELDS
    assert props == REQUIRED_FIELDS | OPTIONAL_FIELDS


def test_schema_environment_enum_matches_python() -> None:
    schema = load_schema()
    env_enum = set(schema["properties"]["environment"]["enum"])
    assert env_enum == ENVIRONMENTS


def test_schema_forbids_additional_properties() -> None:
    schema = load_schema()
    assert schema.get("additionalProperties") is False


def test_schema_typed_fields_match_python_contract() -> None:
    schema = load_schema()
    props = schema["properties"]
    assert props["retry_attempt"]["type"] == "integer"
    assert props["fallback_used"]["type"] == "boolean"
    for key in REQUIRED_FIELDS | (OPTIONAL_FIELDS - {"retry_attempt", "fallback_used"}):
        assert props[key]["type"] == "string", key


def test_schema_string_max_length_matches_python() -> None:
    """Every schema property with maxLength must equal MAX_STRING_LEN (128)."""
    schema = load_schema()
    props = schema["properties"]
    with_max = {
        name: prop["maxLength"]
        for name, prop in props.items()
        if isinstance(prop, dict) and "maxLength" in prop
    }
    assert with_max, "expected bounded string fields in schema"
    for name, max_len in with_max.items():
        assert max_len == MAX_STRING_LEN, f"{name} maxLength={max_len} != {MAX_STRING_LEN}"


def test_schema_string_min_length_when_present() -> None:
    """Schema minLength:1 on non-enum/non-uuid bounded strings matches non-empty Python rule."""
    schema = load_schema()
    props = schema["properties"]
    for name, prop in props.items():
        if not isinstance(prop, dict) or prop.get("type") != "string":
            continue
        if "minLength" in prop:
            assert prop["minLength"] == 1, name
        # request_id is format:uuid (no minLength); environment is enum (no minLength)


def test_schema_retry_attempt_bounds_match_python() -> None:
    schema = load_schema()
    retry = schema["properties"]["retry_attempt"]
    assert retry["minimum"] == RETRY_ATTEMPT_MIN
    assert retry["maximum"] == RETRY_ATTEMPT_MAX
    assert RETRY_ATTEMPT_MIN == 0
    assert RETRY_ATTEMPT_MAX == 100


def test_schema_request_id_is_uuid_format() -> None:
    schema = load_schema()
    assert schema["properties"]["request_id"].get("format") == "uuid"


def test_schema_model_alias_described_as_echo() -> None:
    """INT-103 contract surface: schema documents model_alias as echo of model."""
    schema = load_schema()
    desc = schema["properties"]["model_alias"].get("description", "")
    assert "echo" in desc.lower()


def test_schema_description_mentions_forbidden_secrets() -> None:
    """Secrets are prose in schema; runtime enforcement is pure Python only."""
    schema = load_schema()
    desc = (schema.get("description") or "").lower()
    assert "secret" in desc or "forbidden" in desc
