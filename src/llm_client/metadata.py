"""Validate and serialize request metadata against the bounded contract.

Structural SoT (fields, types, required, maxLength, enums, integer bounds):
``config/llm/metadata-contract.schema.json``.

Runtime enforcement SoT is this pure-Python module (no jsonschema dependency).
It mirrors schema structure and **adds** secret/forbidden-key checks that the
JSON Schema document only describes in prose (not as formal patterns).

Parity of structural constraints is asserted in
``tests/unit/test_metadata_schema_parity.py``.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from llm_client.errors import MetadataValidationError

__all__ = [
    "ENVIRONMENTS",
    "REQUIRED_FIELDS",
    "OPTIONAL_FIELDS",
    "ALLOWED_FIELDS",
    "MAX_STRING_LEN",
    "RETRY_ATTEMPT_MIN",
    "RETRY_ATTEMPT_MAX",
    "USER_ID_PATTERN",
    "UNATTRIBUTED_SERVICE",
    "RequestMetadata",
    "schema_path",
    "load_schema",
    "validate_metadata",
    "metadata_to_dict",
]

ENVIRONMENTS = frozenset({"development", "staging", "production"})

REQUIRED_FIELDS = frozenset(
    {
        "request_id",
        "service",
        "feature",
        "environment",
        "release",
        "model_alias",
    }
)

OPTIONAL_FIELDS = frozenset(
    {
        "trace_id",
        "session_id",
        "user_id",
        "tenant_id",
        "cost_center",
        "workflow_type",
        "retry_attempt",
        "fallback_used",
        "experiment_variant",
    }
)

ALLOWED_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS

# Keys / header-like names that must never appear in metadata.
_FORBIDDEN_KEY_PATTERNS = (
    re.compile(r"authorization", re.I),
    re.compile(r"api[_-]?key", re.I),
    re.compile(r"secret", re.I),
    re.compile(r"password", re.I),
    re.compile(r"cookie", re.I),
    re.compile(r"bearer", re.I),
    re.compile(r"master[_-]?key", re.I),
    re.compile(r"virtual[_-]?key", re.I),
    re.compile(r"litellm[_-]?master", re.I),
    re.compile(r"token", re.I),
)

# Value shapes that look like secrets even under allowed keys.
_SECRET_VALUE_PATTERNS = (
    re.compile(r"^sk-[A-Za-z0-9_\-]{8,}$"),
    re.compile(r"^sk-proj-[A-Za-z0-9_\-]{8,}$"),
    re.compile(r"^pk-lf-[A-Za-z0-9_\-]{8,}$"),
    re.compile(r"^sk-lf-[A-Za-z0-9_\-]{8,}$"),
    re.compile(r"^Bearer\s+\S+", re.I),
    re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----"),
)

# Pseudonymous user id format. `user_id` becomes a first-class Langfuse dimension
# (mapped to `trace_user_id` → the native Users view), so generic secret screening
# is not enough: a raw email / name / MRN would pass the secret checks. Require an
# opaque `usr_<id>` shape and derive it upstream via a keyed HMAC — never a raw or
# unsalted-hashed enumerable identifier. See docs/llm-platform/privacy-and-retention.md.
_USER_ID_RE = re.compile(r"^usr_[A-Za-z0-9_\-]{16,80}$")
USER_ID_PATTERN = _USER_ID_RE.pattern

_STRING_FIELDS = ALLOWED_FIELDS - {"retry_attempt", "fallback_used"}
# Mirrors schema maxLength on bounded string properties (and blanket cap in Python).
MAX_STRING_LEN = 128
_MAX_STRING_LEN = MAX_STRING_LEN  # private alias used below
RETRY_ATTEMPT_MIN = 0
RETRY_ATTEMPT_MAX = 100


def schema_path() -> Path:
    """Absolute path to the JSON Schema file in this repo (when installed from source)."""
    # src/llm_client/metadata.py → repo root
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "config" / "llm" / "metadata-contract.schema.json",
        here.parents[3] / "config" / "llm" / "metadata-contract.schema.json",
        Path.cwd() / "config" / "llm" / "metadata-contract.schema.json",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def load_schema() -> dict[str, Any]:
    """Load the JSON Schema document (for docs/tools; runtime validation is pure Python)."""
    path = schema_path()
    if not path.is_file():
        raise FileNotFoundError(f"metadata contract schema not found: {path}")
    with path.open(encoding="utf-8") as fh:
        data: Any = json.load(fh)
    if not isinstance(data, dict):
        raise MetadataValidationError("metadata schema root must be an object")
    return data


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        return False
    return True


def _looks_like_secret_value(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    return any(p.search(stripped) for p in _SECRET_VALUE_PATTERNS)


def _check_forbidden_key(key: str) -> None:
    for pattern in _FORBIDDEN_KEY_PATTERNS:
        if pattern.search(key):
            raise MetadataValidationError(
                f"metadata key '{key}' is forbidden (secrets / auth material not allowed)"
            )


def validate_metadata(data: Mapping[str, Any], *, require_trace_id: bool = False) -> dict[str, Any]:
    """Validate a metadata mapping; return a sanitized dict for the request body.

    Raises:
        MetadataValidationError: on missing/unknown fields, bad types, or secrets.
    """
    if not isinstance(data, Mapping):
        raise MetadataValidationError("metadata must be a mapping")

    for key in data:
        if not isinstance(key, str):
            raise MetadataValidationError("metadata keys must be strings")
        _check_forbidden_key(key)
        if key not in ALLOWED_FIELDS:
            raise MetadataValidationError(
                f"unknown metadata field '{key}' (additionalProperties not allowed)"
            )

    missing = sorted(REQUIRED_FIELDS - set(data.keys()))
    if missing:
        raise MetadataValidationError(f"missing required metadata fields: {', '.join(missing)}")

    if require_trace_id and not data.get("trace_id"):
        raise MetadataValidationError("trace_id is required when the app creates a Langfuse root")

    out: dict[str, Any] = {}

    for key, value in data.items():
        if value is None:
            raise MetadataValidationError(f"metadata.{key} must not be null")

        if key in _STRING_FIELDS:
            if not isinstance(value, str):
                raise MetadataValidationError(f"metadata.{key} must be a string")
            if not value.strip():
                raise MetadataValidationError(f"metadata.{key} must be non-empty")
            if len(value) > _MAX_STRING_LEN:
                raise MetadataValidationError(
                    f"metadata.{key} exceeds max length {_MAX_STRING_LEN}"
                )
            if _looks_like_secret_value(value):
                raise MetadataValidationError(
                    f"metadata.{key} value looks like a secret or Authorization header"
                )
            if key == "request_id" and not _is_uuid(value):
                raise MetadataValidationError("metadata.request_id must be a UUID string")
            if key == "environment" and value not in ENVIRONMENTS:
                raise MetadataValidationError(
                    f"metadata.environment must be one of {sorted(ENVIRONMENTS)}"
                )
            if key == "user_id" and not _USER_ID_RE.match(value):
                raise MetadataValidationError(
                    "metadata.user_id must be a pseudonymous id matching "
                    f"'{USER_ID_PATTERN}' (e.g. usr_ + 16-80 chars [A-Za-z0-9_-]); "
                    "derive via a keyed HMAC — never a raw email/name/MRN"
                )
            out[key] = value
            continue

        if key == "retry_attempt":
            if isinstance(value, bool) or not isinstance(value, int):
                raise MetadataValidationError("metadata.retry_attempt must be an integer")
            if value < RETRY_ATTEMPT_MIN or value > RETRY_ATTEMPT_MAX:
                raise MetadataValidationError(
                    f"metadata.retry_attempt must be between "
                    f"{RETRY_ATTEMPT_MIN} and {RETRY_ATTEMPT_MAX}"
                )
            out[key] = value
            continue

        if key == "fallback_used":
            if not isinstance(value, bool):
                raise MetadataValidationError("metadata.fallback_used must be a boolean")
            out[key] = value
            continue

    return out


# Sentinel service name when the caller did not set SERVICE_NAME / metadata.service.
# Visible in Langfuse/spend so unattributed traffic is obvious.
UNATTRIBUTED_SERVICE = "unattributed"


@dataclass(frozen=True)
class RequestMetadata:
    """Typed request metadata for gateway chat calls."""

    request_id: str
    service: str
    feature: str
    environment: str
    release: str
    model_alias: str
    trace_id: str | None = None
    session_id: str | None = None
    user_id: str | None = None
    tenant_id: str | None = None
    cost_center: str | None = None
    workflow_type: str | None = None
    retry_attempt: int | None = None
    fallback_used: bool | None = None
    experiment_variant: str | None = None

    def to_dict(self, *, require_trace_id: bool = False) -> dict[str, Any]:
        raw = {k: v for k, v in asdict(self).items() if v is not None}
        return validate_metadata(raw, require_trace_id=require_trace_id)

    @property
    def is_unattributed(self) -> bool:
        """True when service is the unattributed sentinel (or empty after validate)."""
        return self.service.strip().lower() in {
            UNATTRIBUTED_SERVICE,
            "unknown",
            "unknown-service",
        }

    @classmethod
    def from_env(
        cls,
        *,
        model_alias: str,
        feature: str | None = None,
        service: str | None = None,
        environment: str | None = None,
        release: str | None = None,
        request_id: str | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> RequestMetadata:
        """Build required attribution fields from env + call site.

        Env map (all optional except model_alias argument):

        | Field | Env |
        | --- | --- |
        | service | ``SERVICE_NAME`` / ``LLG_SERVICE`` (default ``unattributed``) |
        | feature | ``FEATURE_NAME`` / ``LLG_FEATURE`` (default ``chat``) |
        | environment | ``ENVIRONMENT`` / ``LLG_ENVIRONMENT`` (default ``development``) |
        | release | ``GIT_SHA`` / ``RELEASE`` / ``LLG_RELEASE`` (default ``unknown``) |

        Use this so every GatewayClient call carries origin fields for Langfuse.
        """
        import os

        svc = (
            service
            or os.environ.get("SERVICE_NAME")
            or os.environ.get("LLG_SERVICE")
            or UNATTRIBUTED_SERVICE
        ).strip()
        feat = (
            feature or os.environ.get("FEATURE_NAME") or os.environ.get("LLG_FEATURE") or "chat"
        ).strip()
        env = (
            environment
            or os.environ.get("ENVIRONMENT")
            or os.environ.get("LLG_ENVIRONMENT")
            or "development"
        ).strip()
        if env not in ENVIRONMENTS:
            env = "development"
        rel = (
            release
            or os.environ.get("GIT_SHA")
            or os.environ.get("RELEASE")
            or os.environ.get("LLG_RELEASE")
            or "unknown"
        ).strip()
        rid = (request_id or str(uuid.uuid4())).strip()
        raw: dict[str, Any] = {
            "request_id": rid,
            "service": svc or UNATTRIBUTED_SERVICE,
            "feature": feat or "chat",
            "environment": env,
            "release": rel or "unknown",
            "model_alias": model_alias.strip(),
        }
        if extra:
            for k, v in extra.items():
                if v is not None and k not in raw:
                    raw[k] = v
        return cls.from_mapping(raw)

    @classmethod
    def from_mapping(
        cls,
        data: Mapping[str, Any],
        *,
        require_trace_id: bool = False,
    ) -> RequestMetadata:
        cleaned = validate_metadata(data, require_trace_id=require_trace_id)
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in cleaned.items() if k in known})


def metadata_to_dict(
    metadata: RequestMetadata | Mapping[str, Any],
    *,
    require_trace_id: bool = False,
) -> dict[str, Any]:
    """Normalize RequestMetadata or mapping into a validated dict."""
    if isinstance(metadata, RequestMetadata):
        return metadata.to_dict(require_trace_id=require_trace_id)
    return validate_metadata(metadata, require_trace_id=require_trace_id)
