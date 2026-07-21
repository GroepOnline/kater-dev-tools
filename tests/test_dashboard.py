"""Dashboard rendering + dashboard<->API path coupling.

The dashboard is a deep module behind one interface (`render_dashboard`).
These tests guard two things the design review flagged:
  1. The internal per-view seams still compose into the full document.
  2. Every REST path the dashboard's JS calls actually exists in the API
     RouteTable (catches drift like the previously-missing /api/tunnel route).
"""

from __future__ import annotations

import pytest

from kater.api import ROUTER
from kater.web import render_dashboard
from kater.web.dashboard import (
    _HTML,
    _VIEW_CATALOG,
    _VIEW_DASHBOARD,
    _VIEW_DEPLOY,
    _VIEW_EVALS,
    _VIEW_PR,
    _VIEW_SETTINGS,
)


def test_render_dashboard_is_a_full_document():
    html = render_dashboard()
    assert html.startswith("<!DOCTYPE html>")
    assert "<style>" in html and "</style>" in html
    assert "<script>" in html and "</script>" in html
    assert html.rstrip().endswith("</html>")
    assert 'id="catalog-search"' in html


def test_dashboard_injects_configured_ws_port():
    assert "window.KATER_CONFIG={wsPort:12345}" in render_dashboard(ws_port=12345)
    assert "wsPort:9092" in render_dashboard()


def test_overview_has_situational_awareness_seams():
    # The 2026 redesign leads with triage, not vanity numbers: an exception
    # strip, live KPI sparklines, a 5-state routing table, and a latency strip.
    html = render_dashboard()
    assert 'id="exc-strip"' in html  # triage-first exception strip
    assert 'id="spark-success"' in html and 'id="spark-latency"' in html
    assert 'id="latency-strip"' in html  # canvas latency oscilloscope
    assert "Routing table" in html
    assert 'id="telemetry-stream"' in html


def test_command_palette_is_present():
    # ⌘K command palette is the discoverable entry point for navigation/actions.
    html = render_dashboard()
    assert 'id="cmd-palette"' in html
    assert 'id="palette-input"' in html
    assert 'id="palette-results"' in html


def test_catalog_has_status_facets():
    html = render_dashboard()
    assert 'id="catalog-facets"' in html
    assert 'data-cfilter="needs"' in html
    assert "clearTelemetryStream" in html  # activity clear control
    assert "writeUrlState" in html  # shareable URL state
    assert "context_cost" in html  # routing table uses catalog cost


def test_zero_result_states_have_recovery_actions():
    # Empty states must offer a one-click way out instead of a dead-end note
    # (PR #103): the Catalog and Overview render semantic <button> recovery
    # links that reset the search or the status/route filter.
    html = render_dashboard()
    # Handlers wired to the recovery buttons.
    assert "function clearCatalogSearch" in html
    assert "function resetCatalogFilter" in html
    assert "function resetRouteFilter" in html
    # Labels shown in the empty state, plus the shared styling hook.
    assert "Clear search" in html
    assert "Switch filter to all" in html
    assert "view-empty-link" in html
    # Buttons are defensively typed so they never submit a surrounding form.
    assert "type = 'button'" in html
    # A newer search/filter load invalidates stale in-flight catalog responses.
    assert "catalogLoadSeq" in html


def test_each_view_is_present_via_its_own_seam():
    # The per-view constants must each own exactly their view and compose
    # into the single _HTML body (deletion test: drop one -> a view vanishes).
    for view_id, const in [
        ("view-dashboard", _VIEW_DASHBOARD),
        ("view-catalog", _VIEW_CATALOG),
        ("view-evals", _VIEW_EVALS),
        ("view-deploy", _VIEW_DEPLOY),
        ("view-settings", _VIEW_SETTINGS),
    ]:
        assert f'id="{view_id}"' in const, view_id
        assert const in _HTML, view_id
        assert f'id="{view_id}"' in render_dashboard(), view_id


# (method, concrete-path) pairs that the dashboard JS fetches. Sample values
# stand in for the {name}/{fmt}/{provider}/{action} params.
DASHBOARD_ENDPOINTS = [
    ("GET", "/api/status"),
    ("GET", "/api/profiles"),
    ("GET", "/api/catalog"),
    ("GET", "/api/evals"),
    ("GET", "/api/deploy"),
    ("GET", "/api/deploy/json"),
    ("GET", "/api/settings"),
    ("GET", "/api/mcp/servers/github"),
    ("POST", "/api/mcp/servers/github/enable"),
    ("POST", "/api/mcp/servers/github/disable"),
    ("POST", "/api/mcp/servers/github/toggle"),
    ("GET", "/api/tunnel"),
    ("POST", "/api/tunnel/cloudflare/start"),
    ("POST", "/api/tunnel/tailscale/start"),
    ("POST", "/api/settings"),
]


@pytest.mark.parametrize("method,path", DASHBOARD_ENDPOINTS)
def test_dashboard_endpoint_exists_in_router(method, path):
    assert ROUTER.match(method, path) is not None, f"{method} {path} has no route"


def test_decorative_marks_are_aria_hidden():
    # Icon-only brand marks / tab SVGs must not be announced as unlabeled images.
    html = render_dashboard()
    assert 'class="brand-mark" aria-hidden="true"' in html
    assert html.count('class="tab-icon" aria-hidden="true"') >= 5


