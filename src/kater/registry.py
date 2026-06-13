from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from kater.doctor import run_doctor
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


def build_native_tools() -> list[NativeTool]:
    return [
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
    ]


def tools_for_profile(profile: str) -> list[NativeTool]:
    return [
        tool for tool in build_native_tools() if tool.profile == "core" or tool.profile == profile
    ]
