from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "studio"


def test_studio_is_componentized_and_configurable() -> None:
    config = (STUDIO / "src/config.ts").read_text()
    tokens = (STUDIO / "src/styles/tokens.css").read_text()
    components = {path.name for path in (STUDIO / "src/components").glob("*.tsx")}
    required = {
        "Sidebar.tsx",
        "Topbar.tsx",
        "StatusPill.tsx",
        "MetricCard.tsx",
        "IntegrationCard.tsx",
        "PageHeader.tsx",
        "EmptyState.tsx",
        "PrCard.tsx",
        "AutomationCard.tsx",
        "LatencyStrip.tsx",
        "TelemetryEventRow.tsx",
        "SettingRow.tsx",
        "AgentContextCard.tsx",
    }
    assert required <= components
    assert "studioConfig" in config
    assert "VITE_KATER_API_BASE" in config
    assert "--accent:" in tokens and "--surface:" in tokens and "--sidebar-width:" in tokens


def test_studio_never_replaces_the_python_runtime_with_mock_state() -> None:
    package = (STUDIO / "package.json").read_text()
    source = "\n".join(path.read_text() for path in (STUDIO / "src").rglob("*") if path.is_file())
    assert '"express"' not in package
    assert '"ws"' not in package
    assert "Math.random" not in source
    assert "setInterval" not in source
    assert "cdn.tailwindcss.com" not in source
    assert "/api/status" in source
    assert "/api/catalog" in source
    assert "/api/pr/list" in source
    assert "/api/browser/providers" in source
    assert "/api/browser/sessions" in source
    assert "/api/automations" in source
    assert "/api/events" in source
    assert "/api/contexts" in source
    assert "/api/audit/capabilities" in source
    assert "/api/settings" in source


def test_google_ai_studio_branch_is_documented_as_salvage_only() -> None:
    architecture = (STUDIO / "ARCHITECTURE.md").read_text()
    assert "visual/interaction source material only" in architecture
    assert "Never merge that branch wholesale" in architecture
    assert "Python remains authoritative" in architecture


def test_studio_mutations_use_existing_policy_routes_without_secret_inputs() -> None:
    source = "\n".join(
        path.read_text() for path in (STUDIO / "src").rglob("*") if path.is_file()
    )
    assert "enabled ? 'enable' : 'disable'" in source
    assert "/run" in source
    assert "schedule_seconds" in source
    assert "updateSettings" in source
    assert "default_profile" in source
    assert "storage_backend" in source
    assert "admin-secret" not in source
    assert "KATER_ADMIN_KEY" not in source
    assert "type=\"password\"" not in source


def test_brainless_agent_renderers_require_real_provider_evidence() -> None:
    renderer = (STUDIO / "src/components/brainless/AgentEventLine.tsx").read_text()
    assert "event.metadata?.provider" in renderer
    assert "classifyAgentProvider" in renderer
    assert "includes('anthropic')" in renderer
    assert "includes('openai')" in renderer
    assert "includes('xai')" in renderer
    assert "return 'kater'" in renderer
    assert (STUDIO / "src/components/brainless/claude/claude-tool-call.tsx").exists()
    assert (STUDIO / "src/components/brainless/codex/codex-exec.tsx").exists()
    assert (STUDIO / "src/components/brainless/grok/grok-event.tsx").exists()


def test_agent_runtime_handoff_is_correlation_only() -> None:
    handoff = (STUDIO / "src/components/AgentRuntimeHandoff.tsx").read_text()
    agents = (STUDIO / "src/views/AgentsView.tsx").read_text()
    assert "katerContextId" in handoff
    assert "navigator.clipboard.writeText" in handoff
    assert "principal_id" not in handoff
    assert "allowed_capabilities" not in handoff
    assert "/api/execute" not in handoff
    assert "AgentRuntimeHandoff" in agents


def test_agent_session_projection_stays_read_only_and_context_authoritative() -> None:
    agents = (STUDIO / "src/views/AgentsView.tsx").read_text()
    client = (STUDIO / "src/api/client.ts").read_text()
    assert "/api/contexts" in client
    assert "/api/audit/capabilities" in client
    assert "/api/execute" not in client
    assert ".metadata" not in agents
    assert 'surface="kater"' in agents


def test_experimental_navigation_flag_controls_sidebar() -> None:
    config = (STUDIO / "src/config.ts").read_text()
    sidebar = (STUDIO / "src/components/Sidebar.tsx").read_text()
    assert "experimental: true" in config
    assert "studioConfig.features.showExperimentalViews" in sidebar


def test_studio_shell_is_contextual_without_fake_primary_action() -> None:
    app = (STUDIO / "src/App.tsx").read_text()
    topbar = (STUDIO / "src/components/Topbar.tsx").read_text()
    assert "activeNavigation" in app
    assert "viewLabel={activeNavigation.label}" in app
    assert "section={activeNavigation.section}" in app
    assert "Runtime managed" in topbar
    assert "Add MCP" not in topbar
    assert "disabled" not in topbar


def test_agent_activity_is_session_centered_and_truth_bound() -> None:
    agents = (STUDIO / "src/views/AgentsView.tsx").read_text()
    summary = STUDIO / "src/components/AgentSessionSummary.tsx"
    audit_row = STUDIO / "src/components/AgentAuditEventRow.tsx"
    assert summary.exists()
    assert audit_row.exists()
    assert "AgentSessionSummary" in agents
    assert "AgentAuditEventRow" in agents
    assert "Read-only projection" in summary.read_text()
    assert "Write transport not bound" in summary.read_text()
    assert "reason" in audit_row.read_text()
    assert "timestamp" in audit_row.read_text()
    assert "/api/execute" not in agents
    assert "Send message" not in agents
    assert "Take over" not in agents
