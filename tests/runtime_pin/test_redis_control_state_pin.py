"""INT-001 pin-compatibility spike: dual LiteLLM + Redis control-state.

Claim-neutral: does not change production ``--redis`` behavior or docs claims.

Enable with::

    set LLG_PIN_SPIKE=1   # PowerShell: $env:LLG_PIN_SPIKE = "1"
    uv run pytest tests/runtime_pin -m pin_spike -v

Outcome semantics (policy tests exit nonzero on silent-degrade):

- green: target invariants hold
- silent-degrade: harness ran; pin violated invariant → test fails
- harness-unstable: infrastructure could not establish scenario → test fails distinctly
"""

from __future__ import annotations

import os
import traceback

import pytest
from tests.runtime_pin.harness import (
    OUTAGE_DETECTION_WINDOW_S,
    PinOutcome,
    PinSpikeHarness,
)

# Never use LLG_LIVE for this suite (real providers). Docker runtime integration only.
pytestmark = [
    pytest.mark.pin_spike,
    pytest.mark.skipif(
        os.environ.get("LLG_PIN_SPIKE") != "1",
        reason="Set LLG_PIN_SPIKE=1 (Docker) to run pin-spike; not LLG_LIVE",
    ),
]


@pytest.fixture(scope="module")
def harness() -> PinSpikeHarness:
    h = PinSpikeHarness()
    try:
        h.up()
    except Exception as exc:  # noqa: BLE001
        h.down()
        pytest.fail(f"harness-unstable: stack failed to start: {exc}")
    try:
        yield h
    finally:
        h.down()


def _fail_for_outcome(kind: str, outcome: PinOutcome, detail: str) -> None:
    if outcome is PinOutcome.GREEN:
        return
    if outcome is PinOutcome.SILENT_DEGRADE:
        pytest.fail(f"silent-degrade [{kind}]: pin violated invariant (policy fail). {detail}")
    pytest.fail(f"harness-unstable [{kind}]: {detail}")


def test_shared_virtual_key_rpm_across_proxies(harness: PinSpikeHarness) -> None:
    """While Redis is up, budget consumed via A must be visible on B."""
    try:
        virtual_key = harness.create_virtual_key(rpm=1)
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"harness-unstable: virtual key create failed: {exc}")
    result = harness.characterize_shared_limit(virtual_key, rpm=1)
    print(f"PIN_SPIKE shared_limit outcome={result.outcome.value} detail={result.detail}")
    _fail_for_outcome("shared_limit", result.outcome, result.detail)


def test_redis_outage_request_path_fail_closed(harness: PinSpikeHarness) -> None:
    """After Redis stop + detection window, neither proxy may local-fallback succeed.

    Fresh high-RPM key avoids residual 429 from other tests being mistaken for
    fail-closed. Baseline proves the key works while Redis is healthy.
    """
    try:
        virtual_key = harness.create_virtual_key(rpm=100)
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"harness-unstable: virtual key create failed: {exc}")

    baseline = harness.chat(harness.base_a, virtual_key)
    if baseline.status_code != 200:
        pytest.fail(
            f"harness-unstable: baseline chat before outage failed "
            f"{baseline.status_code}: {baseline.text[:200]}"
        )

    print(
        f"PIN_SPIKE outage_window_s={OUTAGE_DETECTION_WINDOW_S} "
        "(fresh requests after window; first post-kill need not fail)"
    )
    result = harness.characterize_redis_outage(virtual_key)
    print(
        f"PIN_SPIKE outage outcome={result.outcome.value} detail={result.detail} "
        f"A={result.proxy_a_status} B={result.proxy_b_status}"
    )
    if result.health_a:
        print(
            "PIN_SPIKE native_health A "
            f"liveliness={result.health_a.liveliness_status} "
            f"readiness={result.health_a.readiness_status} "
            f"ready_body={result.health_a.readiness_body!r}"
        )
    if result.health_b:
        print(
            "PIN_SPIKE native_health B "
            f"liveliness={result.health_b.liveliness_status} "
            f"readiness={result.health_b.readiness_status} "
            f"ready_body={result.health_b.readiness_body!r}"
        )
    print(f"PIN_SPIKE after_restore={result.after_restore}")
    _fail_for_outcome("redis_outage", result.outcome, result.detail)


def test_characterize_native_health_endpoints_recorded(
    harness: PinSpikeHarness,
) -> None:
    """Record native liveliness/readiness while stack is healthy (characterization only).

    Redis-aware readiness is out of scope for the spike; product PR owns that probe.
    This test only ensures endpoints are probeable and evidence is printed — it does
    not require readiness to go red on outage (see outage test logs for that char).
    """
    try:
        ha = harness.health_snapshot(harness.base_a)
        hb = harness.health_snapshot(harness.base_b)
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"harness-unstable: health snapshot failed: {exc}\n{traceback.format_exc()}")

    print(f"PIN_SPIKE healthy_char A live={ha.liveliness_status} ready={ha.readiness_status}")
    print(f"PIN_SPIKE healthy_char B live={hb.liveliness_status} ready={hb.readiness_status}")
    if ha.liveliness_status is None or hb.liveliness_status is None:
        pytest.fail("harness-unstable: liveliness unreachable on healthy stack")
    assert ha.liveliness_status < 500
    assert hb.liveliness_status < 500
