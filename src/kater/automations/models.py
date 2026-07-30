"""Data model for scheduled automations."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


def new_automation_id() -> str:
    """Generate a unique identifier for an automation.

    Returns:
        str: An identifier prefixed with ``auto_``.
    """
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
        """
        Serialize the automation's metadata, configuration, scheduling, and execution history.

        Returns:
            dict[str, Any]: A dictionary containing the automation fields, with a copied
                configuration mapping.
        """
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
        """
        Serialize the automation run result as a dictionary.

        Returns:
            dict[str, Any]: A dictionary containing the run identifier, kind, status, error, copied
                detail, rounded duration, and timestamp.
        """
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "error": self.error,
            "detail": dict(self.detail),
            "duration_ms": round(self.duration_ms, 2),
            "ran_at": self.ran_at,
        }
