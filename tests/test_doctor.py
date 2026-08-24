from __future__ import annotations

import json

from kater.doctor import _connector_health_check, is_gateway_server, run_doctor


def test_is_gateway_server_matches_hostname_not_path() -> None:
    assert is_gateway_server(
        "kater-sse",
        {"type": "sse", "url": "http://127.0.0.1:9090/sse"},
    )
    assert is_gateway_server(
        "kater-localhost",
        {"type": "sse", "url": "http://localhost:9090/sse"},
    )
    # Loopback satellite on a different port is not the gateway.
    assert not is_gateway_server(
        "direct-satellite",
        {"type": "sse", "url": "http://127.0.0.1:8080/sse"},
    )
    # Hostname-only match: "localhost" in the path must not count.
    assert not is_gateway_server(
        "remote-with-localhost-path",
        {"type": "sse", "url": "https://example.com/path/localhost/sse"},
    )


def test_connector_doctor_does_not_claim_unprobed_http_is_healthy(monkeypatch) -> None:
    from kater.connectors.models import (
        AuthBindingKind,
        AuthBindingRef,
        ConnectorRecord,
        ConnectorStatus,
        ConnectorTransport,
        ConnectorType,
        PermissionLevel,
    )

    record = ConnectorRecord(
        id="remote.api",
        display_name="Remote API",
        type=ConnectorType.API,
        version="1.0.0",
        transport=ConnectorTransport(kind="http", endpoint="https://example.invalid"),
        auth_binding=AuthBindingRef(kind=AuthBindingKind.NONE),
        profiles=frozenset({"ops"}),
        permissions={"ops": PermissionLevel.READ},
        status=ConnectorStatus.ENABLED,
        origin="seed",
    )
    monkeypatch.setattr("kater.connectors.seed.seed_builtin_connectors", lambda: None)
    monkeypatch.setattr("kater.connectors.store.list_connectors", lambda: [record])

    findings = _connector_health_check({"ops"})
    assert [finding.code for finding in findings] == ["connector_configured"]
    assert "not probed" in findings[0].message


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
    # Informational browser-lane probe is allowed; no warnings/errors on core.
    assert all(f.severity == "info" for f in report.findings)
    assert all(f.code.startswith("browser_lane_") for f in report.findings)


def test_doctor_ops_skips_high_risk_missing_env_warnings(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    for var in (
        "GITHUB_PERSONAL_ACCESS_TOKEN",
        "GITLAB_PERSONAL_ACCESS_TOKEN",
        "LINEAR_API_KEY",
        "SENTRY_AUTH_TOKEN",
        "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_ACCOUNT_ID",
        "SLACK_BOT_TOKEN",
        "NOTION_TOKEN",
    ):
        monkeypatch.delenv(var, raising=False)
    mcp_path = tmp_path / "mcp.json"
    mcp_path.write_text(json.dumps({"mcpServers": {"kater": {}}}), encoding="utf-8")

    report = run_doctor(profiles={"ops"}, cursor_mcp_path=mcp_path)
    missing_sources = {f.source for f in report.findings if f.code == "missing_env"}
    assert "github" not in missing_sources
    assert "gitlab" not in missing_sources
    assert "slack" not in missing_sources
    assert "notion" not in missing_sources
    assert any(f.code in {"adapter_ready", "adapter_not_configured"} for f in report.findings)


def test_doctor_ops_adapter_ready_when_linear_and_sentry_configured(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LINEAR_API_KEY", "lin-test")
    monkeypatch.setenv("SENTRY_AUTH_TOKEN", "sentry-test")
    mcp_path = tmp_path / "mcp.json"
    mcp_path.write_text(json.dumps({"mcpServers": {"kater": {}}}), encoding="utf-8")

    report = run_doctor(profiles={"ops"}, cursor_mcp_path=mcp_path)
    ready = {f.source for f in report.findings if f.code == "adapter_ready"}
    assert "linear" in ready
    assert "sentry" in ready
    assert not any(
        f.code == "missing_env" and f.source in {"linear", "sentry"} for f in report.findings
    )


def test_browser_lane_unsupported_when_not_expected(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KATER_BROWSER_ENABLE", raising=False)
    monkeypatch.delenv("KATER_BROWSER_CDP_URL", raising=False)
    monkeypatch.delenv("KATER_BROWSER_STEEL_URL", raising=False)
    monkeypatch.setattr("kater.browser.providers.probe_providers", lambda: [])
    mcp_path = tmp_path / "mcp.json"
    mcp_path.write_text(json.dumps({"mcpServers": {"kater": {}}}), encoding="utf-8")

    report = run_doctor(profiles={"core"}, cursor_mcp_path=mcp_path)
    codes = {f.code for f in report.findings if f.code.startswith("browser_lane_")}
    assert codes == {"browser_lane_unsupported"}


def test_browser_lane_unavailable_when_expected(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KATER_BROWSER_ENABLE", "1")
    monkeypatch.setattr("kater.browser.providers.probe_providers", lambda: [])
    mcp_path = tmp_path / "mcp.json"
    mcp_path.write_text(json.dumps({"mcpServers": {"kater": {}}}), encoding="utf-8")

    report = run_doctor(profiles={"core"}, cursor_mcp_path=mcp_path)
    codes = {f.code for f in report.findings if f.code.startswith("browser_lane_")}
    assert codes == {"browser_lane_unavailable"}


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


def test_doctor_allows_gateway_with_satellite_servers(tmp_path) -> None:
    mcp_path = tmp_path / "mcp.json"
    mcp_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "kater": {"type": "sse", "url": "http://127.0.0.1:9090/sse"},
                    "team-vault": {"command": "node"},
                    "team-brain": {"command": "ssh"},
                    "team-mail": {"command": "npx"},
                    "team-storage": {"command": "ssh"},
                }
            }
        ),
        encoding="utf-8",
    )

    report = run_doctor(
        profiles={"code", "ops"},
        cursor_mcp_path=mcp_path,
    )

    assert not any(finding.code == "too_many_default_servers" for finding in report.findings)
    assert not any(finding.code == "server_outside_profile" for finding in report.findings)
    assert {f.source for f in report.findings if f.code == "satellite_server"} == {
        "team-brain",
        "team-mail",
        "team-storage",
        "team-vault",
    }


def test_doctor_recognizes_gateway_by_url_match(tmp_path) -> None:
    mcp_path = tmp_path / "mcp.json"
    mcp_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "kater-clone": {"type": "sse", "url": "http://127.0.0.1:9090/sse"},
                    "custom-local": {"command": "node"},
                }
            }
        ),
        encoding="utf-8",
    )

    report = run_doctor(profiles={"core"}, cursor_mcp_path=mcp_path)

    assert not any(finding.code == "server_outside_profile" for finding in report.findings)
    assert any(
        finding.code == "satellite_server" and finding.source == "custom-local"
        for finding in report.findings
    )


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
    assert not any(f.code == "public_connect_secret_sink_disabled" for f in report.findings)
    assert any(f.code == "public_connect_base_url_missing" for f in report.findings)


def test_doctor_flags_dynamic_registration_without_token(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_AUTH_MODE", "oauth")
    monkeypatch.setenv("KATER_ALLOW_DYNAMIC_REGISTRATION", "1")
    monkeypatch.delenv("KATER_REGISTRATION_TOKEN", raising=False)

    report = run_doctor(profiles={"core"})

    assert any(
        f.code == "public_oauth_registration_token_missing" and f.severity == "error"
        for f in report.findings
    )
