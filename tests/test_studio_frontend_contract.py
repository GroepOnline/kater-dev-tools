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
    assert "/session/work" in source
    assert "/session/events" in source


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


def test_agent_session_transport_is_bound_to_python_context_authority() -> None:
    agents = (STUDIO / "src/views/AgentsView.tsx").read_text()
    client = (STUDIO / "src/api/client.ts").read_text()
    assert "/api/contexts" in client
    assert "/api/audit/capabilities" in client
    assert "/session/work" in client
    assert "/session/events" in client
    assert "/session/continue" in client
    assert "sessionSubmit" in client
    assert "katerContextId" in client
    assert "/api/execute" not in client
    assert ".metadata" not in agents
    assert 'surface="kater"' in agents
    assert "useAgentSessionTransport" in agents
    assert "AgentSessionEventRow" in agents


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
    activity_hook = (STUDIO / "src/hooks/useAgentContextEvents.ts").read_text()
    assert summary.exists()
    assert audit_row.exists()
    assert "AgentSessionSummary" in agents
    assert "AgentAuditEventRow" in agents
    assert "auditAvailable" in agents
    assert "requestedContextId.current === requestedId" in activity_hook
    assert "requestGeneration.current === generation" in activity_hook
    assert "const generation = ++requestGeneration.current" in activity_hook
    assert "data: null, error: null, loading: true" in activity_hook
    summary_source = summary.read_text()
    composer = (STUDIO / "src/components/AgentSessionComposer.tsx").read_text()
    event_row = (STUDIO / "src/components/AgentSessionEventRow.tsx").read_text()
    transport_hook = (STUDIO / "src/hooks/useAgentSessionTransport.ts").read_text()
    assert "Write transport not bound" not in summary_source
    assert "Python session transport" in summary_source
    assert "AgentSessionComposer" in summary_source
    assert "type AuditStatus = 'loading' | 'available' | 'unavailable'" in summary_source
    assert "auditStatus === 'loading'" in summary_source
    assert "Audit loading…" in summary_source
    assert "Audit unavailable" in summary_source
    assert "auditStatus={auditStatus}" in agents
    assert "auditStatus === 'loading' ? 'audit loading…'" in agents
    assert "reason" in audit_row.read_text()
    assert "timestamp" in audit_row.read_text()
    assert 'htmlFor="agent-session-prompt"' in composer
    assert 'id="agent-session-prompt"' in composer
    assert "Submit work" in composer
    assert "Continue session" in composer
    assert "Cancel work" in composer
    assert "sessionSubmit" in transport_hook
    assert "wait_ms" in transport_hook
    assert "const generation = ++requestGeneration.current" in transport_hook
    assert "requestGeneration.current === generation" in transport_hook
    assert "classifyAgentProvider" in event_row
    assert "event.provider" in event_row
    assert "/api/execute" not in agents
    assert "Send message" not in agents
    assert "Take over" not in agents
    assert "setInterval" not in transport_hook
    assert "Math.random" not in transport_hook


def test_agent_workspace_has_session_and_audit_filtering_without_new_authority() -> None:
    agents = (STUDIO / "src/views/AgentsView.tsx").read_text()
    session_filters = (STUDIO / "src/components/AgentSessionFilters.tsx").read_text()
    audit_filters = (STUDIO / "src/components/AgentAuditFilters.tsx").read_text()
    styles = (STUDIO / "src/styles/global.css").read_text()
    assert "AgentSessionFilters" in agents
    assert "AgentAuditFilters" in agents
    assert "activeOnly" in agents
    assert "outcomeFilter" in agents
    assert "visibleRows" in agents
    assert "visibleEvents" in agents
    assert "aria-pressed" in session_filters
    assert "aria-pressed" in audit_filters
    assert 'htmlFor="agent-session-search"' in session_filters
    assert 'id="agent-session-search"' in session_filters
    assert 'htmlFor="agent-audit-search"' in audit_filters
    assert 'id="agent-audit-search"' in audit_filters
    assert 'role="group"' in audit_filters
    assert ".topbar-actions .authority-chip{display:none}" in styles
    assert styles.count(
        "grid-template-columns:repeat(3,minmax(0,1fr))"
    ) == 1
    responsive_facts = (
        "@media(max-width:900px){.agent-session-facts{"
        "grid-template-columns:repeat(2,minmax(0,1fr))}}"
    )
    assert responsive_facts in styles
    assert (
        ".agent-context-list>.subsection-title,.agent-context-list>.agent-filter-panel,"
        ".agent-context-list>.empty-state{grid-column:1/-1}"
    ) in styles
    assert "/api/execute" not in agents
    assert "send message" not in agents.lower()
    assert "takeover" not in agents.lower()
    assert "Submit work" not in agents


