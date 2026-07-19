"""Docker harness for INT-001 LiteLLM pin Redis control-state spike.

Isolated Compose project + network; stops only its own Redis container.
Does not use LLG_LIVE (no real provider credentials).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import httpx

COMPOSE_DIR = Path(__file__).resolve().parent / "compose"
COMPOSE_FILE = COMPOSE_DIR / "compose.pin-spike.yaml"

MASTER_KEY = "sk-pin-spike-master"
MODEL = "pin-spike-model"

# Bounded wait after Redis stop before classifying request-path behavior.
# Open connections may briefly survive; first post-kill request need not fail.
OUTAGE_DETECTION_WINDOW_S = float(os.environ.get("PIN_SPIKE_OUTAGE_WINDOW_S", "15"))
REQUEST_TIMEOUT_S = float(os.environ.get("PIN_SPIKE_REQUEST_TIMEOUT_S", "20"))
STARTUP_TIMEOUT_S = float(os.environ.get("PIN_SPIKE_STARTUP_TIMEOUT_S", "180"))


class PinOutcome(StrEnum):
    """Characterization result classification (not soft-pass semantics)."""

    GREEN = "green"
    SILENT_DEGRADE = "silent-degrade"
    HARNESS_UNSTABLE = "harness-unstable"


@dataclass
class HealthSnapshot:
    liveliness_status: int | None
    readiness_status: int | None
    liveliness_body: str = ""
    readiness_body: str = ""


@dataclass
class OutageCharacterization:
    outcome: PinOutcome
    detail: str
    proxy_a_status: int | None = None
    proxy_b_status: int | None = None
    proxy_a_body: str = ""
    proxy_b_body: str = ""
    health_a: HealthSnapshot | None = None
    health_b: HealthSnapshot | None = None
    after_restore: dict[str, Any] = field(default_factory=dict)


@dataclass
class SharedLimitCharacterization:
    outcome: PinOutcome
    detail: str
    statuses: list[int] = field(default_factory=list)


class PinSpikeHarness:
    """Lifecycle manager for the dual-proxy pin-spike stack."""

    def __init__(self) -> None:
        self.project = f"llg-pin-{uuid.uuid4().hex[:10]}"
        self.port_a = int(os.environ.get("PIN_SPIKE_PORT_A", "14001"))
        self.port_b = int(os.environ.get("PIN_SPIKE_PORT_B", "14002"))
        self.base_a = f"http://127.0.0.1:{self.port_a}"
        self.base_b = f"http://127.0.0.1:{self.port_b}"
        self._started = False

    def _compose_cmd(self, *args: str) -> list[str]:
        return [
            "docker",
            "compose",
            "-p",
            self.project,
            "-f",
            str(COMPOSE_FILE),
            *args,
        ]

    def _run(
        self,
        *args: str,
        check: bool = True,
        capture: bool = False,
        timeout: float | None = 120,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PIN_SPIKE_PORT_A"] = str(self.port_a)
        env["PIN_SPIKE_PORT_B"] = str(self.port_b)
        cmd = self._compose_cmd(*args)
        result = subprocess.run(
            cmd,
            cwd=str(COMPOSE_DIR),
            env=env,
            check=False,
            capture_output=capture,
            text=True,
            timeout=timeout,
        )
        if check and result.returncode != 0:
            stderr = result.stderr if capture else ""
            raise RuntimeError(f"compose failed ({result.returncode}): {' '.join(cmd)}\n{stderr}")
        return result

    def require_docker(self) -> None:
        if shutil.which("docker") is None:
            raise RuntimeError("docker not found on PATH")
        probe = subprocess.run(
            ["docker", "info"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if probe.returncode != 0:
            raise RuntimeError(f"docker daemon not available: {probe.stderr[:300]}")

    def up(self) -> None:
        self.require_docker()
        if not COMPOSE_FILE.is_file():
            raise RuntimeError(f"missing compose file: {COMPOSE_FILE}")
        self._run("up", "-d", "--build", timeout=300)
        self._started = True
        self._wait_proxies_ready()

    def down(self) -> None:
        if not self._started and not self._project_exists():
            return
        try:
            self._run("down", "-v", "--remove-orphans", check=False, timeout=180)
        finally:
            self._started = False

    def _project_exists(self) -> bool:
        result = subprocess.run(
            ["docker", "compose", "-p", self.project, "ps", "-q"],
            cwd=str(COMPOSE_DIR),
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return bool(result.stdout.strip())

    def _wait_proxies_ready(self) -> None:
        deadline = time.monotonic() + STARTUP_TIMEOUT_S
        last_err = ""
        while time.monotonic() < deadline:
            try:
                for base in (self.base_a, self.base_b):
                    r = httpx.get(f"{base}/health/liveliness", timeout=5.0)
                    if r.status_code >= 400:
                        raise RuntimeError(f"{base} liveliness {r.status_code}")
                return
            except Exception as exc:  # noqa: BLE001 — aggregate startup wait
                last_err = str(exc)
                time.sleep(2.0)
        raise RuntimeError(f"proxies not ready within {STARTUP_TIMEOUT_S}s: {last_err}")

    def stop_redis(self) -> None:
        """Stop only this project's redis service (not host/operator Redis)."""
        self._run("stop", "redis", timeout=60)

    def start_redis(self) -> None:
        self._run("start", "redis", timeout=60)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            result = self._run("ps", "--status", "running", capture=True, check=False)
            if "redis" in (result.stdout or ""):
                # Give redis a moment after start
                time.sleep(2.0)
                return
            time.sleep(1.0)
        # Fallback: compose start may report ok even if ps format differs
        time.sleep(3.0)

    def create_virtual_key(self, *, rpm: int = 1) -> str:
        client = httpx.Client(
            base_url=self.base_a,
            headers={
                "Authorization": f"Bearer {MASTER_KEY}",
                "Content-Type": "application/json",
            },
            timeout=REQUEST_TIMEOUT_S,
        )
        try:
            response = client.post(
                "/key/generate",
                json={
                    "models": [MODEL],
                    "rpm_limit": rpm,
                    "key_alias": f"pin-spike-{self.project}-{uuid.uuid4().hex[:8]}",
                    "metadata": {"service": "pin-spike", "environment": "test"},
                },
            )
            if response.status_code >= 400:
                raise RuntimeError(f"key/generate → {response.status_code}: {response.text[:400]}")
            data = response.json()
            token = data.get("key") or data.get("token")
            if not token or not str(token).startswith("sk-"):
                raise RuntimeError(f"no virtual key in response: {data!r}")
            return str(token)
        finally:
            client.close()

    def chat(
        self,
        base: str,
        virtual_key: str,
        *,
        timeout: float | None = None,
    ) -> httpx.Response:
        return httpx.post(
            f"{base.rstrip('/')}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {virtual_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 16,
            },
            timeout=timeout or REQUEST_TIMEOUT_S,
        )

    def health_snapshot(self, base: str) -> HealthSnapshot:
        liveliness_status: int | None = None
        readiness_status: int | None = None
        liveliness_body = ""
        readiness_body = ""
        try:
            r = httpx.get(f"{base}/health/liveliness", timeout=5.0)
            liveliness_status = r.status_code
            liveliness_body = r.text[:300]
        except httpx.HTTPError as exc:
            liveliness_body = f"error: {exc}"
        try:
            r = httpx.get(f"{base}/health/readiness", timeout=5.0)
            readiness_status = r.status_code
            readiness_body = r.text[:300]
        except httpx.HTTPError as exc:
            readiness_body = f"error: {exc}"
        return HealthSnapshot(
            liveliness_status=liveliness_status,
            readiness_status=readiness_status,
            liveliness_body=liveliness_body,
            readiness_body=readiness_body,
        )

    def characterize_shared_limit(
        self, virtual_key: str, *, rpm: int = 1
    ) -> SharedLimitCharacterization:
        """Exhaust RPM via A then probe B. Green = B rejects after shared budget."""
        statuses: list[int] = []
        try:
            # Use rpm successful calls on A (plus small headroom attempts).
            for _ in range(rpm):
                r = self.chat(self.base_a, virtual_key)
                statuses.append(r.status_code)
                if r.status_code >= 500:
                    return SharedLimitCharacterization(
                        PinOutcome.HARNESS_UNSTABLE,
                        f"proxy A failed during budget fill: {r.status_code} {r.text[:200]}",
                        statuses,
                    )
            # One more on A should hit limit if local or shared.
            r_over_a = self.chat(self.base_a, virtual_key)
            statuses.append(r_over_a.status_code)
            # Fresh request on B should reject if shared control state works.
            r_b = self.chat(self.base_b, virtual_key)
            statuses.append(r_b.status_code)
        except httpx.HTTPError as exc:
            return SharedLimitCharacterization(
                PinOutcome.HARNESS_UNSTABLE,
                f"HTTP error during shared-limit: {exc}",
                statuses,
            )

        limit_codes = {429, 403}
        b_limited = r_b.status_code in limit_codes
        if b_limited:
            return SharedLimitCharacterization(
                PinOutcome.GREEN,
                f"B observed shared limit (status={r_b.status_code}); statuses={statuses}",
                statuses,
            )
        if r_b.status_code == 200:
            return SharedLimitCharacterization(
                PinOutcome.SILENT_DEGRADE,
                f"B still served after A exhausted rpm={rpm}; statuses={statuses}",
                statuses,
            )
        return SharedLimitCharacterization(
            PinOutcome.HARNESS_UNSTABLE,
            f"unexpected B status {r_b.status_code}: {r_b.text[:200]}; statuses={statuses}",
            statuses,
        )

    def characterize_redis_outage(self, virtual_key: str) -> OutageCharacterization:
        """Stop project Redis, wait detection window, classify request-path + native health."""
        try:
            self.stop_redis()
        except Exception as exc:  # noqa: BLE001
            return OutageCharacterization(
                PinOutcome.HARNESS_UNSTABLE,
                f"failed to stop project redis: {exc}",
            )

        time.sleep(OUTAGE_DETECTION_WINDOW_S)

        try:
            ra = self.chat(self.base_a, virtual_key, timeout=REQUEST_TIMEOUT_S)
            rb = self.chat(self.base_b, virtual_key, timeout=REQUEST_TIMEOUT_S)
        except httpx.HTTPError as exc:
            # Connection refused / total proxy death is not the fail-closed 503 contract,
            # but is not "local-only success" either — treat as harness-unstable unless
            # both return structured errors via httpx (they shouldn't if proxy is up).
            return OutageCharacterization(
                PinOutcome.HARNESS_UNSTABLE,
                f"HTTP transport error after redis stop: {exc}",
            )

        health_a = self.health_snapshot(self.base_a)
        health_b = self.health_snapshot(self.base_b)

        def _is_fail_closed(status: int, body: str) -> bool:
            if status == 503:
                return True
            # Accept related explicit unavailable signals if body names shared/redis.
            return status in (500, 502, 504) and any(
                token in body.lower() for token in ("redis", "shared_state", "cache", "unavailable")
            )

        a_closed = _is_fail_closed(ra.status_code, ra.text)
        b_closed = _is_fail_closed(rb.status_code, rb.text)
        a_local = ra.status_code == 200
        b_local = rb.status_code == 200

        if a_local or b_local:
            outcome = PinOutcome.SILENT_DEGRADE
            detail = (
                "pin served with local-only success while Redis stopped "
                f"(A={ra.status_code}, B={rb.status_code})"
            )
        elif a_closed and b_closed:
            outcome = PinOutcome.GREEN
            detail = (
                f"both proxies fail-closed after outage window "
                f"(A={ra.status_code}, B={rb.status_code})"
            )
        elif ra.status_code == 429 or rb.status_code == 429:
            # Fresh high-RPM keys should not 429 solely from prior tests.
            # Persistent 429 with Redis down without fail-closed is not GREEN.
            outcome = PinOutcome.SILENT_DEGRADE
            detail = (
                "pin returned rate-limit while Redis stopped without explicit "
                f"shared_state_unavailable/503 (A={ra.status_code}, B={rb.status_code}); "
                "treat as non-fail-closed control path"
            )
        else:
            outcome = PinOutcome.HARNESS_UNSTABLE
            detail = (
                f"ambiguous outage responses A={ra.status_code} B={rb.status_code}: "
                f"A={ra.text[:120]!r} B={rb.text[:120]!r}"
            )

        after_restore: dict[str, Any] = {}
        try:
            self.start_redis()
            time.sleep(OUTAGE_DETECTION_WINDOW_S)
            rr_a = self.chat(self.base_a, virtual_key)
            rr_b = self.chat(self.base_b, virtual_key)
            after_restore = {
                "proxy_a_status": rr_a.status_code,
                "proxy_b_status": rr_b.status_code,
                "health_a": self.health_snapshot(self.base_a).__dict__,
                "health_b": self.health_snapshot(self.base_b).__dict__,
            }
        except Exception as exc:  # noqa: BLE001
            after_restore = {"error": str(exc)}

        return OutageCharacterization(
            outcome=outcome,
            detail=detail,
            proxy_a_status=ra.status_code,
            proxy_b_status=rb.status_code,
            proxy_a_body=ra.text[:400],
            proxy_b_body=rb.text[:400],
            health_a=health_a,
            health_b=health_b,
            after_restore=after_restore,
        )
