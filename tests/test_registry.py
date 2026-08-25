from __future__ import annotations

from kater.registry import (
    adapter_inventory_tool,
    build_native_tools,
    chains_list_tool,
    config_render_tool,
    profile_list_tool,
    tools_for_profile,
)


def test_profile_list_tool_returns_profiles() -> None:
    result = profile_list_tool()
    assert "profiles" in result
    profiles = result["profiles"]
    assert "core" in profiles
    assert "ops" in profiles


def test_chains_list_tool_returns_chains_for_core() -> None:
    result = chains_list_tool("core")
    assert "chains" in result
    assert isinstance(result["chains"], list)


def test_adapter_inventory_tool_returns_adapters_for_core() -> None:
    result = adapter_inventory_tool("core")
    assert result["profile"] == "core"
    assert "adapters" in result
    assert "connectors" in result


def test_adapter_inventory_tool_exposes_connector_help_for_agents() -> None:
    result = adapter_inventory_tool("core")
    # A healthy catalog reports no error and ships machine-readable guidance so
    # agents can discover how to invoke/manage connectors behind the 17 tools.
    assert result["connectors_error"] is None
    help_block = result["connector_help"]
    assert "chains" in help_block["invoke_via"]
    assert help_block["manage"]["cli"].startswith("kater connector")
    assert "policy_blocked" in help_block["health_states"]


def test_adapter_inventory_tool_surfaces_connector_error_redacted(monkeypatch) -> None:
    def _boom() -> int:
        raise RuntimeError("catalog exploded Bearer super-secret-token")

    monkeypatch.setattr("kater.connectors.seed.seed_builtin_connectors", _boom)
    result = adapter_inventory_tool("core")
    # Fail closed but visible, and never leak a secret in the surfaced error.
    assert result["connectors"] == []
    assert result["connectors_error"]
    assert "super-secret-token" not in result["connectors_error"]


def test_native_gateway_surface_is_seventeen_without_extensions(monkeypatch) -> None:
    monkeypatch.delenv("KATER_EXTENSIONS_MODULE", raising=False)
    monkeypatch.delenv("KATER_PUBLIC", raising=False)
    names = [tool.name for tool in build_native_tools()]
    assert len(names) == 17
    assert "kater_github" not in names
    assert "kater_connectors" not in names
    assert names.count("kater_profiles") == 1


def test_config_render_tool_returns_mcp_config_without_secrets() -> None:
    result = config_render_tool("core")
    assert "profile" in result
    assert result["profile"] == "core"
    assert "mcpServers" in result
    # kater native entry is always present
    assert "kater" in result["mcpServers"]


def test_build_native_tools_includes_core_tools() -> None:
    tools = build_native_tools()
    names = {t.name for t in tools}
    assert "kater_profiles" in names
    assert "kater_doctor" in names
    assert "kater_chains" in names
    assert "kater_adapters" in names
    assert "kater_config" in names
    assert "kater_pr_list" in names
    assert "kater_pr_status" in names
    assert "kater_pr_gate" in names
    assert "kater_pr_policy" in names
    assert "kater_pr_audit" in names
    assert "kater_pr_merge" in names


def test_build_native_tools_loads_extension_tools(monkeypatch) -> None:
    """When KATER_EXTENSIONS_MODULE exports NATIVE_TOOLS, they are merged in."""
    monkeypatch.setenv("KATER_EXTENSIONS_MODULE", "tests.fixtures.private_extension")
    tools = build_native_tools()
    names = {t.name for t in tools}
    # Core tools still present
    assert "kater_profiles" in names
    # Extension tools from the private_extension fixture are included
    # (the fixture exports one extra native tool)
    assert len(tools) > 11  # more than the 11 builtins


def test_tools_for_profile_filters_by_profile() -> None:
    """tools_for_profile only returns tools matching the requested profile."""
    core_tools = tools_for_profile("core")
    core_names = {t.name for t in core_tools}
    # All core-profile tools should be present
    assert "kater_profiles" in core_names
    assert "kater_doctor" in core_names

    # Non-existent profile should still get core tools
    unknown_tools = tools_for_profile("nonexistent-profile")
    unknown_names = {t.name for t in unknown_tools}
    assert "kater_profiles" in unknown_names
