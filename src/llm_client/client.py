"""OpenAI-compatible GatewayClient for the LiteLLM proxy (virtual key only)."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from llm_client.errors import (
    GatewayConfigError,
    GatewayError,
    GatewayTimeout,
    GatewayUnavailable,
    error_from_response,
)
from llm_client.metadata import RequestMetadata

__all__ = [
    "GatewayConfig",
    "GatewayClient",
    "disallow_master_key",
    "is_likely_master_key",
]


def _truthy_env(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def disallow_master_key() -> bool:
    """Whether master-key app traffic is rejected (default: true)."""
    return _truthy_env("LLG_DISALLOW_MASTER", default=True)


def is_likely_master_key(virtual_key: str, master_key: str | None = None) -> bool:
    """Heuristic: reject master-key shaped app credentials when detectable.

    Detection rules (when ``LLG_DISALLOW_MASTER`` is on):

    1. Exact match against ``LITELLM_MASTER_KEY`` (env or explicit ``master_key``).
    2. Virtual key starts with the configured master value (catches accidental
       paste of master as a longer token / prefix collision).

    Limitations (documented, not a full crypto/auth audit):

    - If ``LITELLM_MASTER_KEY`` is **unset** in this process, equality/prefix
      checks are a no-op — apps that never load the master key cannot compare.
    - Name-only heuristics (e.g. token contains the literal ``"master"``) are
      **not** applied: LiteLLM virtual keys are opaque and may coincidentally
      include that substring. Rely on env comparison + not shipping master to apps.
    - Does not call the proxy to classify keys; server-side auth still decides.
    """
    key = virtual_key.strip()
    if not key:
        return False
    mk = (
        master_key if master_key is not None else os.environ.get("LITELLM_MASTER_KEY") or ""
    ).strip()
    if not mk:
        return False
    if key == mk:
        return True
    # Prefix: same secret value used as a leading substring (min length avoids
    # pathological short master placeholders matching every key).
    return bool(len(mk) >= 8 and key.startswith(mk))


@dataclass(frozen=True)
class GatewayConfig:
    """Client configuration: OpenAI-compatible base URL + virtual key.

    Application traffic only. Does not require ``LANGFUSE_*`` (observability is
    proxy-side). Master-key refusal depends on ``LLG_DISALLOW_MASTER`` (default on)
    and ``is_likely_master_key`` — see that function for detection limits.
    """

    base_url: str
    virtual_key: str
    timeout: float = 60.0
    disallow_master: bool = True

    @classmethod
    def from_env(
        cls,
        *,
        timeout: float | None = None,
        disallow_master: bool | None = None,
    ) -> GatewayConfig:
        """Load from LITELLM_BASE_URL + LITELLM_VIRTUAL_KEY.

        Does not fall back to LITELLM_MASTER_KEY. Does not require LANGFUSE_*.
        Raises GatewayConfigError if virtual key is missing or matches the master
        key under disallow policy (see ``is_likely_master_key`` limitations).
        """
        from llm_client.proxy_url import openai_base

        # Normalize dual dialect: with or without /v1 → always OpenAI-compatible base
        root = openai_base(os.environ.get("LITELLM_BASE_URL"))

        key = (os.environ.get("LITELLM_VIRTUAL_KEY") or "").strip()
        if not key:
            raise GatewayConfigError(
                "LITELLM_VIRTUAL_KEY is required. Applications must not use "
                "LITELLM_MASTER_KEY; provision a virtual key with `uv run llg keys create`."
            )

        policy = disallow_master_key() if disallow_master is None else disallow_master
        if policy and is_likely_master_key(key):
            raise GatewayConfigError(
                "LITELLM_VIRTUAL_KEY matches LITELLM_MASTER_KEY. "
                "Master key is admin-only; set LLG_DISALLOW_MASTER=0 only for break-glass."
            )

        # Reject if apps accidentally point transport at a provider key env.
        for provider_env in (
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GEMINI_API_KEY",
            "XAI_API_KEY",
        ):
            provider_val = (os.environ.get(provider_env) or "").strip()
            if provider_val and key == provider_val:
                raise GatewayConfigError(
                    f"LITELLM_VIRTUAL_KEY must not equal {provider_env}. "
                    "Apps call the gateway with a virtual key only."
                )

        return cls(
            base_url=root,
            virtual_key=key,
            timeout=60.0 if timeout is None else timeout,
            disallow_master=policy,
        )


class GatewayClient:
    """Thin httpx client for ``POST /v1/chat/completions`` via LiteLLM.

    Virtual-key only by default (``LLG_DISALLOW_MASTER``). Does not require
    ``LANGFUSE_*`` — gateway OTEL export is proxy-side; missing Langfuse env
    must not block chat. Master-key detection is best-effort equality/prefix
    against ``LITELLM_MASTER_KEY`` when that env is present (see
    ``is_likely_master_key``).
    """

    def __init__(
        self,
        config: GatewayConfig | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config or GatewayConfig.from_env()
        if self.config.disallow_master and is_likely_master_key(self.config.virtual_key):
            raise GatewayConfigError(
                "Refusing to use master key as application credential "
                "(LLG_DISALLOW_MASTER is enabled)."
            )
        self._client = httpx.Client(
            base_url=self.config.base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {self.config.virtual_key}",
                "Content-Type": "application/json",
            },
            timeout=self.config.timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> GatewayClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def chat(
        self,
        *,
        model: str,
        messages: Sequence[Mapping[str, Any]],
        metadata: RequestMetadata | Mapping[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra_body: Mapping[str, Any] | None = None,
        require_trace_id: bool = False,
        require_attribution: bool | None = None,
    ) -> dict[str, Any]:
        """Call chat completions; always attach validated origin metadata.

        If ``metadata`` is omitted, builds fields from env via
        :meth:`RequestMetadata.from_env` (``SERVICE_NAME``, ``ENVIRONMENT``, …).
        Unattributed traffic still sends ``service=unattributed`` so Langfuse
        shows *something*. Set ``LLG_REQUIRE_ATTRIBUTION=1`` (or pass
        ``require_attribution=True``) to refuse calls without a real service name.

        Returns the parsed JSON body (OpenAI-compatible).
        """
        if not model or not str(model).strip():
            raise GatewayConfigError("model is required (use a gateway alias, e.g. llm-general)")
        if not messages:
            raise GatewayConfigError("messages must be a non-empty sequence")

        if metadata is None:
            meta_obj = RequestMetadata.from_env(model_alias=str(model).strip())
        elif isinstance(metadata, RequestMetadata):
            meta_obj = metadata
        else:
            meta_obj = RequestMetadata.from_mapping(metadata, require_trace_id=require_trace_id)

        # Cross-check model_alias when caller provided metadata with a different alias.
        if meta_obj.model_alias != str(model).strip():
            meta_obj = RequestMetadata.from_mapping(
                {
                    **meta_obj.to_dict(require_trace_id=require_trace_id),
                    "model_alias": str(model).strip(),
                },
                require_trace_id=require_trace_id,
            )

        must_attr = (
            require_attribution
            if require_attribution is not None
            else _truthy_env("LLG_REQUIRE_ATTRIBUTION", default=False)
        )
        if must_attr and meta_obj.is_unattributed:
            raise GatewayConfigError(
                "request is unattributed: set SERVICE_NAME (or pass metadata.service) "
                "so Langfuse/spend can identify the caller. "
                "Unset LLG_REQUIRE_ATTRIBUTION to allow service=unattributed."
            )

        body: dict[str, Any] = {
            "model": model,
            "messages": list(messages),
            "metadata": meta_obj.to_dict(require_trace_id=require_trace_id),
        }
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if extra_body:
            for k, v in extra_body.items():
                if k in {"model", "messages", "metadata"}:
                    continue
                body[k] = v

        try:
            response = self._client.post("/chat/completions", json=body)
        except httpx.TimeoutException as exc:
            raise GatewayTimeout(f"gateway timeout: {exc}") from exc
        except httpx.HTTPError as exc:
            raise GatewayUnavailable(f"gateway unavailable: {exc}") from exc

        if response.status_code >= 400:
            try:
                payload: Any = response.json()
            except ValueError:
                payload = response.text
            raise error_from_response(response.status_code, payload)

        try:
            data: Any = response.json()
        except ValueError as exc:
            raise GatewayError(
                f"non-JSON response: {response.text[:200]}",
                status_code=response.status_code,
            ) from exc
        if not isinstance(data, dict):
            raise GatewayError(
                f"unexpected JSON type: {type(data).__name__}",
                status_code=response.status_code,
            )
        return data
