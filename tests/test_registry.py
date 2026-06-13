from __future__ import annotations

from kater.registry import profile_list_tool, tools_for_profile


def test_registry_exposes_core_tools() -> None:
    tools = tools_for_profile("core")
    names = {tool.name for tool in tools}

    assert "kater_profiles" in names
    assert "kater_doctor" in names


def test_profile_list_tool_returns_profiles() -> None:
    payload = profile_list_tool()

    assert "core" in payload["profiles"]
