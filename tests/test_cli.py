from __future__ import annotations

import json

from typer.testing import CliRunner

from kater.cli import app

runner = CliRunner()


def test_cli_help_starts() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Kater" in result.output or "Developer MCP gateway" in result.output


def test_doctor_json() -> None:
    result = runner.invoke(app, ["doctor", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["profiles"] == ["core"]


def test_apply_requires_yes() -> None:
    result = runner.invoke(app, ["doctor", "--apply"])

    assert result.exit_code == 2
    assert "--apply requires --yes" in result.output


def test_profiles_json() -> None:
    result = runner.invoke(app, ["profiles", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "core" in payload["profiles"]
