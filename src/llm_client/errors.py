"""Stable gateway client errors (plan §7.3 error contract)."""

from __future__ import annotations

from typing import Any

__all__ = [
    "GatewayError",
    "GatewayConfigError",
    "MetadataValidationError",
    "GatewayAuthError",
    "ModelAccessDenied",
    "BudgetExceeded",
    "GatewayRateLimited",
    "ProviderUnavailable",
    "GatewayUnavailable",
    "GatewayTimeout",
    "map_http_error",
]


class GatewayError(Exception):
    """Base class for all gateway client failures."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class GatewayConfigError(GatewayError):
    """Missing/invalid client configuration (env, master-key policy, etc.)."""


class MetadataValidationError(GatewayError):
    """Request metadata failed the bounded contract."""


class GatewayAuthError(GatewayError):
    """Invalid, revoked, or unauthorized virtual key (HTTP 401/403)."""


class ModelAccessDenied(GatewayError):
    """Virtual key is not allowed to call the requested model alias."""


class BudgetExceeded(GatewayError):
    """Spend budget for the key/team was exceeded (fail closed)."""


class GatewayRateLimited(GatewayError):
    """Gateway-enforced rate limit (RPM/TPM), distinct from provider 429."""


class ProviderUnavailable(GatewayError):
    """Upstream provider failure after gateway retries (429/5xx from provider)."""


class GatewayUnavailable(GatewayError):
    """Gateway unreachable or returning infrastructure failure (no silent bypass)."""


class GatewayTimeout(GatewayError):
    """Request timed out waiting for the gateway."""


def _haystack(body: str | None, message: str) -> str:
    return f"{message} {body or ''}".lower()


def map_http_error(
    status_code: int,
    body: str | None = None,
    *,
    message: str | None = None,
) -> GatewayError:
    """Map HTTP status + LiteLLM error body to a stable client error type."""
    text = (body or "")[:500]
    msg = message or f"gateway HTTP {status_code}"
    if text:
        msg = f"{msg}: {text}"
    hay = _haystack(text, msg)

    if status_code in (401, 403):
        if any(
            token in hay
            for token in (
                "budget",
                "exceeded max budget",
                "crossed budget",
                "spend limit",
            )
        ):
            return BudgetExceeded(msg, status_code=status_code, body=text)
        if any(
            token in hay
            for token in (
                "not allowed to access model",
                "model access",
                "model not allowed",
                "does not have access",
                "key not allowed to access",
            )
        ):
            return ModelAccessDenied(msg, status_code=status_code, body=text)
        return GatewayAuthError(msg, status_code=status_code, body=text)

    if status_code == 400 and any(
        token in hay
        for token in (
            "not allowed to access model",
            "model access",
            "model not allowed",
            "invalid model",
        )
    ):
        return ModelAccessDenied(msg, status_code=status_code, body=text)

    if status_code == 429:
        if (
            any(
                token in hay
                for token in (
                    "provider",
                    "upstream",
                    "openai",
                    "anthropic",
                    "gemini",
                    "xai",
                    "rate_limit_error",
                )
            )
            and "litellm" not in hay
            and "rpm" not in hay
            and "tpm" not in hay
        ):
            return ProviderUnavailable(msg, status_code=status_code, body=text)
        # Prefer gateway rate-limit for key/rpm/tpm style messages
        if any(token in hay for token in ("rpm", "tpm", "rate limit", "rate_limit", "quota")):
            return GatewayRateLimited(msg, status_code=status_code, body=text)
        return GatewayRateLimited(msg, status_code=status_code, body=text)

    if status_code == 402 or (
        status_code in (400, 403) and any(t in hay for t in ("budget", "max budget", "spend"))
    ):
        return BudgetExceeded(msg, status_code=status_code, body=text)

    if status_code in (502, 503, 504):
        if any(t in hay for t in ("provider", "upstream", "openai", "anthropic")):
            return ProviderUnavailable(msg, status_code=status_code, body=text)
        return GatewayUnavailable(msg, status_code=status_code, body=text)

    if status_code >= 500:
        return GatewayUnavailable(msg, status_code=status_code, body=text)

    return GatewayError(msg, status_code=status_code, body=text)


def error_from_response(status_code: int, payload: Any) -> GatewayError:
    """Build an error from a parsed JSON body or raw text."""
    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict):
            message = str(err.get("message") or err.get("type") or payload)
        elif isinstance(err, str):
            message = err
        else:
            message = str(payload.get("message") or payload)
        body = str(payload)
    else:
        message = str(payload)
        body = str(payload) if payload is not None else None
    return map_http_error(status_code, body, message=message)
