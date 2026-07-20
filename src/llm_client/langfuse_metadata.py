"""Project the vendor-neutral attribution contract onto LiteLLM→Langfuse keys.

The :class:`~llm_client.metadata.RequestMetadata` contract stays vendor-neutral.
This module *derives* the reserved metadata keys that LiteLLM's classic ``langfuse``
callback promotes to **native Langfuse dimensions** (trace name, observation name,
release, user, tags) — it does not pollute the contract with vendor plumbing.

Why these names (verified against LiteLLM's langfuse callback + Langfuse docs):

- ``trace_release`` (NOT ``version``): Langfuse ``release`` identifies the app
  deployment (git SHA / semver); ``version`` identifies an *observation/component*
  version. ``RequestMetadata.release`` is a deployment identifier → ``trace_release``.
  We deliberately do **not** emit ``version`` until a genuine component/operation/
  prompt version exists.
- ``generation_name`` alongside ``trace_name``: Langfuse Metrics API v2 is
  observation-centric (no traces view), so stable *observation* names are required
  for reliable cost/latency/error/TTFT breakdowns.
- ``model_alias:`` tag (NOT ``model:``): Langfuse already has a native provided-model
  dimension for the real upstream model; the gateway routing alias is distinct.

Tag cardinality rule (load-bearing): tags are immutable after ingestion and each
value is capped (~200 chars). Only **low-cardinality** dimensions belong in tags —
env / service / feature / model_alias. Never tag identifiers (request_id, release,
session_id, user_id, trace_id): high cardinality makes filters useless and bloats
the project.

The reserved keys here are merged into the request body ``metadata`` *after* the
contract has been validated, so the derived values are always built from
already-screened inputs. See :func:`llm_client.client.GatewayClient.chat`.
"""

from __future__ import annotations

from typing import Any

from llm_client.metadata import RequestMetadata

__all__ = ["LANGFUSE_RESERVED_KEYS", "langfuse_fields"]

# Keys LiteLLM's classic `langfuse` callback consumes and promotes to native
# Langfuse trace/observation fields (rather than leaving in the metadata blob).
# A collision guard in client.py refuses to send if the attribution contract ever
# starts emitting one of these (a future contract change must not silently shadow
# the projection).
LANGFUSE_RESERVED_KEYS = frozenset(
    {
        "tags",
        "trace_name",
        "generation_name",
        "trace_user_id",
        "trace_release",
        "trace_version",
    }
)


def langfuse_fields(meta: RequestMetadata) -> dict[str, Any]:
    """Derive LiteLLM→Langfuse native-dimension keys from validated attribution.

    Returns only the reserved keys (see :data:`LANGFUSE_RESERVED_KEYS`); the caller
    merges them onto the validated attribution dict. ``trace_user_id`` is emitted
    only when ``user_id`` is set (its absence otherwise leaves the native User view
    unset rather than blank-keyed).

    Note: ``session_id`` is intentionally NOT projected here — it already flows under
    its own contract key and LiteLLM's callback maps it to the native Session
    dimension without a rename.
    """
    operation = f"{meta.service}:{meta.feature}"
    fields: dict[str, Any] = {
        "trace_name": operation,
        "generation_name": operation,
        "trace_release": meta.release,
        # LOW-cardinality tags only — see module docstring cardinality rule.
        "tags": [
            f"env:{meta.environment}",
            f"service:{meta.service}",
            f"feature:{meta.feature}",
            f"model_alias:{meta.model_alias}",
        ],
    }
    if meta.user_id is not None:
        # Fixes the empty Langfuse "Users" view: LiteLLM reads `trace_user_id`,
        # not `user_id`. Value is already pseudonym-validated by the contract.
        fields["trace_user_id"] = meta.user_id
    return fields
