"""GitHub toolkit: native PR/gate actions routed through the generic executor."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kater.connectors.errors import ConnectorCapabilityError, ConnectorPolicyError
from kater.connectors.models import ConnectorCapability

GITHUB_PR_ACTIONS: tuple[ConnectorCapability, ...] = (
    ConnectorCapability(
        id="github.pr.list",
        description="List pull requests with merge-readiness summary.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "state": {"type": "string", "default": "open"},
                "limit": {"type": "integer", "default": 30},
                "repo": {"type": "string", "default": ""},
            },
        },
    ),
    ConnectorCapability(
        id="github.pr.status",
        description="Show status and merge-readiness gate for one PR.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["number"],
            "properties": {
                "number": {"type": "integer"},
                "repo": {"type": "string", "default": ""},
            },
        },
    ),
    ConnectorCapability(
        id="github.pr.gate",
        description="Evaluate the deterministic merge gate (PASS/WARN/BLOCK).",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["number"],
            "properties": {
                "number": {"type": "integer"},
                "expected_head_sha": {"type": "string", "default": ""},
                "repo": {"type": "string", "default": ""},
            },
        },
    ),
    ConnectorCapability(
        id="github.pr.policy",
        description="Show the resolved merge-gate policy.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {"policy_path": {"type": "string", "default": ""}},
        },
    ),
    ConnectorCapability(
        id="github.pr.audit",
        description="Show the local merge-gate audit trail.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "pr_number": {"type": "integer", "default": 0},
                "limit": {"type": "integer", "default": 100},
            },
        },
    ),
    ConnectorCapability(
        id="github.pr.merge",
        description="Gate-then-merge a PR. Dangerous write: nonempty expected_head_sha.",
        mutation=True,
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["number"],
            "properties": {
                "number": {"type": "integer"},
                "expected_head_sha": {"type": "string"},
                "actor": {"type": "string", "default": ""},
                "repo": {"type": "string", "default": ""},
            },
        },
    ),
)


def _int(arguments: dict[str, Any], key: str, default: int = 0) -> int:
    value = arguments.get(key, default)
    if value is None or value == "":
        return default
    return int(value)


def _str(arguments: dict[str, Any], key: str, default: str = "") -> str:
    value = arguments.get(key, default)
    return default if value is None else str(value)


def _list(arguments: dict[str, Any]) -> dict[str, Any]:
    from kater.pr_control import pr_list_tool

    return pr_list_tool(
        state=_str(arguments, "state", "open"),
        limit=_int(arguments, "limit", 30),
        repo=_str(arguments, "repo"),
    )


def _status(arguments: dict[str, Any]) -> dict[str, Any]:
    from kater.pr_control import pr_status_tool

    return pr_status_tool(number=_int(arguments, "number"), repo=_str(arguments, "repo"))


def _gate(arguments: dict[str, Any]) -> dict[str, Any]:
    from kater.pr_control import pr_gate_tool

    return pr_gate_tool(
        number=_int(arguments, "number"),
        expected_head_sha=_str(arguments, "expected_head_sha"),
        repo=_str(arguments, "repo"),
    )


def _policy(arguments: dict[str, Any]) -> dict[str, Any]:
    from kater.pr_control import pr_policy_tool

    return pr_policy_tool(policy_path=_str(arguments, "policy_path"))


def _audit(arguments: dict[str, Any]) -> dict[str, Any]:
    from kater.pr_control import pr_audit_tool

    return pr_audit_tool(
        pr_number=_int(arguments, "pr_number"),
        limit=_int(arguments, "limit", 100),
    )


def _merge(arguments: dict[str, Any]) -> dict[str, Any]:
    from kater.pr_control import pr_merge_tool

    sha = _str(arguments, "expected_head_sha").strip()
    if not sha:
        raise ConnectorPolicyError(
            "dangerous write requires a nonempty expected_head_sha",
            connector_id="github",
            code="policy_blocked",
        )
    return pr_merge_tool(
        number=_int(arguments, "number"),
        expected_head_sha=sha,
        actor=_str(arguments, "actor"),
        repo=_str(arguments, "repo"),
    )


HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "github.pr.list": _list,
    "github.pr.status": _status,
    "github.pr.gate": _gate,
    "github.pr.policy": _policy,
    "github.pr.audit": _audit,
    "github.pr.merge": _merge,
}


def invoke_github_action(action: str, arguments: dict[str, Any]) -> dict[str, Any]:
    handler = HANDLERS.get(action)
    if handler is None:
        raise ConnectorCapabilityError(
            f"github action {action!r} is not a native toolkit action",
            connector_id="github",
        )
    return handler(dict(arguments or {}))
