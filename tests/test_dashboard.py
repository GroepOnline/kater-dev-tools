"""Dashboard rendering + dashboard<->API path coupling.

The dashboard is a deep module behind one interface (`render_dashboard`).
These tests guard two things the design review flagged:
  1. The internal per-view seams still compose into the full document.
  2. Every REST path the dashboard's JS calls actually exists in the API
     RouteTable (catches drift like the previously-missing /api/tunnel route).
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from kater.api import ROUTER
from kater.web import render_dashboard
from kater.web.dashboard import (
    _HTML,
    _VIEW_AUTOMATIONS,
    _VIEW_BROWSER,
    _VIEW_CATALOG,
    _VIEW_DASHBOARD,
    _VIEW_DEPLOY,
    _VIEW_EVALS,
    _VIEW_FABRIC,
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


def test_zero_result_states_have_profile_recovery_action():
    # Sighted, screen reader, and keyboard users must have a path to escape
    # zero-result states when a custom profile has nothing configured.
    html = render_dashboard()
    assert "Switch profile to core" in html
    assert "switchProfile('core')" in html


def test_each_view_is_present_via_its_own_seam():
    # The per-view constants must each own exactly their view and compose
    # into the single _HTML body (deletion test: drop one -> a view vanishes).
    for view_id, const in [
        ("view-dashboard", _VIEW_DASHBOARD),
        ("view-catalog", _VIEW_CATALOG),
        ("view-evals", _VIEW_EVALS),
        ("view-deploy", _VIEW_DEPLOY),
        ("view-settings", _VIEW_SETTINGS),
        ("view-browser", _VIEW_BROWSER),
        ("view-automations", _VIEW_AUTOMATIONS),
        ("view-fabric", _VIEW_FABRIC),
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
    ("POST", "/api/ws-ticket"),
    ("GET", "/api/browser/providers"),
    ("GET", "/api/browser/sessions"),
    ("POST", "/api/browser/sessions"),
    ("DELETE", "/api/browser/sessions/bsess_deadbeef"),
    ("POST", "/api/browser/sessions/bsess_deadbeef/act"),
    ("POST", "/api/browser/sessions/bsess_deadbeef/screenshot"),
    ("GET", "/api/automations"),
    ("POST", "/api/automations/auto_demo/run"),
    ("POST", "/api/automations/auto_demo/enable"),
    ("POST", "/api/automations/auto_demo/disable"),
    ("GET", "/api/capabilities"),
    ("GET", "/api/contexts"),
    ("GET", "/api/computer"),
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
    # Digits 1-5 map to Overview/Servers/Browser/Deploy/Settings. PR,
    # Automations, and Fabric are palette-only (no keycap); Performance lost
    # its digit.
    html = render_dashboard()
    assert "PR control" in html
    # No tab-kbd immediately after the PR / Automations / Fabric labels.
    assert 'tab-label">PR control</span> <span class="tab-kbd">' not in html
    assert 'tab-label">Automations</span> <span class="tab-kbd">' not in html
    assert 'tab-label">Fabric</span> <span class="tab-kbd">' not in html
    assert 'tab-label">Performance</span> <span class="tab-kbd">' not in html
    # Digit map: Browser takes 3; Performance/Fabric are palette-only.
    assert "['dashboard', 'catalog', 'browser', 'deploy', 'settings']" in html


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


def _extract_js_function(source: str, name: str) -> str:
    """Slice a whole `function name(...) {...}` declaration out of the JS."""
    start = source.index(f"function {name}(")
    # Keep a leading `async` so awaited helpers stay valid when re-run in Node.
    if start >= 6 and source[start - 6 : start] == "async ":
        start -= 6
    depth = 0
    for pos in range(source.index("{", start), len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[start : pos + 1]
    raise AssertionError(f"unbalanced braces in function {name}")


# Minimal DOM shim: enough of document/Element for the credentials modal to
# build its fields, so the test exercises the shipped JS instead of matching
# source strings. `id` registrations are tracked so a label's `for` can be
# resolved the way a browser (and a screen reader) would.
_DOM_HARNESS = r"""
const byId = new Map();

