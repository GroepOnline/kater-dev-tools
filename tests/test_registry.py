from __future__ import annotations

from kater.registry import profile_list_tool, tools_for_profile


def test_registry_exposes_core_tools() -> None:
    tools = tools_for_profile("core")
    names = {tool.name for tool in tools}

    assert "kater_profiles" in names
    assert "kater_doctor" in names
    assert "kater_chains" in names


def test_registry_profile_gated_tools() -> None:
    core_tools = {t.name for t in tools_for_profile("core")}
    private_tools = {t.name for t in tools_for_profile("demo_private")}

    assert "demo_private_status" not in core_tools
    assert "demo_private_status" in private_tools


def test_registry_all_profiles_share_core() -> None:
    for profile in ["core", "ops", "research", "demo_private"]:
        names = {t.name for t in tools_for_profile(profile)}
        assert "kater_profiles" in names


def test_profile_list_tool_returns_profiles() -> None:
    payload = profile_list_tool()

    assert "core" in payload["profiles"]
    assert "demo_private" in payload["profiles"]


def test_unknown_profile_has_core_tools_only() -> None:
    names = {t.name for t in tools_for_profile("unknown")}
    assert "kater_profiles" in names
    assert "demo_private_status" not in names


def test_tools_for_profile_accepts_comma_separated_profiles() -> None:
    names = {t.name for t in tools_for_profile("core,ops")}
    assert "kater_profiles" in names
    assert "kater_doctor" in names
