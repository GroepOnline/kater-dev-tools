from __future__ import annotations

import json
import re

from typer.testing import CliRunner

from kater.cli import app

runner = CliRunner()

ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def test_cli_help_starts() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Kater" in result.output or "Developer MCP gateway" in result.output


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
    assert "--apply requires --yes" in result.output


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
    assert "utrecht_status" in result.output
    assert "research_brief" not in result.output


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
    assert "not found" in result.output


def test_mcp_serve_profile_flag() -> None:
    result = runner.invoke(app, ["mcp", "serve", "--help"])

    assert result.exit_code == 0
    plain_output = strip_ansi(result.output)
    assert "profile" in plain_output
    assert "Profile to expose" in plain_output


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
    assert payload["profile"] == "ops"
    assert payload["total"] >= 1


def test_mcp_list_table() -> None:
    result = runner.invoke(app, ["mcp", "list", "--profile", "core"])
    assert result.exit_code == 0
    assert "github" in result.output
    assert "filesystem" in result.output


def test_profiles_includes_mcp_counts() -> None:
    result = runner.invoke(app, ["profiles", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["counts"]["core"] >= 1


def test_config_profile_no_hidden_servers() -> None:
    result = runner.invoke(app, ["config", "--profile", "core", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["profile"] == "core"
    assert "mcpServers" in payload
    assert "notion" not in payload["mcpServers"]


def test_validate_profile_unknown() -> None:
    result = runner.invoke(app, ["config", "--profile", "unknown", "--json"])
    assert result.exit_code == 2
    assert "Unknown profile" in result.output


def test_config_opencode() -> None:
    result = runner.invoke(app, ["config", "--profile", "core", "--format", "opencode"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "mcp" in payload or "mcpServers" in payload


def test_doctor_text() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Doctor" in result.output or "profiles" in result.output


def test_init_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    result = runner.invoke(app, ["init", "--yes"])
    assert result.exit_code == 0
    assert (tmp_path / ".kater" / "config.toml").exists()


def test_init_config_no_overwrite(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    config_dir = tmp_path / ".kater"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"
    config_file.write_text("existing")

    result = runner.invoke(app, ["init", "--yes"])
    assert result.exit_code == 0
    assert config_file.read_text() == "existing"


def test_env_example() -> None:
    result = runner.invoke(app, ["env", "example", "--profile", "core"])
    assert result.exit_code == 0
    assert "GITHUB_TOKEN" in result.output


def test_env_example_json() -> None:
    result = runner.invoke(app, ["env", "example", "--profile", "core", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "GITHUB_TOKEN" in payload["required"]
