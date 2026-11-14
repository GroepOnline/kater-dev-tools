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