def test_catalog_count_is_status_region_not_describedby():
    # Result counts are a status readout (role=status). Pairing them with
    # aria-describedby on the search box caused mid-keystroke chatter.
    html = render_dashboard()
    assert 'id="catalog-count" role="status"' in html
    assert 'aria-describedby="catalog-count"' not in html
    assert "aria-describedby='catalog-count'" not in html
    # Pluralization contract used by the status region.
    assert "serverCount === 1 ? '1 server'" in html
    assert "serverCount + ' servers'" in html


def test_tunnel_controls_have_state_aware_aria_contract():
    # Notion eval for dashboard a11y: visible/action labels stay consistent and
    # transition states are announced (Start → Starting → Stop).
    html = render_dashboard()
    assert 'id="btn-cf"' in html
    assert 'aria-label="Start cloudflare tunnel"' in html
    assert 'aria-label="Start tailscale tunnel"' in html
    assert "btn.textContent = running ? 'Stop' : 'Start'" in html
    assert "aria-label', (running ? 'Stop ' : 'Start ') + provider + ' tunnel')" in html
    assert "Starting ' : 'Stopping '" in html
    # No stale "ON" label that disagrees with the Stop aria-label.
    assert "running ? 'ON'" not in html


def test_catalog_toggle_aria_label_matches_enable_disable_verb():
    # Switch labels use Enable/Disable (same verb as the command palette), and
    # toggleServerCard refreshes the label after the POST succeeds.
    html = render_dashboard()
    assert "(s.enabled ? 'Disable ' : 'Enable ') + s.name + ' server'" in html
    assert "(data.enabled ? 'Disable ' : 'Enable ') + name + ' server'" in html
    assert "'Toggle '" not in html
    assert '"Toggle "' not in html


def test_profile_pills_expose_pressed_state():
    html = render_dashboard()
    assert "pill.setAttribute('aria-pressed', String(on))" in html
    assert "el.setAttribute('aria-pressed', String(on))" in html


def test_copy_deploy_code_guards_reentrancy_and_gives_feedback():
    html = render_dashboard()
    assert "function copyDeployCode(btn)" in html
    assert "if (btn.dataset.copying) return;" in html
    assert "btn.textContent = 'Copied!';" in html
    assert 'onclick="copyDeployCode(this)"' in html


def test_mobile_hides_tab_shortcut_hints():
    # Shortcut keycaps are desktop-only; hide them under the mobile breakpoint.
    html = render_dashboard()
    assert ".tab-kbd { display: none; }" in html


def test_pr_tab_does_not_claim_digit_shortcut():
    # Digits 1-5 map to dashboard/catalog/evals/deploy/settings. PR control is
    # palette-only, so it must not show a misleading "4" keycap.
    html = render_dashboard()
    assert "PR control" in html
    # No tab-kbd immediately after the PR label.
    assert 'tab-label">PR control</span> <span class="tab-kbd">' not in html
    # Digit map still excludes PR.
    assert "['dashboard', 'catalog', 'evals', 'deploy', 'settings']" in html


def test_pr_view_uses_standard_header_and_scroll_layout():
    # The PR control view must follow the same .view-header / .view-scroll
    # contract as the other views so vertical alignment stays consistent.
    assert 'class="view-header"' in _VIEW_PR
    assert 'class="view-scroll"' in _VIEW_PR
    assert _VIEW_PR in _HTML
    assert 'class="view-header"' in render_dashboard()


def test_pr_view_has_accessible_refresh_button_and_status_region():
    # Manual reload is keyboard-accessible with an explicit ARIA label, and the
    # PR count is a live status region so screen readers announce updates.
    html = render_dashboard()
    assert 'id="btn-pr-refresh"' in _VIEW_PR
    assert 'aria-label="Refresh pull requests"' in _VIEW_PR
    assert 'onclick="loadPRView(this)"' in _VIEW_PR
    assert 'id="pr-count" role="status"' in _VIEW_PR
    assert 'id="btn-pr-refresh"' in html


def test_pr_view_reload_is_race_safe_and_dom_safe():
    # An incrementing sequence counter discards stale responses when multiple
    # reloads overlap, and untrusted PR data is rendered via the DOM API
    # (textContent / setAttribute) rather than innerHTML, removing XSS surface.
    html = render_dashboard()
    assert "let prLoadSeq" in html
    assert "const seq = ++prLoadSeq" in html
    assert "if (seq !== prLoadSeq) return" in html
    # loadPRView takes the button so it can manage its own busy state.
    assert "async function loadPRView(btn)" in html
    # Inside loadPRView, the grid is cleared and populated via the DOM API.
    # Slice the function body out so the assertion only covers PR rendering
    # (the catalog grid elsewhere still uses innerHTML = '' and that's fine).
    fn_start = html.index("async function loadPRView(btn)")
    fn_body = html[fn_start : html.index("async function onMergeClick", fn_start)]
    assert "grid.replaceChildren()" in fn_body
    assert "grid.innerHTML" not in fn_body  # DOM API only; no XSS surface
    # Card fields are assigned via textContent, not string interpolation.
    assert "title.textContent = '#' + pr.number" in fn_body
    assert "badge.textContent = verdict" in fn_body
