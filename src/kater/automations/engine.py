"""Process-wide automation engine: schedule, run, and persist status."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from kater.automations.builtins import KNOWN_KINDS, run_kind
from kater.automations.models import Automation, AutomationRunResult, new_automation_id
from kater.automations.store import AutomationStore, reset_cache

_log = logging.getLogger("kater.automations.engine")

DEFAULT_AUTOMATIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "auto_doctor_watch",
        "name": "Doctor watch",
        "kind": "doctor_watch",
        "schedule_seconds": 900,
        "config": {"profile": "core"},
    },
    {
        "id": "auto_browser_reap",
        "name": "Browser session reap",
        "kind": "browser_reap",
        "schedule_seconds": 120,
        "config": {},
    },
    {
        "id": "auto_telemetry_prune",
        "name": "Telemetry prune",
        "kind": "telemetry_prune",
        "schedule_seconds": 3600,
        "config": {},
    },
    {
        "id": "auto_credential_nudge",
        "name": "Credential nudge",
        "kind": "credential_nudge",
        "schedule_seconds": 1800,
        "config": {"profile": "core"},
    },
)


class AutomationEngine:
    """CRUD + scheduled execution for automations."""

    def __init__(
        self,
        store: AutomationStore | None = None,
        *,
        clock: Any | None = None,
    ) -> None:
        self._store = store or AutomationStore()
        self._clock = clock or time.time
        self._lock = threading.RLock()
        self._in_flight: set[str] = set()
        self._defaults_ensured = False

    def ensure_defaults(self) -> list[Automation]:
        """Seed the four built-in schedules when the table is empty."""
        with self._lock:
            if self._defaults_ensured and self._store.count() > 0:
                return self._store.list()
            if self._store.count() == 0:
                now = float(self._clock())
                for spec in DEFAULT_AUTOMATIONS:
                    self._store.upsert(
                        Automation(
                            id=str(spec["id"]),
                            name=str(spec["name"]),
                            kind=str(spec["kind"]),
                            enabled=True,
                            schedule_seconds=int(spec["schedule_seconds"]),
                            config=dict(spec.get("config") or {}),
                            created_at=now,
                            updated_at=now,
                        )
                    )
                _log.info("seeded %d default automations", len(DEFAULT_AUTOMATIONS))
            self._defaults_ensured = True
            return self._store.list()

    def list(self) -> list[Automation]:
        return self._store.list()

    def get(self, automation_id: str) -> Automation | None:
        return self._store.get(automation_id)

    def set_enabled(self, automation_id: str, enabled: bool) -> Automation | None:
        return self._store.set_enabled(automation_id, enabled)

    def upsert(
        self,
        *,
        id: str | None = None,
        name: str,
        kind: str,
        enabled: bool = True,
        schedule_seconds: int = 0,
        config: dict[str, Any] | None = None,
    ) -> Automation:
        if kind not in KNOWN_KINDS:
            raise ValueError(f"unknown automation kind: {kind}")
        now = float(self._clock())
        automation_id = id or new_automation_id()
        existing = self._store.get(automation_id)
        created_at = existing.created_at if existing is not None else now
        record = Automation(
            id=automation_id,
            name=name,
            kind=kind,
            enabled=enabled,
            schedule_seconds=int(schedule_seconds),
            config=dict(config or {}),
            last_run_at=existing.last_run_at if existing is not None else None,
            last_status=existing.last_status if existing is not None else None,
            last_error=existing.last_error if existing is not None else None,
            created_at=created_at,
            updated_at=now,
        )
        return self._store.upsert(record)

    def delete(self, automation_id: str) -> bool:
        return self._store.delete(automation_id)

    def tick(self) -> int:
        """Run every enabled automation that is due. Returns how many ran.

        Due automations are claimed under the lock (recorded in
        ``self._in_flight``) and then executed *outside* it, so a long-running
        ``run_kind`` never blocks a concurrent ``run_now`` on a different
        automation. An automation already in flight is skipped this tick.
        """
        now = float(self._clock())
        due: list[Automation] = []
        with self._lock:
            for automation in self._store.list():
                if not automation.enabled:
                    continue
                if automation.schedule_seconds <= 0:
                    continue
                if (
                    automation.last_run_at is not None
                    and (now - automation.last_run_at) < automation.schedule_seconds
                ):
                    continue
                if automation.id in self._in_flight:
                    continue
                self._in_flight.add(automation.id)
                due.append(automation)
        ran = 0
        for automation in due:
            try:
                self._execute(automation, ran_at=now)
                ran += 1
            finally:
                with self._lock:
                    self._in_flight.discard(automation.id)
        return ran

    def run_now(self, automation_id: str, *, force: bool = False) -> AutomationRunResult:
        with self._lock:
            automation = self._store.get(automation_id)
            if automation is None:
                raise KeyError(automation_id)
            if not automation.enabled and not force:
                raise ValueError(f"automation {automation_id} is disabled")
            if automation_id in self._in_flight:
                raise ValueError(f"automation {automation_id} is already running")
            self._in_flight.add(automation_id)
        try:
            return self._execute(automation, ran_at=float(self._clock()))
        finally:
            with self._lock:
                self._in_flight.discard(automation_id)

    def _execute(self, automation: Automation, *, ran_at: float) -> AutomationRunResult:
        started = time.perf_counter()
        status = "ok"
        error: str | None = None
        detail: dict[str, Any] = {}
        try:
            detail = run_kind(automation.kind, automation.config)
        except Exception as exc:
            status = "error"
            error = str(exc)
            _log.warning(
                "automation %s (%s) failed: %s", automation.id, automation.kind, exc
            )
        duration_ms = (time.perf_counter() - started) * 1000.0
        self._store.record_run(
            automation.id, ran_at=ran_at, status=status, error=error
        )
        result = AutomationRunResult(
            id=automation.id,
            kind=automation.kind,
            status=status,
            error=error,
            detail=detail,
            duration_ms=duration_ms,
            ran_at=ran_at,
        )
        self._broadcast(result)
        return result

    def _broadcast(self, result: AutomationRunResult) -> None:
        try:
            from kater.websocket import broadcast_event

            broadcast_event(
                {
                    "type": "automation_run",
                    "id": result.id,
                    "kind": result.kind,
                    "status": result.status,
                    "error": result.error,
                    "detail": result.detail,
                    "duration_ms": result.duration_ms,
                    "ts": result.ran_at,
                }
            )
        except Exception as exc:
            _log.debug("automation broadcast failed: %s", exc)


_engine: AutomationEngine | None = None
_engine_lock = threading.Lock()


def get_engine() -> AutomationEngine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = AutomationEngine()
    return _engine


def reset_engine() -> None:
    """Drop the process singleton and store cache (tests)."""
    global _engine
    with _engine_lock:
        _engine = None
        reset_cache()
