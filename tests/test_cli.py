from __future__ import annotations

import json
import re

from typer.testing import CliRunner

from kater.cli import app

runner = CliRunner()

ANSI_RE = re.compile(r"\[([0-9;]*[a-zA-Z])")
def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)



def test_cli_help_starts() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    output = strip_ansi(result.output)
    assert "Kater" in output or "Developer MCP gateway" in output


def test_doctor_json() -> None:
    result = runner.invoke(app, ["doctor", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["profiles"] == ["core"]


def test_doctor_json_with_apply(tmp_path) -> None:
    result = runner.invoke(
        app,
        ["doctor", "--profile", "research", "--fix-plan", "--apply", "--yes", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "apply_result" in payload
    assert payload["profiles"] == ["research"]


def test_apply_requires_yes() -> None:
    result = runner.invoke(app, ["doctor", "--apply"])

    assert result.exit_code == 2
    assert "--apply requires --yes" in strip_ansi(result.output)


def test_profiles_json() -> None:
    result = runner.invoke(app, ["profiles", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "core" in payload["profiles"]


def test_tools_json() -> None:
    result = runner.invoke(app, ["tools", "--profile", "core", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["profile"] == "core"
    names = {t["name"] for t in payload["tools"]}
    assert "kater_profiles" in names
    assert "kater_doctor" in names


def test_chains_json() -> None:
    result = runner.invoke(app, ["chains", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload["chains"]) > 0
    names = {c["name"] for c in payload["chains"]}
    assert "research_brief" in names


def test_chains_filtered_by_profile() -> None:
    result = runner.invoke(app, ["chains", "--profile", "utrecht"])

    assert result.exit_code == 0
    assert "utrecht_status" in strip_ansi(result.output)
    assert "research_brief" not in strip_ansi(result.output)


def test_chain_run_research_brief() -> None:
    result = runner.invoke(
        app, ["chain", "run", "research_brief", "--profile", "research", "--json"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["chain"] == "research_brief"
    assert len(payload["steps"]) > 0


def test_chain_run_unknown() -> None:
    result = runner.invoke(app, ["chain", "run", "nonexistent"])

    assert result.exit_code == 1
    assert "not found" in strip_ansi(result.output)


def test_mcp_serve_profile_flag() -> None:
    result = runner.invoke(app, ["mcp", "serve", "--help"])

    assert result.exit_code == 0
    assert "--profile" in strip_ansi(result.output)


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.output.strip()


def test_config_json() -> None:
    result = runner.invoke(app, ["config", "--profile", "core", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["profile"] == "core"
    assert "kater" in payload["mcpServers"]


def test_adapters_json() -> None:
    result = runner.invoke(app, ["adapters", "--profile", "ops", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["total"] > 0


def test_mcp_list_json() -> None:
    result = runner.invoke(app, ["mcp", "list", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["total"] > 10
    names = {s["name"] for s in payload["servers"]}
    assert "github" in names
    assert "cloudflare" in names


def test_mcp_list_filtered_by_profile() -> None:
    result = runner.invoke(app, ["mcp", "list", "--profile", "ops", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    names = {s["name"] for s in payload["servers"]}
    assert "github" in names
    assert "exa" not in names


def test_mcp_status_known() -> None:
    result = runner.invoke(app, ["mcp", "status", "github", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["name"] == "github"
    assert payload["transport"] == "stdio"


def test_mcp_status_unknown() -> None:
    result = runner.invoke(app, ["mcp", "status", "nonexistent"])
    assert result.exit_code == 1
    assert "unknown" in strip_ansi(result.output)


def test_init_creates_kater_dir(tmp_path) -> None:
    result = runner.invoke(app, ["init", "--profile", "ops", "--force", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload["created"]) > 0


def test_serve_help() -> None:
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "--api-port" in strip_ansi(result.output)
    assert "--mcp-port" in strip_ansi(result.output)


def test_enable_server() -> None:
    result = runner.invoke(app, ["enable", "github", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["enabled"] is True


def test_disable_server() -> None:
    result = runner.invoke(app, ["disable", "sentry", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["enabled"] is False


def test_toggle_server() -> None:
    result = runner.invoke(app, ["toggle", "exa", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "enabled" in payload


def test_enable_unknown() -> None:
    result = runner.invoke(app, ["enable", "nonexistent"])
    assert result.exit_code == 1


def test_deploy_list() -> None:
    result = runner.invoke(app, ["deploy", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    names = {f["name"] for f in payload["formats"]}
    assert "docker" in names
    assert "cloudflare" in names


def test_deploy_render() -> None:
    result = runner.invoke(app, ["deploy", "render", "docker", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["format"] == "docker-compose"


def test_deploy_render_cloudflare() -> None:
    result = runner.invoke(
        app, ["deploy", "render", "cloudflare", "--domain", "kater.test.com", "--json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["format"] == "cloudflare-tunnel"


def test_auth_status() -> None:
    result = runner.invoke(app, ["auth", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "mode" in payload


def test_auth_set_apikey() -> None:
    result = runner.invoke(app, ["auth", "set", "apikey", "--key", "test-key", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["mode"] == "apikey"
    assert "test-key" in payload["api_keys"]


def test_auth_set_none() -> None:
    result = runner.invoke(app, ["auth", "set", "none", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["mode"] == "none"


def test_settings_json() -> None:
    result = runner.invoke(app, ["settings", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["version"] == 2
    assert "auth" in payload