def test_catalog_sort_markup_ships_in_studio_bundle() -> None:
    source = "\n".join(
        path.read_text() for path in (STUDIO / "src").rglob("*") if path.is_file()
    )
    # The Studio IntegrationsView renders a sort <select> next to its toolbar.
    assert "catalog-sort-select" in source
    assert "Popularity" in source
    assert "Name (A-Z)" in source
    assert "Name (Z-A)" in source
    assert "onSortChange" in source
    assert "SEARCH_DEBOUNCE_MS" in source

    # The bundled studio assets must also surface the sort markup, since the
    # runtime UI ships from `studio_dist/assets/*` (no manual hand-edits in
    # dashboard.py). The grep'd substring proves the rebuild captured it.
    dist_js = (ROOT / "src/kater/web/studio_dist/assets/studio.js")
    assert dist_js.exists(), "studio dist bundle missing; run `cd studio && npm run build`"
    bundle = dist_js.read_text()
    assert "catalog-sort-select" in bundle
    assert "Popularity" in bundle


def test_automation_reschedule_cycles_known_intervals_and_resets_unknown() -> None:
    source = (STUDIO / "src/views/AutomationsView.tsx").read_text()
    assert "const schedules = [60, 300, 900]" in source
    assert "const index = schedules.indexOf(seconds)" in source
    assert "schedules[(index + 1) % schedules.length]" in source


def test_connection_count_pill_is_wired_into_studio() -> None:
    card = (STUDIO / "src/components/IntegrationCard.tsx").read_text()
    types = (STUDIO / "src/types.ts").read_text()
    # Source-level wiring: the prop is typed, optional, and the pill ships a
    # distinct className so CSS can style it.
    assert "connectionCount" in card
    assert "connection-pill" in card
    assert "connection_count" in types

    # The bundled studio assets must also carry the prop and className so the
    # runtime UI ships the pill without hand-edits in dashboard.py.
    dist_js = (ROOT / "src/kater/web/studio_dist/assets/studio.js")
    assert dist_js.exists(), "studio dist bundle missing; run `cd studio && npm run build`"
    bundle = dist_js.read_text()
    assert "connectionCount" in bundle
    assert "connection-pill" in bundle


def test_trigger_pills_render_in_studio_bundle() -> None:
    types = (STUDIO / "src/types.ts").read_text()
    card = (STUDIO / "src/components/IntegrationCard.tsx").read_text()
    view = (STUDIO / "src/views/IntegrationsView.tsx").read_text()
    # Source-level wiring: triggers are typed, and both card + detail panel
    # render the pill row with cadence-aware className + glyph.
    assert "triggers" in types
    assert "cadence" in types
    assert "'realtime' | 'poll'" in types
    assert "trigger-pill" in card
    assert "triggers" in card
    assert "trigger-pill" in view
    assert "triggers" in view

    # The bundled studio assets must carry the pill class + cadence token so
    # the runtime UI ships the pills without hand-edits in dashboard.py.
    dist_js = ROOT / "src/kater/web/studio_dist/assets/studio.js"
    assert dist_js.exists(), "studio dist bundle missing; run `cd studio && npm run build`"
    bundle = dist_js.read_text()
    assert "trigger-pill" in bundle
    assert "triggers" in bundle
    assert "realtime" in bundle
    assert "poll" in bundle
