"""Data model for scheduled automations."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


def new_automation_id() -> str:
    return f"auto_{uuid.uuid4().hex}"


@dataclass
class Automation:
    id: str
    name: str
    kind: str
    enabled: bool = True
    schedule_seconds: int = 0
    config: dict[str, Any] = field(default_factory=dict)
    last_run_at: float | None = None
    last_status: str | None = None
    last_error: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "kind": self.kind,
            "schedule_seconds": self.schedule_seconds,
            "config": dict(self.config),
            "last_run_at": self.last_run_at,
            "last_status": self.last_status,
            "last_error": self.last_error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


RUN_STATUSES = frozenset({"ok", "error", "skipped", "unknown"})
RUN_TRIGGERS = frozenset({"schedule", "manual"})


@dataclass(frozen=True)
class AutomationRun:
    """One persisted run; ``unknown`` with no ``finished_at`` means it never finished."""

    id: int
    automation_id: str
    started_at: float
    finished_at: float | None
    status: str
    error: str | None
    trigger: str

    def to_dict(self) -> dict[str, Any]:
        duration_ms = (
            round((self.finished_at - self.started_at) * 1000.0, 2)
            if self.finished_at is not None
            else None
        )
        return {
            "id": self.id,
            "automation_id": self.automation_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": duration_ms,
            "status": self.status,
            "error": self.error,
            "trigger": self.trigger,
        }


@dataclass(frozen=True)
class AutomationRunResult:
    id: str
    kind: str
    status: str
    error: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    ran_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "error": self.error,
            "detail": dict(self.detail),
            "duration_ms": round(self.duration_ms, 2),
            "ran_at": self.ran_at,
        }
