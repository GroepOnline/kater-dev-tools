from __future__ import annotations

import json

from kater.doctor import run_doctor


def test_doctor_passes_core_profile() -> None:
    report = run_doctor(profiles={"core"})

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
