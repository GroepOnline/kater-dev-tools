"""Regression coverage for the browser-lane / computer-connector documentation
and ``.env.example`` additions in this PR.

Mirrors the plain-text-assertion convention established in
``test_ci_workflow_changes.py``: these are docs/config files that are only
ever read by humans and tooling, never executed, so we assert on their text
content rather than importing them.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_EXAMPLE = ROOT / ".env.example"
DOC_BROWSER = ROOT / "docs" / "browser.md"
DOC_DEPLOY_LOCAL = ROOT / "docs" / "deploy-local.md"
DOC_DEPLOY_SERVER = ROOT / "docs" / "deploy-server.md"
DOC_CATALOG_CONNECT = ROOT / "docs" / "ops" / "catalog-connect.md"
DOC_SECURITY = ROOT / "SECURITY.md"


class TestEnvExampleCatalogConnectPolicy:
    def test_documents_connect_secret_and_origin_gates(self) -> None:
        text = ENV_EXAMPLE.read_text(encoding="utf-8")
        assert "KATER_CONNECT_ALLOW_LOCAL_SETTINGS=0" in text
        assert "KATER_CONNECT_SECRET_SINK=" in text
        assert "KATER_CONNECT_PUBLIC_BASE_URL=https://kater.example.com" in text
        assert "docs/ops/chefvault.md" in text
        assert "does not write Vault items" in text


class TestEnvExampleContextTokenSection:
    def test_documents_context_token_secret(self) -> None:
        text = ENV_EXAMPLE.read_text(encoding="utf-8")
        assert "KATER_CONTEXT_TOKEN_SECRET=" in text
        assert "X-Kater-Context" in text

    def test_warns_about_process_local_fallback_in_multi_instance(self) -> None:
        text = ENV_EXAMPLE.read_text(encoding="utf-8")
        assert "process-local secret" in text
        assert "Multi-instance / production" in text


class TestEnvExampleBrowserLane:
    def test_documents_all_three_provider_backends(self) -> None:
        text = ENV_EXAMPLE.read_text(encoding="utf-8")
        assert "local  — Playwright Chromium in-process (default)" in text
        assert "cdp    — attach to Browserless" in text
        assert "steel  — Steel Browser OSS" in text
        assert "docs/browser.md" in text

    def test_documents_public_deploy_opt_in_gate(self) -> None:
        text = ENV_EXAMPLE.read_text(encoding="utf-8")
        assert "KATER_PUBLIC=1" in text
        assert "KATER_BROWSER_ENABLE" in text
        assert "1/true/yes/on" in text

    def test_documents_expected_browser_env_vars(self) -> None:
        text = ENV_EXAMPLE.read_text(encoding="utf-8")
        expected_vars = [
            "KATER_BROWSER_ENABLE=0",
            "KATER_BROWSER_PROVIDER=local",
            "KATER_BROWSER_CDP_URL=",
            "KATER_BROWSER_STEEL_URL=",
            "KATER_BROWSER_STEEL_KEY=",
            "KATER_BROWSER_ALLOW_DOMAINS=",
            "KATER_BROWSER_DENY_DOMAINS=",
            "KATER_BROWSER_ALLOW_PRIVATE=0",
            "KATER_BROWSER_MAX_SESSIONS=4",
            "KATER_BROWSER_SESSION_TTL=1800",
            "KATER_BROWSER_ACTION_TIMEOUT_MS=15000",
            "KATER_BROWSER_NO_SANDBOX=0",
            "KATER_BROWSER_ALLOW_EVALUATE=0",
            "KATER_BROWSER_MAX_PAGES_PER_SESSION=5",
            "KATER_BROWSER_MAX_SCREENSHOT_BYTES=2097152",
        ]
        for var in expected_vars:
            assert var in text, f"missing expected browser env line: {var!r}"


class TestEnvExampleComputerConnector:
    def test_documents_computer_connector_vars(self) -> None:
        text = ENV_EXAMPLE.read_text(encoding="utf-8")
        assert "KATER_COMPUTER_URL=" in text
        assert "KATER_COMPUTER_TOKEN=" in text
        assert "KATER_COMPUTER_PROFILE=core" in text
        assert "/api/computer" in text
        assert "kater computer" in text


class TestEnvExampleExtensionsSection:
    def test_no_longer_points_only_at_private_overlays_doc(self) -> None:
        # Regression: the extensions section used to only reference the
        # private overlay doc; it must now also point at the public docs.
        text = ENV_EXAMPLE.read_text(encoding="utf-8")
        assert "docs/profiles.md" in text
        assert "docs/architecture/" in text
        assert "docs/ops/private-overlays.md" in text
        assert "domain overlays" in text


class TestDocBrowserMd:
    def test_file_exists(self) -> None:
        assert DOC_BROWSER.is_file()

    def test_documents_public_deploy_gate(self) -> None:
        text = DOC_BROWSER.read_text(encoding="utf-8")
        assert "KATER_PUBLIC=1" in text
        assert "KATER_BROWSER_ENABLE" in text
        assert "1`, `true`, `yes`, or `on`" in text

    def test_documents_each_provider_backend(self) -> None:
        text = DOC_BROWSER.read_text(encoding="utf-8")
        assert "## local (default)" in text
        assert "## cdp" in text
        assert "## steel / remote" in text
        assert "KATER_BROWSER_CDP_URL" in text
        assert "KATER_BROWSER_STEEL_URL" in text
        assert "KATER_BROWSER_STEEL_KEY" in text
        assert "steel-dev/steel-browser" in text

    def test_documents_policy_knobs_section(self) -> None:
        text = DOC_BROWSER.read_text(encoding="utf-8")
        assert "## Policy knobs" in text
        assert ".env.example" in text


class TestDocDeployLocalMd:
    def test_documents_three_port_layout(self) -> None:
        text = DOC_DEPLOY_LOCAL.read_text(encoding="utf-8")
        assert "9090" in text
        assert "9091" in text
        assert "9092" in text
        assert "MCP SSE" in text
        assert "REST API + dashboard" in text
        assert "WebSocket telemetry" in text

    def test_documents_health_check(self) -> None:
        text = DOC_DEPLOY_LOCAL.read_text(encoding="utf-8")
        assert "curl -fsS http://127.0.0.1:9091/health" in text

    def test_documents_migrate_and_backup_cli(self) -> None:
        text = DOC_DEPLOY_LOCAL.read_text(encoding="utf-8")
        assert "uv run kater migrate apply" in text
        assert "uv run kater backup create" in text
        assert "concurrent-writer" in text.replace("\n", " ")

    def test_documents_optional_browser_lane_install(self) -> None:
        text = DOC_DEPLOY_LOCAL.read_text(encoding="utf-8")
        assert "uv sync --extra browser" in text
        assert "uv run playwright install chromium" in text
        assert "KATER_BROWSER_*" in text


class TestDocDeployServerMd:
    def test_documents_ports_table_with_env_vars(self) -> None:
        text = DOC_DEPLOY_SERVER.read_text(encoding="utf-8")
        assert "KATER_MCP_PORT" in text
        assert "KATER_API_PORT" in text
        assert "KATER_WS_PORT" in text
        assert "9090" in text
        assert "9091" in text
        assert "9092" in text

    def test_documents_kater_dir_volume_mount(self) -> None:
        text = DOC_DEPLOY_SERVER.read_text(encoding="utf-8")
        assert "/app/.kater" in text

    def test_documents_migrate_and_backup_cli(self) -> None:
        text = DOC_DEPLOY_SERVER.read_text(encoding="utf-8")
        assert "uv run kater migrate apply" in text
        assert "uv run kater backup create" in text

    def test_documents_playwright_system_dependencies_guidance(self) -> None:
        text = DOC_DEPLOY_SERVER.read_text(encoding="utf-8")
        assert "uv sync --extra browser" in text
        assert "playwright install --with-deps chromium" in text
        assert "CDP/remote providers avoid shipping a browser" in text
        assert "KATER_CONNECT_PUBLIC_BASE_URL" in text
        assert "docs/ops/catalog-connect.md" in text


class TestDocCatalogConnect:
    def test_documents_deny_default_sink_and_origin(self) -> None:
        text = DOC_CATALOG_CONNECT.read_text(encoding="utf-8")
        assert "KATER_CONNECT_ALLOW_LOCAL_SETTINGS" in text
        assert "KATER_CONNECT_PUBLIC_BASE_URL" in text
        assert "check_admin" in text
        assert "does **not** write Vault items" in text
        assert "X-Forwarded-Host" in text
        security = DOC_SECURITY.read_text(encoding="utf-8")
        assert "KATER_CONNECT_PUBLIC_BASE_URL" in security
        assert "KATER_CONNECT_ALLOW_LOCAL_SETTINGS" in security