class El {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase();
    this.children = [];
    this.attributes = {};
    this.dataset = {};
    this.style = {};
    this.textContent = '';
    this.focused = false;
    this._id = '';
    const classes = new Set();
    this.classList = {
      add: (c) => classes.add(c),
      remove: (c) => classes.delete(c),
      contains: (c) => classes.has(c),
    };
  }
  get id() { return this._id; }
  set id(value) {
    this._id = String(value);
    if (!byId.has(this._id)) byId.set(this._id, []);
    byId.get(this._id).push(this);
  }
  get innerHTML() { return ''; }
  set innerHTML(value) {
    if (value !== '') throw new Error('harness only supports clearing innerHTML');
    this.children = [];
  }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return name in this.attributes ? this.attributes[name] : null; }
  appendChild(child) { this.children.push(child); return child; }
  addEventListener() {}
  focus() { this.focused = true; }
  querySelector(sel) {
    for (const child of this.children) {
      if (child.tagName === String(sel).toUpperCase()) return child;
      const hit = child.querySelector(sel);
      if (hit) return hit;
    }
    return null;
  }
}

const shell = {};
for (const id of ['cred-title', 'cred-sub', 'cred-fields', 'cred-provider', 'cred-modal']) {
  const el = new El('div');
  el.id = id;
  shell[id] = el;
}
const document = {
  createElement: (tag) => new El(tag),
  getElementById: (id) => shell[id] || null,
};
let credServer = null;
let credInvoker = null;
let detailInvoker = null;

/*__DASHBOARD_JS__*/

openCredentialsModal(/*__SERVER__*/);

