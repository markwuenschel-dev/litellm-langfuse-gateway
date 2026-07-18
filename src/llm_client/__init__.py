"""Application client for the LiteLLM gateway (virtual key + metadata contract)."""

from __future__ import annotations

from llm_client.client import GatewayClient, GatewayConfig, disallow_master_key
from llm_client.errors import (
    BudgetExceeded,
    GatewayAuthError,
    GatewayConfigError,
    GatewayError,
    GatewayRateLimited,
    GatewayTimeout,
    GatewayUnavailable,
    MetadataValidationError,
    ModelAccessDenied,
    ProviderUnavailable,
)
from llm_client.metadata import RequestMetadata, load_schema, validate_metadata

__all__ = [
    "BudgetExceeded",
    "GatewayAuthError",
    "GatewayClient",
    "GatewayConfig",
    "GatewayConfigError",
    "GatewayError",
    "GatewayRateLimited",
    "GatewayTimeout",
    "GatewayUnavailable",
    "MetadataValidationError",
    "ModelAccessDenied",
    "ProviderUnavailable",
    "RequestMetadata",
    "disallow_master_key",
    "load_schema",
    "validate_metadata",
]

__version__ = "0.1.0"
