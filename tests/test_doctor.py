from __future__ import annotations

import json

from kater.doctor import parse_profiles, run_doctor
from kater.profiles import DEFAULT_PROFILE


def test_parse_profiles():
    # Null or empty inputs
    assert parse_profiles(None) == {DEFAULT_PROFILE}
    assert parse_profiles("") == {DEFAULT_PROFILE}

    # Whitespace/empty tokens
    assert parse_profiles("   ") == {DEFAULT_PROFILE}
    assert parse_profiles(",,") == {DEFAULT_PROFILE}
    assert parse_profiles(" , ") == {DEFAULT_PROFILE}

    # Single item
    assert parse_profiles("core") == {"core"}
    assert parse_profiles("  core  ") == {"core"}

    # Multiple items
    assert parse_profiles("core,research") == {"core", "research"}
    assert parse_profiles(" core , research ") == {"core", "research"}

    # Mixed with empty tokens
    assert parse_profiles("core,,research,") == {"core", "research"}
    assert parse_profiles("core,  , research") == {"core", "research"}


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
