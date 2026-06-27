from __future__ import annotations

from kater.adapters.external import (
    _resolve_env,
    _substitute_env_vars,
    render_profile_config,
    scan_adapters,
)


def test_scan_adapters_core_has_no_externals() -> None:
    inventory = scan_adapters({"core"})
    # core should only have kater (native)
    assert len(inventory.sources) == 0
    assert inventory.for_profile("core") == []


def test_scan_adapters_research(monkeypatch) -> None:
    monkeypatch.setenv("EXA_API_KEY", "test-key")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "test-key")

    inventory = scan_adapters({"research"})
    names = {a.source.name for a in inventory.sources}

    assert "exa" in names
    assert "firecrawl" in names
    assert "github" not in names


def test_scan_adapters_reports_missing_env(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)

    inventory = scan_adapters({"ops"})
    github = next((a for a in inventory.sources if a.source.name == "github"), None)

    assert github is not None
    assert github.configured is False
    assert "GITHUB_PERSONAL_ACCESS_TOKEN" in github.missing_env


def test_render_profile_config_core(monkeypatch) -> None:
    config = render_profile_config("core")
    servers = config.get("mcpServers", {})

    assert "kater" in servers
    assert servers["kater"]["type"] == "sse"


def test_render_profile_config_research(monkeypatch) -> None:
    monkeypatch.setenv("EXA_API_KEY", "test-key")

    config = render_profile_config("research")
    servers = config.get("mcpServers", {})

    assert "kater" in servers
    assert "exa" in servers
    assert servers["exa"]["type"] == "sse"
    assert "test-key" in servers["exa"]["env"]["EXA_API_KEY"]


def test_render_profile_config_configured_stdio(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "test-token")

    config = render_profile_config("ops")
    servers = config.get("mcpServers", {})

    assert "github" in servers
    assert servers["github"]["type"] == "stdio"
    assert servers["github"]["command"] == "npx"
    assert "kater" in servers


def test_render_profile_config_redacts_secrets_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "supersecret-token")

    leaky = render_profile_config("ops", include_secrets=True)
    safe = render_profile_config("ops", include_secrets=False)

    assert "supersecret-token" in str(leaky["mcpServers"]["github"]["env"])
    assert "supersecret-token" not in str(safe["mcpServers"]["github"]["env"])


def test_embedded_env_var_substitution(monkeypatch) -> None:
    monkeypatch.setenv("NOTION_API_KEY", "ntn_secret")
    headers = '{"Authorization":"Bearer ${NOTION_API_KEY}"}'

    assert _substitute_env_vars(headers, include_secrets=True) == (
        '{"Authorization":"Bearer ntn_secret"}'
    )
    # Placeholder preserved when secrets are disabled.
    assert _substitute_env_vars(headers, include_secrets=False) == headers
    # _resolve_env handles embedded (non-exact) ${VAR} values too.
    resolved = _resolve_env({"OPENAPI_MCP_HEADERS": headers}, include_secrets=True)
    assert resolved["OPENAPI_MCP_HEADERS"] == '{"Authorization":"Bearer ntn_secret"}'


def test_adapter_inventory_profile_gating(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "test-token")

    ops_inventory = scan_adapters({"ops"})
    research_inventory = scan_adapters({"research"})

    ops_names = {a.source.name for a in ops_inventory.sources}
    research_names = {a.source.name for a in research_inventory.sources}

    assert "github" in ops_names
    assert "github" not in research_names