const fields = document.getElementById('cred-fields');
const rendered = fields.children.map((wrap) => {
  const label = wrap.children.find((c) => c.tagName === 'LABEL') || null;
  const input = wrap.children.find((c) => c.tagName === 'INPUT') || null;
  const target = label ? label.getAttribute('for') : null;
  const matches = target ? (byId.get(target) || []) : [];
  return {
    labelText: label ? label.textContent : null,
    labelFor: target,
    inputId: input ? input.id : null,
    inputType: input ? input.type : null,
    envData: input ? input.dataset.env : null,
    focused: input ? input.focused : null,
    // How many elements in the document answer to the label's `for`, and
    // whether the one it resolves to is this field's own input.
    idMatchCount: matches.length,
    resolvesToOwnInput: matches.length === 1 && matches[0] === input,
  };
});
process.stdout.write(JSON.stringify({
  fields: rendered,
  modalOpen: document.getElementById('cred-modal').classList.contains('show'),
}));
"""


def _open_credentials_modal(env_required: list[str], tmp_path) -> dict:
    """Run the dashboard's real credentials-modal JS and report the DOM built."""
    node = shutil.which("node") or shutil.which("nodejs")
    if node is None:  # pragma: no cover - depends on the host toolchain
        pytest.skip("node is required to execute the dashboard JS")
    assert node is not None
    html = render_dashboard()
    dashboard_js = "\n".join(
        _extract_js_function(html, name) for name in ("credInputId", "openCredentialsModal")
    )
    server = {"name": "demo", "env_required": env_required, "env_configured": False}
    script = tmp_path / "cred_modal.cjs"
    script.write_text(
        _DOM_HARNESS.replace("/*__DASHBOARD_JS__*/", dashboard_js).replace(
            "/*__SERVER__*/", json.dumps(server)
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [node, str(script)], capture_output=True, text=True, timeout=60, check=False
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_credential_inputs_are_explicitly_associated_with_labels(tmp_path):
    # Behavioural check: run the modal's JS and assert every rendered input is
    # reachable from its own label via for/id, which is what a screen reader
    # uses to announce the credential name.
    names = ["GITHUB_TOKEN", "OPENAI_API_KEY"]
    result = _open_credentials_modal(names, tmp_path)
    assert result["modalOpen"] is True
    assert [f["labelText"] for f in result["fields"]] == names
    for name, field in zip(names, result["fields"], strict=True):
        assert field["inputId"], "input needs an id for its label to target it"
        assert field["labelFor"] == field["inputId"]
        assert field["resolvesToOwnInput"] is True
        assert field["envData"] == name
        assert field["inputType"] == "password"
    # Focus lands on the first credential field when the modal opens.
    assert result["fields"][0]["focused"] is True


def test_credential_input_ids_stay_unique_when_env_names_collide_after_sanitize(tmp_path):
    # Sanitization is lossy (FOO_BAR and FOO-BAR normalize alike, and some
    # names sanitize to nothing), so each label must still resolve to exactly
    # one input rather than stealing focus from an earlier field.
    names = ["FOO_BAR", "FOO-BAR", "API_KEY", "API-KEY", "___", "---", ""]
    result = _open_credentials_modal(names, tmp_path)
    ids = [f["inputId"] for f in result["fields"]]
    assert len(ids) == len(set(ids))
    for name, field in zip(names, result["fields"], strict=True):
        assert field["labelText"] == name
        assert field["labelFor"] == field["inputId"]
        assert field["idMatchCount"] == 1
        assert field["resolvesToOwnInput"] is True
        assert " " not in field["inputId"]


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


def test_browser_view_has_live_pane_seams():
    html = render_dashboard()
    assert 'id="view-browser"' in _VIEW_BROWSER
    assert 'class="view-header"' in _VIEW_BROWSER
    assert 'class="view-scroll"' in _VIEW_BROWSER
    assert _VIEW_BROWSER in _HTML
    assert 'id="browser-stage"' in html
    assert 'id="browser-sessions"' in html
    assert 'id="browser-url"' in html
    assert 'id="browser-log"' in html
    assert 'id="browser-providers"' in html
    assert "kater_browser_open" in html
    assert "New browser session" in html
    assert 'data-view="browser"' in html


def test_automations_view_has_list_and_unavailable_fallback():
    html = render_dashboard()
    assert 'id="view-automations"' in _VIEW_AUTOMATIONS
    assert 'class="view-header"' in _VIEW_AUTOMATIONS
    assert 'class="view-scroll"' in _VIEW_AUTOMATIONS
    assert _VIEW_AUTOMATIONS in _HTML
    assert 'id="automations-list"' in html
    assert 'data-view="automations"' in html
    assert "Automations unavailable" in html
    assert "function loadAutomationsView" in html


def test_fabric_view_has_capabilities_contexts_computer_seams():
    html = render_dashboard()
    assert 'id="view-fabric"' in _VIEW_FABRIC
    assert 'class="view-header"' in _VIEW_FABRIC
    assert 'class="view-scroll"' in _VIEW_FABRIC
    assert _VIEW_FABRIC in _HTML
    assert 'id="fabric-capabilities"' in html
    assert 'id="fabric-contexts"' in html
    assert 'id="fabric-computer"' in html
    assert 'data-view="fabric"' in html
    assert "function loadFabricView" in html
    assert "/api/capabilities" in html
    assert "/api/contexts" in html
    assert "/api/computer" in html


def test_focus_restoration_logic_is_present():
    html = render_dashboard()
    assert "let detailInvoker = null;" in html
    assert "let credInvoker = null;" in html
    assert "let detailRequestGen = 0;" in html
    assert "function openDetail" in html
    assert "const trigger = invoker !== undefined ? invoker : document.activeElement;" in html
    assert "detailInvoker = trigger;" in html
    assert "function closeDetail" in html
    assert "invoker.focus()" in html
    assert "function openCredentialsModal" in html
    assert "credInvoker = trigger;" in html
    assert "function closeCredentialsModal" in html
    assert "function openServerDetail" in html
    assert "if (gen !== detailRequestGen) return;" in html
    # Real callers must keep refresh=true on background reloads.
    assert "openServerDetail(name, true)" in html
    assert "openServerDetail(data.name, true)" in html


_FOCUS_HARNESS = r"""
const panelClassList = {
  open: false,
  add(c) { if (c === 'open') this.open = true; },
  remove(c) { if (c === 'open') this.open = false; },
  contains(c) { return c === 'open' ? this.open : false; },
};
const detailPanel = {
  classList: panelClassList,
  appendChild() {},
  contains() { return false; },
  innerHTML: '',
  textContent: '',
  style: {},
};
const document = {
  activeElement: null,
  contains(el) { return true; },
  getElementById(id) {
    if (id === 'detail-panel') return detailPanel;
    return {
      classList: { remove() {}, add() {}, contains() { return false; } },
      appendChild() {},
      contains() { return false; },
      innerHTML: '',
      textContent: '',
      style: {},
      disabled: false,
    };
  }
};
let selectedNode = null;
let writeUrlState = () => {};
const makeBadge = () => ({ classList: { remove() {} } });
const formatLaunch = () => '-';
function toast() {}

let detailInvoker = null;
let credInvoker = null;
let detailRequestGen = 0;

let pendingApi = null;
function api(url) {
  return new Promise((resolve, reject) => {
    pendingApi = { url, resolve, reject };
  });
}

/*__DASHBOARD_JS__*/

const makeCard = () => ({
  tagName: 'BUTTON',
  focusCalled: false,
  focus() { this.focusCalled = true; },
});
const cardA = makeCard();
const cardB = makeCard();
const commandBar = {
  tagName: 'INPUT',
  focusCalled: false,
  focus() { this.focusCalled = true; },
};

(async () => {
  document.activeElement = cardA;
  openDetail({ name: 'a' });
  const afterOpenDetailInvoker = detailInvoker;

  // Selecting another server while the panel stays open must retarget focus.
  document.activeElement = cardB;
  openDetail({ name: 'b' });
  const afterReselectInvoker = detailInvoker;

  // A background refresh (WebSocket update) while the user works elsewhere
  // (e.g. the command bar) must not steal the return target from the last
  // explicitly selected row.
  document.activeElement = commandBar;
  openDetail({ name: 'b' }, true);
  const afterRefreshInvoker = detailInvoker;

  // Real caller: openServerDetail captures the invoker before the await.
  // Move focus to the command bar while the API response is still pending.
  detailInvoker = cardB;
  selectedNode = { name: 'b' };
  panelClassList.open = true;
  document.activeElement = cardB;
  const openPromise = openServerDetail('b', false, cardB);
  document.activeElement = commandBar;
  pendingApi.resolve({
    name: 'b', env_required: [], env_configured: true, enabled: true,
  });
  await openPromise;
  const afterAsyncInvoker = detailInvoker;

  // Background refresh via the real caller must pass refresh=true and keep
  // the prior invoker even when focus sits on the command bar.
  document.activeElement = commandBar;
  const refreshPromise = openServerDetail('b', true);
  pendingApi.resolve({
    name: 'b', env_required: [], env_configured: true, enabled: true,
  });
  await refreshPromise;
  const afterCallerRefreshInvoker = detailInvoker;

  // Stale refresh after the panel closed must not reopen it.
  closeDetail();
  const afterCloseDetailInvoker = detailInvoker;
  panelClassList.open = false;
  selectedNode = null;
  const staleRefresh = openServerDetail('b', true);
  pendingApi.resolve({ name: 'b', env_required: [], env_configured: true });
  await staleRefresh;
  const staleRefreshReopened = panelClassList.open;

  process.stdout.write(JSON.stringify({
    detailInvokerSet: afterOpenDetailInvoker === cardA,
    detailInvokerFollowsSelection: afterReselectInvoker === cardB,
    detailInvokerSurvivesRefresh: afterRefreshInvoker === cardB,
    detailInvokerSurvivesAsyncFetch: afterAsyncInvoker === cardB,
    detailInvokerSurvivesCallerRefresh: afterCallerRefreshInvoker === cardB,
    detailInvokerCleared: afterCloseDetailInvoker === null,
    focusCalled: cardB.focusCalled,
    staleInvokerFocused: cardA.focusCalled,
    refreshFocusStolen: commandBar.focusCalled,
    staleRefreshDropped: staleRefreshReopened === false,
  }));
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
"""


def test_focus_restoration_behavior_node(tmp_path):
    node = shutil.which("node") or shutil.which("nodejs")
    if node is None:
        pytest.skip("node is required to execute the dashboard JS")
    assert node is not None
    html = render_dashboard()
    dashboard_js = "\n".join(
        _extract_js_function(html, name)
        for name in ("openDetail", "closeDetail", "openServerDetail")
    )
    script = tmp_path / "focus_restoration.cjs"
    script.write_text(
        _FOCUS_HARNESS.replace("/*__DASHBOARD_JS__*/", dashboard_js),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [node, str(script)], capture_output=True, text=True, timeout=60, check=False
    )
    assert proc.returncode == 0, proc.stderr
    res = json.loads(proc.stdout)
    assert res["detailInvokerSet"] is True
    assert res["detailInvokerFollowsSelection"] is True
    assert res["detailInvokerSurvivesRefresh"] is True
    assert res["detailInvokerSurvivesAsyncFetch"] is True
    assert res["detailInvokerSurvivesCallerRefresh"] is True
    assert res["detailInvokerCleared"] is True
    assert res["focusCalled"] is True
    assert res["staleInvokerFocused"] is False
    assert res["refreshFocusStolen"] is False
    assert res["staleRefreshDropped"] is True


# The credentials modal builds real DOM, so it needs the element shim rather
# than the flat stub above. Each scenario reruns open/close against a fresh
# invoker so capture, clearing, and restoration are asserted independently.
_CRED_FOCUS_HARNESS = r"""
class El {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase();
    this.children = [];
    this.dataset = {};
    this.style = {};
    this.textContent = '';
    this.focused = false;
    const classes = new Set();
    this.classList = {
      add: (c) => classes.add(c),
      remove: (c) => classes.delete(c),
      contains: (c) => classes.has(c),
    };
  }
  get innerHTML() { return ''; }
  set innerHTML(value) {
    if (value !== '') throw new Error('harness only supports clearing innerHTML');
    this.children = [];
  }
  setAttribute() {}
  appendChild(child) { this.children.push(child); return child; }
  addEventListener() {}
  focus() { this.focused = true; }
  querySelector(sel) {
    for (const child of this.children) {
      if (child.tagName === String(sel).toUpperCase()) return child;
      const hit = child.querySelector(sel);
      if (hit) return hit;
    }
    return null;
  }
}

const shell = {};
for (const id of ['cred-title', 'cred-sub', 'cred-fields', 'cred-provider', 'cred-modal']) {
  shell[id] = new El('div');
}
let connected = new Set();
const document = {
  createElement: (tag) => new El(tag),
  getElementById: (id) => shell[id] || null,
  activeElement: null,
  contains: (el) => connected.has(el),
};
let credServer = null;
let credInvoker = null;

/*__DASHBOARD_JS__*/

const server = { name: 'demo', env_required: [], env_configured: false };

function scenario(invoker, isConnected) {
  credInvoker = null;
  document.activeElement = invoker;
  connected = isConnected ? new Set([invoker]) : new Set();
  openCredentialsModal(server);
  const captured = credInvoker;
  const modalOpened = shell['cred-modal'].classList.contains('show');
  closeCredentialsModal();
  return {
    capturedInvoker: captured === invoker,
    capturedNothing: captured === null,
    cleared: credInvoker === null,
    focusRestored: invoker.focused,
    modalOpened: modalOpened,
    modalClosed: !shell['cred-modal'].classList.contains('show'),
  };
}

process.stdout.write(JSON.stringify({
  focusable: scenario(new El('button'), true),
  detached: scenario(new El('button'), false),
  body: scenario(new El('body'), true),
}));
"""


def test_credentials_modal_focus_restoration_behavior_node(tmp_path):
    node = shutil.which("node") or shutil.which("nodejs")
    if node is None:  # pragma: no cover - depends on the host toolchain
        pytest.skip("node is required to execute the dashboard JS")
    assert node is not None
    html = render_dashboard()
    dashboard_js = "\n".join(
        _extract_js_function(html, name)
        for name in ("credInputId", "openCredentialsModal", "closeCredentialsModal")
    )
    script = tmp_path / "cred_focus_restoration.cjs"
    script.write_text(
        _CRED_FOCUS_HARNESS.replace("/*__DASHBOARD_JS__*/", dashboard_js),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [node, str(script)], capture_output=True, text=True, timeout=60, check=False
    )
    assert proc.returncode == 0, proc.stderr
    res = json.loads(proc.stdout)

    # A connected, focusable trigger is captured on open and refocused on close.
    assert res["focusable"]["capturedInvoker"] is True
    assert res["focusable"]["modalOpened"] is True
    assert res["focusable"]["cleared"] is True
    assert res["focusable"]["focusRestored"] is True
    assert res["focusable"]["modalClosed"] is True

    # A trigger removed from the document while the modal was open is still
    # cleared, but focusing it would throw focus back to nowhere, so it isn't.
    assert res["detached"]["capturedInvoker"] is True
    assert res["detached"]["cleared"] is True
    assert res["detached"]["focusRestored"] is False

    # <body> is not a real trigger; capturing it would trap focus at the top.
    assert res["body"]["capturedNothing"] is True
    assert res["body"]["cleared"] is True
    assert res["body"]["focusRestored"] is False
