from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from kater.adapters.external import render_profile_config, scan_adapters
from kater.chains import list_chains
from kater.doctor import parse_profiles, run_doctor
from kater.pr_control import pr_gate_tool, pr_list_tool, pr_status_tool
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


def adapter_inventory_tool(profile: str = "core") -> dict[str, Any]:
    inventory = scan_adapters({profile})
    return {
        "profile": profile,
        "adapters": [
            {
                "name": a.source.name,
                "transport": a.source.transport,
                "configured": a.configured,
                "missing_env": a.missing_env,
                "risk": a.source.risk,
            }
            for a in inventory.sources
        ],
    }


def config_render_tool(profile: str = "core") -> dict[str, Any]:
    # Exposed as an MCP tool to connected agents: redact secrets, emit
    # ${VAR} placeholders instead of the server's live environment values.
    return render_profile_config(profile, include_secrets=False)


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
            description="Scan which external MCP adapters are configured.",
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
    ]
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
