"""INT-014: JSON Schema SoT must stay in lockstep with pure-Python constants."""

from __future__ import annotations

from llm_client.metadata import (
    ALLOWED_FIELDS,
    ENVIRONMENTS,
    OPTIONAL_FIELDS,
    REQUIRED_FIELDS,
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
