"""Native toolkit action handlers (GitHub first; more providers follow the same path)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from kater.connectors.errors import ConnectorCapabilityError
from kater.toolkits import github as github_toolkit

ActionHandler = Callable[[dict[str, Any]], dict[str, Any]]

_HANDLERS: dict[str, ActionHandler] = dict(github_toolkit.HANDLERS)


@dataclass(frozen=True, slots=True)
class ToolkitManifest:
    """Agent-facing toolkit: integrations plus the actions execute can dispatch."""

    id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    integrations: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "integrations": list(self.integrations),
            "actions": list(self.actions),
        }


GITHUB_TOOLKIT = ToolkitManifest(
    id="github",
    name="GitHub",
    description="GitHub PR, issue, and repository operations.",
    integrations=("github",),
    actions=tuple(item.id for item in github_toolkit.GITHUB_PR_ACTIONS),
)


def toolkit_manifests() -> tuple[ToolkitManifest, ...]:
    return (GITHUB_TOOLKIT,)


def native_action_ids() -> frozenset[str]:
    return frozenset(_HANDLERS)


def native_action_owner(action: str) -> str | None:
    for toolkit in toolkit_manifests():
        if action in toolkit.actions:
            if toolkit.integrations:
                return toolkit.integrations[0]
            return toolkit.id
    return None


def invoke_native_action(action: str, arguments: dict[str, Any]) -> dict[str, Any]:
    handler = _HANDLERS.get(action)
    if handler is None:
        raise ConnectorCapabilityError(f"native action {action!r} is not registered")
    return handler(dict(arguments or {}))
