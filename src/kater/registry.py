from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from kater.adapters.external import render_profile_config, scan_adapters
from kater.browser.tools import (
    BROWSER_TOOL_SPECS,
    browser_act_tool,
    browser_close_tool,
    browser_open_tool,
    browser_providers_tool,
    browser_screenshot_tool,
    browser_sessions_tool,
)
from kater.chains import list_chains
from kater.doctor import parse_profiles, run_doctor
from kater.pr_control import (
    pr_audit_tool,
    pr_gate_tool,
    pr_list_tool,
    pr_merge_tool,
    pr_policy_tool,
    pr_status_tool,
)
from kater.profiles import list_profiles

ToolHandler = Callable[..., dict[str, Any]]


class NativeTool(BaseModel):
    name: str
    description: str
    profile: str
    risk: str
    handler: ToolHandler

    model_config = {"arbitrary_types_allowed": True}


def profile_list_tool() -> dict[str, Any]:
    return {"profiles": list_profiles()}


def doctor_tool(profile: str = "core") -> dict[str, Any]:
    report = run_doctor(profiles={profile})
    return report.model_dump(mode="json")


def chains_list_tool(profile: str = "core") -> dict[str, Any]:
    chains = list_chains(profile)
    return {"chains": [chain.model_dump(mode="json") for chain in chains]}


# Machine-readable guidance so agents can discover the connector control plane
# without a new native tool. Connectors stay behind the 17 kater_* tools: agents
# invoke a capability through chains, and operators manage the catalog via the
# `kater connector` CLI or the admin-gated /api/connectors routes.
_CONNECTOR_HELP: dict[str, Any] = {
    "summary": (
        "Connectors are vendor integrations behind the 17 native kater_* tools; "
        "they are never extra native tools."
    ),
    "invoke_via": "chains (kater_chains) — a chain step names a connector capability id",
    "capability_id_format": "{connector_id}.{area}.{action} (e.g. github.pull_requests.read)",
    "manage": {
        "cli": "kater connector list|validate|enable|disable|invoke",
        "http": "GET /api/connectors ; POST /api/connectors/{id}/{action} (admin-gated)",
    },
    "health_states": [
        "healthy",
        "degraded",
        "unavailable",
        "disabled",
        "unsupported",
        "auth_missing",
        "policy_blocked",
    ],
    "notes": "Health is recomputed live, never stored. Disabled/out-of-scope is not broken.",
}


def adapter_inventory_tool(profile: str = "core") -> dict[str, Any]:
    inventory = scan_adapters({profile})
    connectors: list[dict[str, Any]] = []
    connectors_error: str | None = None
    try:
        from kater.connectors.registry import inventory as connector_inventory
        from kater.connectors.seed import seed_builtin_connectors

        seed_builtin_connectors()
        connectors = [view.as_dict() for view in connector_inventory(profile)]
    except Exception as exc:
        # Fail closed but visible: an agent should see *that* the catalog is
        # unavailable, not a silently empty list. Redact so no secret leaks.
        from kater.connectors.auth import redact_text

        connectors = []
        connectors_error = redact_text(str(exc)) or "connector catalog unavailable"
    return {
        "profile": profile,
        "adapters": [
            {
                "name": a.source.name,
                "transport": getattr(a.source.transport, "value", a.source.transport),
                "configured": a.configured,
                "missing_env": a.missing_env,
                "risk": getattr(a.source.risk, "value", a.source.risk),
            }
            for a in inventory.sources
        ],
        "connectors": connectors,
        "connectors_error": connectors_error,
        "connector_help": _CONNECTOR_HELP,
    }


def config_render_tool(profile: str = "core") -> dict[str, Any]:
    # Exposed as an MCP tool to connected agents: redact secrets, emit
    # ${VAR} placeholders instead of the server's live environment values.
    return render_profile_config(profile, include_secrets=False)


# Typed FastMCP wrappers — handlers in kater.browser.tools use **kwargs, which
# FastMCP cannot introspect into a useful input schema. These keep real signatures.


def kater_browser_open(
    label: str | None = None,
    profile: str = "core",
    width: int = 1280,
    height: int = 800,
) -> dict[str, Any]:
    return browser_open_tool(label=label, profile=profile, width=width, height=height)


def kater_browser_act(
    session_id: str,
    kind: str,
    url: str | None = None,
    selector: str | None = None,
    text: str | None = None,
    key: str | None = None,
    value: str | None = None,
    expression: str | None = None,
    delta_y: float | None = None,
    timeout_ms: int | None = None,
    full_page: bool = False,
) -> dict[str, Any]:
    return browser_act_tool(
        session_id=session_id,
        kind=kind,
        url=url,
        selector=selector,
        text=text,
        key=key,
        value=value,
        expression=expression,
        delta_y=delta_y,
        timeout_ms=timeout_ms,
        full_page=full_page,
    )


