from __future__ import annotations

import json

from kater.doctor import run_doctor


def test_doctor_passes_core_profile(monkeypatch, tmp_path) -> None:
    for var in (
        "LINEAR_API_KEY",
        "CLOUDFLARE_API_TOKEN",
        "GITHUB_PERSONAL_ACCESS_TOKEN",
        "GITLAB_PERSONAL_ACCESS_TOKEN",
    ):
        monkeypatch.delenv(var, raising=False)

    mcp_path = tmp_path / "mcp.json"
    mcp_path.write_text(json.dumps({"mcpServers": {"kater": {}}}), encoding="utf-8")

    report = run_doctor(profiles={"core"}, cursor_mcp_path=mcp_path)

    assert report.profiles == ["core"]
    assert [source["name"] for source in report.sources] == ["kater"]
    assert report.findings == []


def test_doctor_reports_context_bloat(tmp_path) -> None:
    mcp_path = tmp_path / "mcp.json"
    mcp_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "kater": {},
                    "github": {},
                    "linear": {},
                    "firecrawl": {},
                    "resend": {},
                }
            }
        ),
        encoding="utf-8",
    )

    report = run_doctor(profiles={"core"}, cursor_mcp_path=mcp_path)

    assert any(finding.code == "too_many_default_servers" for finding in report.findings)
    assert any(finding.code == "server_outside_profile" for finding in report.findings)


def test_fix_plan_includes_safe_actions(tmp_path) -> None:
    mcp_path = tmp_path / "mcp.json"
    mcp_path.write_text(
        json.dumps({"mcpServers": {"github": {}, "linear": {}, "firecrawl": {}, "resend": {}}}),
        encoding="utf-8",
    )

    report = run_doctor(profiles={"research"}, cursor_mcp_path=mcp_path, include_fix_plan=True)

    assert any(action.action == "render_cursor_snippet" for action in report.fix_actions)
    assert any(action.action == "render_env_example" for action in report.fix_actions)


def test_doctor_flags_public_without_auth(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_AUTH_MODE", "none")

    report = run_doctor(profiles={"core"})

    assert any(f.code == "public_without_auth" for f in report.findings)


def test_doctor_ok_for_public_oauth(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_AUTH_MODE", "oauth")

    report = run_doctor(profiles={"core"})

    assert not any(f.code == "public_without_auth" for f in report.findings)
    assert not any(f.code == "public_oauth_open_registration" for f in report.findings)
    assert any(f.code == "public_oauth_ready" for f in report.findings)


def test_doctor_flags_dynamic_registration_without_token(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_AUTH_MODE", "oauth")
    monkeypatch.setenv("KATER_ALLOW_DYNAMIC_REGISTRATION", "1")
    monkeypatch.delenv("KATER_REGISTRATION_TOKEN", raising=False)

    report = run_doctor(profiles={"core"})

    assert any(
        f.code == "public_oauth_registration_token_missing"
        and f.severity == "error"
        for f in report.findings
    )

import pathlib
from pathlib import Path
from kater.doctor import resolve_cursor_mcp

def test_resolve_cursor_mcp_provided_path_exists(tmp_path) -> None:
    mcp_path = tmp_path / "mcp.json"
    mcp_path.write_text("{}")
    assert resolve_cursor_mcp(mcp_path) == mcp_path


def test_resolve_cursor_mcp_provided_path_missing(tmp_path) -> None:
    mcp_path = tmp_path / "mcp.json"
    assert resolve_cursor_mcp(mcp_path) is None


def test_resolve_cursor_mcp_cwd_candidate(monkeypatch, tmp_path) -> None:
    mock_cwd = tmp_path / "cwd"
    mock_cwd.mkdir()
    monkeypatch.chdir(mock_cwd)

    cwd_mcp = mock_cwd / ".cursor" / "mcp.json"
    cwd_mcp.parent.mkdir()
    cwd_mcp.write_text("{}")

    assert resolve_cursor_mcp(None) == cwd_mcp


def test_resolve_cursor_mcp_home_candidate(monkeypatch, tmp_path) -> None:
    mock_cwd = tmp_path / "cwd"
    mock_cwd.mkdir()
    monkeypatch.chdir(mock_cwd)

    mock_home = tmp_path / "home"
    mock_home.mkdir()
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: mock_home))

    home_mcp = mock_home / ".cursor" / "mcp.json"
    home_mcp.parent.mkdir()
    home_mcp.write_text("{}")

    assert resolve_cursor_mcp(None) == home_mcp


def test_resolve_cursor_mcp_none_found(monkeypatch, tmp_path) -> None:
    mock_cwd = tmp_path / "cwd"
    mock_cwd.mkdir()
    monkeypatch.chdir(mock_cwd)

    mock_home = tmp_path / "home"
    mock_home.mkdir()
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: mock_home))

    assert resolve_cursor_mcp(None) is None
