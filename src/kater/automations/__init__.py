"""Eager automations engine — scheduled doctor, reap, prune, and nudges."""

from __future__ import annotations

from kater.automations.engine import (
    DEFAULT_AUTOMATIONS,
    AutomationEngine,
    get_engine,
    reset_engine,
)
from kater.automations.models import Automation, AutomationRunResult, new_automation_id
from kater.automations.store import AutomationStore, reset_cache

__all__ = [
    "DEFAULT_AUTOMATIONS",
    "Automation",
    "AutomationEngine",
    "AutomationRunResult",
    "AutomationStore",
    "get_engine",
    "new_automation_id",
    "reset_cache",
    "reset_engine",
]