def kater_browser_screenshot(
    session_id: str,
    full_page: bool = False,
) -> dict[str, Any]:
    return browser_screenshot_tool(session_id=session_id, full_page=full_page)


def kater_browser_sessions(live_only: bool = False) -> dict[str, Any]:
    return browser_sessions_tool(live_only=live_only)


def kater_browser_close(
    session_id: str | None = None,
    all: bool = False,
) -> dict[str, Any]:
    return browser_close_tool(session_id=session_id, all=all)


def kater_browser_providers() -> dict[str, Any]:
    return browser_providers_tool()


_BROWSER_HANDLERS: dict[str, ToolHandler] = {
    "kater_browser_open": kater_browser_open,
    "kater_browser_act": kater_browser_act,
    "kater_browser_screenshot": kater_browser_screenshot,
    "kater_browser_sessions": kater_browser_sessions,
    "kater_browser_close": kater_browser_close,
    "kater_browser_providers": kater_browser_providers,
}


_ENV_BROWSER_ENABLE = "KATER_BROWSER_ENABLE"


def _browser_lane_enabled() -> bool:
    """Whether the native browser tools should be surfaced.

    Browser tools ship in ``core`` so they are always available on trusted local
    deployments. On a public deployment (``KATER_PUBLIC``) they must NOT be
    auto-exposed: there they surface only when explicitly enabled via
    ``KATER_BROWSER_ENABLE`` (1/true/yes/on).
    """
    from kater.profiles import is_public_mode

    if not is_public_mode():
        return True
    return os.environ.get(_ENV_BROWSER_ENABLE, "").strip().lower() in {"1", "true", "yes", "on"}


def _browser_native_tools() -> list[NativeTool]:
    if not _browser_lane_enabled():
        return []
    return [
        NativeTool(
            name=spec["name"],
            description=spec["description"],
            profile="core",
            risk=spec["risk"],
            handler=_BROWSER_HANDLERS[spec["name"]],
        )
        for spec in BROWSER_TOOL_SPECS
    ]


def _extension_native_tools() -> list[NativeTool]:
    from kater.extensions import extension_attr

    return list(extension_attr("NATIVE_TOOLS", []))


def build_native_tools() -> list[NativeTool]:
    tools = [
        NativeTool(
            name="kater_profiles",
            description="List available Kater tool profiles.",
            profile="core",
            risk="low",
            handler=profile_list_tool,
        ),
        NativeTool(
            name="kater_doctor",
            description="Run Kater context and MCP configuration diagnostics.",
            profile="core",
            risk="low",
            handler=doctor_tool,
        ),
        NativeTool(
            name="kater_chains",
            description="List available tool chains for a profile.",
            profile="core",
            risk="low",
            handler=chains_list_tool,
        ),
        NativeTool(
            name="kater_adapters",
            description=(
                "Inventory external MCP adapters and the connector catalog "
                "(health, capabilities, and how to invoke/manage connectors)."
            ),
            profile="core",
            risk="low",
            handler=adapter_inventory_tool,
        ),
        NativeTool(
            name="kater_config",
            description="Render the full MCP config for a profile.",
            profile="core",
            risk="low",
            handler=config_render_tool,
        ),
        NativeTool(
            name="kater_pr_list",
            description="List GitHub pull requests with merge-readiness summary.",
            profile="core",
            risk="low",
            handler=pr_list_tool,
        ),
        NativeTool(
            name="kater_pr_status",
            description="Show status and merge-readiness gate for one PR.",
            profile="core",
            risk="low",
            handler=pr_status_tool,
        ),
        NativeTool(
            name="kater_pr_gate",
            description="Evaluate the deterministic merge gate (PASS/WARN/BLOCK) for a PR.",
            profile="core",
            risk="low",
            handler=pr_gate_tool,
        ),
        NativeTool(
            name="kater_pr_policy",
            description="Show the resolved merge-gate policy (thresholds, blocking rules).",
            profile="core",
            risk="low",
            handler=pr_policy_tool,
        ),
        NativeTool(
            name="kater_pr_audit",
            description="Show the local merge-gate audit trail (optionally for one PR).",
            profile="core",
            risk="low",
            handler=pr_audit_tool,
        ),
        NativeTool(
            name="kater_pr_merge",
            description="Gate-then-merge a PR (squash). Requires PASS and expected head SHA.",
            profile="core",
            risk="high",
            handler=pr_merge_tool,
        ),
    ]
    tools.extend(_browser_native_tools())
    tools.extend(_extension_native_tools())
    return tools


def tools_for_profile(profile: str) -> list[NativeTool]:
    from kater.profiles import is_private_profile, is_public_mode

    profile_names = parse_profiles(profile)
    public = is_public_mode()
    return [
        tool
        for tool in build_native_tools()
        if (tool.profile == "core" or tool.profile in profile_names)
        and not (public and is_private_profile(tool.profile))
    ]
