"""Virtual key admin client: create / list / revoke via LiteLLM Proxy API.

Uses master-key admin endpoints only. Never logs or returns the master key.
Virtual key tokens are returned once on create for the caller to store.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

__all__ = [
    "KeyClientError",
    "KeyClient",
    "default_base_url",
    "require_master_key",
]


class KeyClientError(Exception):
    """HTTP or configuration failure talking to the LiteLLM key API."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def default_base_url() -> str:
    """Proxy base URL without trailing slash or /v1 suffix."""
    return (
        os.environ.get("LITELLM_BASE_URL", "http://localhost:4000").removesuffix("/v1").rstrip("/")
    )


def require_master_key(explicit: str | None = None) -> str:
    """Resolve master key from arg or LITELLM_MASTER_KEY. Never print it."""
    key = (explicit or os.environ.get("LITELLM_MASTER_KEY") or "").strip()
    if not key:
        raise KeyClientError(
            "LITELLM_MASTER_KEY is required (env or --master-key). "
            "Do not use the master key in applications; it is admin-only."
        )
    return key


@dataclass
class KeyClient:
    """Thin httpx wrapper around LiteLLM /key/* admin routes."""

    base_url: str
    master_key: str
    timeout: float = 30.0

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.master_key}",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}{path}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        try:
            response = httpx.request(
                method,
                self._url(path),
                headers=self._headers(),
                json=json,
                params=params,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise KeyClientError(f"request failed: {exc}") from exc

        if response.status_code >= 400:
            body = response.text[:500]
            raise KeyClientError(
                f"{method} {path} → {response.status_code}: {body}",
                status_code=response.status_code,
            )

        if not response.content:
            return {}
        try:
            data: Any = response.json()
        except ValueError as exc:
            raise KeyClientError(f"non-JSON response from {path}: {response.text[:200]}") from exc
        if not isinstance(data, (dict, list)):
            raise KeyClientError(f"unexpected JSON type from {path}: {type(data).__name__}")
        return data  # type: ignore[return-value]

    def create(
        self,
        *,
        models: list[str] | None = None,
        max_budget: float | None = None,
        rpm: int | None = None,
        team_id: str | None = None,
        key_alias: str | None = None,
        metadata: dict[str, Any] | None = None,
        budget_duration: str | None = None,
        tpm: int | None = None,
    ) -> dict[str, Any]:
        """POST /key/generate. Returns proxy JSON including the virtual `key` once."""
        body: dict[str, Any] = {}
        if models is not None:
            body["models"] = models
        if max_budget is not None:
            body["max_budget"] = max_budget
        if rpm is not None:
            body["rpm_limit"] = rpm
        if tpm is not None:
            body["tpm_limit"] = tpm
        if team_id is not None:
            body["team_id"] = team_id
        if key_alias is not None:
            body["key_alias"] = key_alias
        if metadata is not None:
            body["metadata"] = metadata
        if budget_duration is not None:
            body["budget_duration"] = budget_duration

        data = self._request("POST", "/key/generate", json=body)
        if not isinstance(data, dict):
            raise KeyClientError("unexpected list response from /key/generate")
        return data

    def list_keys(
        self,
        *,
        page: int = 1,
        size: int = 100,
        team_id: str | None = None,
    ) -> dict[str, Any] | list[Any]:
        """GET /key/list (non-secret metadata: aliases, spend, models — not full tokens)."""
        params: dict[str, Any] = {"page": page, "size": size}
        if team_id is not None:
            params["team_id"] = team_id
        return self._request("GET", "/key/list", params=params)

    def revoke(
        self,
        key: str,
        *,
        mode: str = "delete",
    ) -> dict[str, Any]:
        """Revoke a virtual key via POST /key/delete or POST /key/block.

        mode:
          - delete: permanently remove the key (default)
          - block: soft-disable (can be unblocked later via Admin UI/API)
        """
        token = key.strip()
        if not token:
            raise KeyClientError("key token is required for revoke")

        if mode == "block":
            data = self._request("POST", "/key/block", json={"key": token})
        elif mode == "delete":
            data = self._request("POST", "/key/delete", json={"keys": [token]})
        else:
            raise KeyClientError(f"unknown revoke mode: {mode!r} (use delete or block)")

        if not isinstance(data, dict):
            raise KeyClientError(f"unexpected list response from revoke ({mode})")
        return data
