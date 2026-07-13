# ruff: noqa: E501
from __future__ import annotations

_CSS = r"""
:root {
  color-scheme: dark;
  --bg: #0b0e11;
  --surface: #11151a;
  --surface-2: #161b21;
  --surface-3: #1b2128;
  --line: #29313a;
  --line-strong: #3a4550;
  --text: #d8dee5;
  --muted: #87919c;
  --faint: #59636d;
  --cyan: #58c4d8;
  --green: #63c58b;
  --amber: #d9a84e;
  --red: #e06c75;
  --mono: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  --sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
* { box-sizing: border-box; }
html, body { min-height: 100%; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 13px/1.45 var(--sans);
  -webkit-font-smoothing: antialiased;
}
button, input, select, textarea { color: inherit; font: inherit; }
button, select { cursor: pointer; }
button:disabled, input:disabled, select:disabled { cursor: not-allowed; opacity: .55; }
a { color: var(--cyan); }
:focus-visible { outline: 2px solid var(--cyan); outline-offset: 2px; }
::selection { background: var(--cyan); color: #071013; }
.sr-only {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
}
.skip-link:focus {
  position: fixed; z-index: 100; top: 8px; left: 8px; width: auto; height: auto;
  padding: 8px 12px; clip: auto; background: var(--text); color: var(--bg);
}
[hidden], .hidden { display: none !important; }
.mono { font-family: var(--mono); }
.num { font-variant-numeric: tabular-nums; text-align: right; }
.muted { color: var(--muted); }
.danger { color: var(--red); }

.topbar {
  position: sticky; z-index: 20; top: 0; min-height: 50px; padding: 0 18px;
  display: flex; align-items: center; justify-content: space-between; gap: 20px;
  background: var(--surface); border-bottom: 1px solid var(--line);
}
.brand { display: flex; align-items: center; gap: 10px; font: 600 13px var(--mono); letter-spacing: .08em; }
.brand-mark { width: 9px; height: 9px; background: var(--cyan); }
.brand small { color: var(--faint); font-weight: 400; letter-spacing: 0; }
.top-status { display: flex; align-items: center; gap: 14px; color: var(--muted); font: 11px var(--mono); }
.status-item { display: inline-flex; align-items: center; gap: 7px; white-space: nowrap; }
.dot { width: 7px; height: 7px; border-radius: 50%; background: var(--faint); }
.dot.ok { background: var(--green); }
.dot.warn { background: var(--amber); }
.dot.bad { background: var(--red); }

.nav {
  position: sticky; z-index: 19; top: 50px; display: flex; align-items: stretch;
  padding: 0 18px; overflow-x: auto; background: var(--surface); border-bottom: 1px solid var(--line);
}
.nav button {
  min-width: 104px; padding: 11px 14px; border: 0; border-bottom: 2px solid transparent;
  background: transparent; color: var(--muted); text-align: left; font: 12px var(--mono);
}
.nav button:hover { color: var(--text); background: var(--surface-2); }
.nav button[aria-selected="true"] { color: var(--cyan); border-bottom-color: var(--cyan); }
.nav-key { float: right; color: var(--faint); font-size: 10px; }

#app { min-height: calc(100vh - 92px); padding-bottom: 45px; }
.view { max-width: 1600px; margin: 0 auto; padding: 20px 22px 28px; }
.view-header {
  min-height: 45px; margin-bottom: 14px; display: flex; align-items: flex-start;
  justify-content: space-between; gap: 20px; border-bottom: 1px solid var(--line);
}
.view-header h1 { margin: 0; font-size: 16px; font-weight: 600; }
.view-header p { margin: 3px 0 11px; color: var(--muted); font-size: 12px; }
.view-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

.panel { min-width: 0; background: var(--surface); border: 1px solid var(--line); }
.panel-head {
  min-height: 39px; padding: 9px 12px; display: flex; align-items: center;
  justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--line);
}
.panel-head h2 { margin: 0; font: 600 11px var(--mono); letter-spacing: .05em; }
.panel-body { padding: 13px; }
.section-note { color: var(--muted); font-size: 11px; }

.metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border: 1px solid var(--line); }
.metric { min-height: 92px; padding: 13px 15px; background: var(--surface); border-right: 1px solid var(--line); }
.metric:last-child { border-right: 0; }
.metric-label { color: var(--muted); font: 10px var(--mono); letter-spacing: .06em; }
.metric-value { margin-top: 8px; font: 500 28px/1 var(--mono); font-variant-numeric: tabular-nums; }
.metric-meta { margin-top: 9px; color: var(--faint); font: 10px var(--mono); }
.dashboard-grid { display: grid; grid-template-columns: minmax(540px, 1.6fr) minmax(320px, .8fr); gap: 12px; margin-top: 12px; }
.stack { display: grid; align-content: start; gap: 12px; }

.table-wrap { overflow: auto; }
table { width: 100%; border-collapse: collapse; white-space: nowrap; }
th, td { height: 37px; padding: 7px 10px; border-bottom: 1px solid var(--line); text-align: left; }
th { position: sticky; top: 0; z-index: 1; background: var(--surface-2); color: var(--muted); font: 10px var(--mono); letter-spacing: .04em; }
tbody tr:last-child td { border-bottom: 0; }
tbody tr:hover td { background: var(--surface-2); }
.empty { padding: 26px !important; color: var(--muted); text-align: center !important; white-space: normal; }
.view-empty-link {
  display: inline-block; margin-top: 10px; padding: 4px 0;
  background: none; border: 0; cursor: pointer;
  font: 11px var(--mono); color: var(--cyan); text-decoration: underline;
}
.view-empty-link:hover { color: var(--text); }

.badge {
  display: inline-flex; align-items: center; gap: 5px; min-height: 20px; padding: 2px 6px;
  border: 1px solid var(--line-strong); color: var(--muted); font: 10px var(--mono); white-space: nowrap;
}
.badge.ok { color: var(--green); border-color: #315a43; }
.badge.warn { color: var(--amber); border-color: #614d2b; }
.badge.bad { color: var(--red); border-color: #66363b; }
.badge.info { color: var(--cyan); border-color: #315a62; }

.btn {
  min-height: 31px; padding: 5px 10px; border: 1px solid var(--line-strong);
  background: var(--surface-2); color: var(--text); font: 11px var(--mono);
}
.btn:hover { border-color: var(--muted); background: var(--surface-3); }
.btn-primary { border-color: #3b707a; color: var(--cyan); }
.btn-danger { border-color: #66363b; color: var(--red); }
.btn-small { min-height: 26px; padding: 3px 8px; font-size: 10px; }

.field { display: grid; gap: 5px; }
.field label, .field-label { color: var(--muted); font: 10px var(--mono); letter-spacing: .04em; }
.input, select, textarea {
  width: 100%; min-height: 34px; padding: 7px 9px; border: 1px solid var(--line-strong);
  border-radius: 0; background: #0d1115;
}
.input::placeholder, textarea::placeholder { color: var(--faint); }
textarea { resize: vertical; }
.filters { display: grid; grid-template-columns: minmax(220px, 1fr) 180px 160px; gap: 8px; }

.tunnel-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: var(--line); }
.tunnel { padding: 12px; background: var(--surface); }
.tunnel-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.tunnel-meta { margin: 9px 0 0; color: var(--muted); font: 10px var(--mono); overflow-wrap: anywhere; }
#constellation-canvas { display: block; width: 100%; height: 220px; background: #0d1115; }

.feed { height: 220px; overflow: auto; padding: 4px 10px; background: #0d1115; font: 10px/1.6 var(--mono); }
.feed-row { display: grid; grid-template-columns: 64px 92px 1fr; gap: 8px; padding: 4px 0; border-bottom: 1px solid #1e252c; }
.feed-row .ok { color: var(--green); }
.feed-row .bad { color: var(--red); }
.feed-row .warn { color: var(--amber); }

.catalog-grid { margin-top: 10px; border: 1px solid var(--line); }
.server-row {
  display: grid; grid-template-columns: minmax(190px, 1fr) minmax(260px, 2fr) 110px 100px 120px;
  align-items: center; gap: 10px; min-height: 58px; padding: 8px 10px;
  border-bottom: 1px solid var(--line); background: var(--surface);
}
.server-row:last-child { border-bottom: 0; }
.server-row:hover { background: var(--surface-2); }
.server-name { font: 600 12px var(--mono); color: var(--text); }
.server-desc { color: var(--muted); font-size: 11px; }
.server-actions { display: flex; justify-content: flex-end; gap: 6px; }
.switch {
  position: relative; width: 34px; height: 18px; padding: 0; border: 1px solid var(--line-strong); background: var(--surface-3);
}
.switch::after { content: ""; position: absolute; width: 10px; height: 10px; top: 3px; left: 4px; background: var(--muted); }
.switch[aria-checked="true"] { border-color: #315a43; }
.switch[aria-checked="true"]::after { left: 18px; background: var(--green); }
.switch.pending::after { background: var(--amber); }

.eval-summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; margin-bottom: 12px; background: var(--line); border: 1px solid var(--line); }
.eval-stat { padding: 12px; background: var(--surface); }
.eval-stat strong { display: block; margin-top: 5px; font: 19px var(--mono); }

.deploy-layout { display: grid; grid-template-columns: 250px minmax(0, 1fr); min-height: 480px; }
.deploy-tabs { border-right: 1px solid var(--line); }
.deploy-tab {
  width: 100%; padding: 11px 12px; border: 0; border-bottom: 1px solid var(--line);
  background: transparent; color: var(--muted); text-align: left;
}
.deploy-tab:hover { background: var(--surface-2); color: var(--text); }
.deploy-tab.active { box-shadow: inset 2px 0 var(--cyan); color: var(--cyan); background: var(--surface-2); }
.deploy-tab small { display: block; margin-top: 3px; color: var(--faint); }
.code-area { min-width: 0; display: flex; flex-direction: column; }
.code-toolbar { height: 42px; padding: 6px 10px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--line); }
pre { flex: 1; margin: 0; padding: 15px; overflow: auto; background: #0d1115; color: #bdc6cf; font: 11px/1.6 var(--mono); tab-size: 2; }

.settings-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 13px; }
.field-wide { grid-column: 1 / -1; }
.callout { padding: 10px 12px; border-left: 2px solid var(--amber); background: #17150f; color: #b9aa8a; font-size: 11px; }

.drawer {
  position: fixed; z-index: 50; inset: 0 0 0 auto; width: min(480px, 100%);
  background: var(--surface); border-left: 1px solid var(--line-strong); overflow: auto;
}
.drawer-head {
  position: sticky; top: 0; z-index: 1; padding: 14px 16px; display: flex;
  align-items: center; justify-content: space-between; background: var(--surface); border-bottom: 1px solid var(--line);
}
.drawer-body { padding: 16px; display: grid; gap: 16px; }
.detail-list { margin: 0; display: grid; grid-template-columns: 120px 1fr; border-top: 1px solid var(--line); }
.detail-list dt, .detail-list dd { margin: 0; padding: 8px 0; border-bottom: 1px solid var(--line); }
.detail-list dt { color: var(--muted); font: 10px var(--mono); }
.credential-fields { display: grid; gap: 10px; }

.overlay { position: fixed; z-index: 70; inset: 0; display: grid; place-items: center; padding: 16px; background: rgba(0,0,0,.72); }
.dialog { width: min(440px, 100%); background: var(--surface); border: 1px solid var(--line-strong); }
.dialog h2 { margin: 0; padding: 13px 15px; border-bottom: 1px solid var(--line); font-size: 13px; }
.dialog-body { padding: 15px; color: var(--muted); }
.dialog-actions { padding: 10px 15px; display: flex; justify-content: flex-end; gap: 8px; border-top: 1px solid var(--line); }

.command-bar {
  position: fixed; z-index: 30; bottom: 0; left: 0; right: 0; height: 40px;
  padding: 0 18px; display: flex; align-items: center; gap: 10px;
  background: var(--surface); border-top: 1px solid var(--line-strong);
}
.command-bar span { color: var(--cyan); font: 12px var(--mono); }
#cmd-input { flex: 1; min-width: 0; border: 0; outline: 0; background: transparent; font: 11px var(--mono); }
#telegraph { color: var(--muted); font: 10px var(--mono); white-space: nowrap; }
.toast {
  position: fixed; z-index: 90; right: 16px; bottom: 54px; max-width: 380px;
  padding: 9px 12px; background: var(--surface-3); border: 1px solid var(--line-strong); font: 11px var(--mono);
}
.toast.ok { border-color: #315a43; color: var(--green); }
.toast.bad { border-color: #66363b; color: var(--red); }

@media (max-width: 960px) {
  .metrics, .eval-summary { grid-template-columns: 1fr 1fr; }
  .metric:nth-child(2) { border-right: 0; }
  .metric:nth-child(-n+2) { border-bottom: 1px solid var(--line); }
  .dashboard-grid, .settings-grid { grid-template-columns: 1fr; }
  .server-row { grid-template-columns: 1fr auto; }
  .server-row .server-desc { grid-column: 1 / -1; }
  .server-row .server-transport, .server-row .server-state { display: none; }
}
@media (max-width: 650px) {
  .topbar { padding: 0 12px; }
  .brand small, .top-status .status-item:first-child { display: none; }
  .nav { padding: 0; }
  .nav button { min-width: 88px; padding-inline: 10px; }
  .nav-key { display: none; }
  .view { padding: 14px 10px 24px; }
  .view-header { display: block; }
  .view-actions { margin-bottom: 10px; }
  .filters, .form-grid { grid-template-columns: 1fr; }
  .field-wide { grid-column: auto; }
  .tunnel-grid { grid-template-columns: 1fr; }
  .deploy-layout { grid-template-columns: 1fr; }
  .deploy-tabs { display: flex; overflow-x: auto; border-right: 0; border-bottom: 1px solid var(--line); }
  .deploy-tab { min-width: 150px; border-right: 1px solid var(--line); }
  .deploy-tab.active { box-shadow: inset 0 -2px var(--cyan); }
  #telegraph { display: none; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; transition: none !important; animation: none !important; }
}
"""

_HTML_SHELL_TOP = r"""
<a class="sr-only skip-link" href="#app">Skip to main content</a>
<header class="topbar">
  <div class="brand"><span class="brand-mark" aria-hidden="true"></span>KATER <small>Control plane</small></div>
  <div class="top-status">
    <span class="status-item"><span id="api-dot" class="dot"></span><span id="api-status">API checking</span></span>
    <span class="status-item"><span id="ws-dot" class="dot"></span><span id="ws-status">Live feed offline</span></span>
  </div>
</header>
<nav class="nav" role="tablist" aria-label="Dashboard views">
  <button id="tab-dashboard" role="tab" aria-selected="true" aria-controls="view-dashboard" tabindex="0" data-view="dashboard">Overview <span class="nav-key">1</span></button>
  <button id="tab-catalog" role="tab" aria-selected="false" aria-controls="view-catalog" tabindex="-1" data-view="catalog">Catalog <span class="nav-key">2</span></button>
  <button id="tab-evals" role="tab" aria-selected="false" aria-controls="view-evals" tabindex="-1" data-view="evals">Evals <span class="nav-key">3</span></button>
  <button id="tab-deploy" role="tab" aria-selected="false" aria-controls="view-deploy" tabindex="-1" data-view="deploy">Deploy <span class="nav-key">4</span></button>
  <button id="tab-settings" role="tab" aria-selected="false" aria-controls="view-settings" tabindex="-1" data-view="settings">Settings <span class="nav-key">5</span></button>
</nav>
<main id="app">
"""

_VIEW_DASHBOARD = r"""
<section class="view" id="view-dashboard" role="tabpanel" aria-labelledby="tab-dashboard" tabindex="0">
  <header class="view-header">
    <div><h1>Gateway overview</h1><p>Runtime health, backend state, and current traffic.</p></div>
    <div class="view-actions"><button class="btn" type="button" data-refresh="dashboard">Refresh</button></div>
  </header>
  <h2 class="sr-only">Key metrics</h2>
  <div class="metrics" aria-label="Gateway metrics">
    <div class="metric"><div class="metric-label">Enabled servers</div><div id="metric-servers" class="metric-value">—</div><div id="metric-servers-meta" class="metric-meta">Waiting for status</div></div>
    <div class="metric"><div class="metric-label">Tool calls</div><div id="metric-calls" class="metric-value">—</div><div class="metric-meta">Recorded events</div></div>
    <div class="metric"><div class="metric-label">Success rate</div><div id="metric-success" class="metric-value">—</div><div class="metric-meta">Across tool calls</div></div>
    <div class="metric"><div class="metric-label">Errors</div><div id="metric-errors" class="metric-value">—</div><div id="metric-profile" class="metric-meta">Profile —</div></div>
  </div>
  <div class="dashboard-grid">
    <div class="stack">
      <section class="panel">
        <div class="panel-head"><h2>Backend health</h2><span id="backend-summary" class="section-note">Loading</span></div>
        <div class="table-wrap"><table>
          <thead><tr><th>Backend</th><th>Health</th><th>Configured</th><th class="num">Tools</th><th class="num">Latency</th><th>Breaker</th></tr></thead>
          <tbody id="backend-body"><tr><td colspan="6" class="empty">Loading backend state…</td></tr></tbody>
        </table></div>
      </section>
      <section class="panel">
        <div class="panel-head"><h2>Recent calls</h2><span class="section-note">Newest first</span></div>
        <div class="table-wrap"><table>
          <thead><tr><th>Time</th><th>Tool</th><th>Profile</th><th class="num">Duration</th><th>Result</th></tr></thead>
          <tbody id="events-body"><tr><td colspan="5" class="empty">Loading recent calls…</td></tr></tbody>
        </table></div>
      </section>
    </div>
    <div class="stack">
      <section class="panel">
        <div class="panel-head"><h2>Network exposure</h2><span id="tunnel-domain" class="section-note"></span></div>
        <div id="tunnel-grid" class="tunnel-grid"><div class="tunnel">Loading tunnel state…</div></div>
      </section>
      <section class="panel">
        <div class="panel-head"><h2>Backend topology</h2><span class="section-note">Gateway → active backends</span></div>
        <canvas id="constellation-canvas" aria-label="Gateway backend topology"></canvas>
      </section>
      <section class="panel" id="telemetry-stream">
        <div class="panel-head"><h2>Live event feed</h2><span class="section-note">WebSocket</span></div>
        <div id="live-feed" class="feed" role="log" aria-live="polite"><div class="feed-row"><span>—</span><span>system</span><span>Waiting for events</span></div></div>
      </section>
    </div>
  </div>
</section>
"""

_VIEW_CATALOG = r"""
<section class="view" id="view-catalog" role="tabpanel" aria-labelledby="tab-catalog" tabindex="0" hidden>
  <header class="view-header">
    <div><h1>Server catalog</h1><p>Control backend availability and configure declared credentials.</p></div>
    <span id="catalog-count" class="badge" aria-live="polite">— servers</span>
  </header>
  <div class="filters">
    <div class="field"><label for="catalog-search">Search</label><input id="catalog-search" class="input" type="search" placeholder="Name or description" aria-describedby="catalog-count"></div>
    <div class="field"><label for="catalog-profile">Profile</label><select id="catalog-profile"><option value="">All profiles</option></select></div>
    <div class="field"><label for="catalog-status">Status</label><select id="catalog-status"><option value="">All states</option><option value="enabled">Enabled</option><option value="disabled">Disabled</option><option value="configured">Configured</option><option value="missing">Needs credentials</option></select></div>
  </div>
  <div id="catalog-grid" class="catalog-grid" aria-live="polite"><div class="empty">Loading server catalog…</div></div>
</section>
"""

_VIEW_EVALS = r"""
<section class="view" id="view-evals" role="tabpanel" aria-labelledby="tab-evals" tabindex="0" hidden>
  <header class="view-header">
    <div><h1>Tool performance</h1><p>Observed reliability and latency from gateway events.</p></div>
    <div class="view-actions"><button class="btn" type="button" data-refresh="evals">Refresh</button></div>
  </header>
  <div id="eval-summary" class="eval-summary">
    <div class="eval-stat"><span class="field-label">Tool calls</span><strong id="eval-calls">—</strong></div>
    <div class="eval-stat"><span class="field-label">Unique tools</span><strong id="eval-tools">—</strong></div>
    <div class="eval-stat"><span class="field-label">Success rate</span><strong id="eval-success">—</strong></div>
    <div class="eval-stat"><span class="field-label">Errors</span><strong id="eval-errors">—</strong></div>
  </div>
  <section class="panel">
    <div class="panel-head"><h2>Per-tool performance</h2><span id="eval-span" class="section-note"></span></div>
    <div class="table-wrap"><table>
      <thead><tr><th>Tool</th><th class="num">Calls</th><th class="num">Succeeded</th><th class="num">Failed</th><th class="num">Success rate</th><th class="num">Average latency</th></tr></thead>
      <tbody id="eval-body"><tr><td colspan="6" class="empty">Loading evaluation telemetry…</td></tr></tbody>
    </table></div>
  </section>
</section>
"""

_VIEW_DEPLOY = r"""
<section class="view" id="view-deploy" role="tabpanel" aria-labelledby="tab-deploy" tabindex="0" hidden>
  <header class="view-header">
    <div><h1>Deployment configs</h1><p>Generated, profile-aware client and infrastructure configuration.</p></div>
  </header>
  <section class="panel deploy-layout">
    <div id="deploy-tabs" class="deploy-tabs" role="tablist" aria-label="Deployment formats"><div class="empty">Loading formats…</div></div>
    <div class="code-area">
      <div class="code-toolbar"><span id="deploy-description" class="section-note">Select a format</span><button id="deploy-copy" class="btn btn-small" type="button">Copy</button></div>
      <pre id="deploy-code" tabindex="0">Waiting for deployment configuration…</pre>
    </div>
  </section>
</section>
"""

_VIEW_SETTINGS = r"""
<section class="view" id="view-settings" role="tabpanel" aria-labelledby="tab-settings" tabindex="0" hidden>
  <header class="view-header">
    <div><h1>Gateway config</h1><p>Authentication policy, profile defaults, limits, and storage.</p></div>
    <div class="view-actions"><button id="settings-save" class="btn btn-primary" type="button">Save settings</button></div>
  </header>
  <div class="settings-grid">
    <section class="panel">
      <div class="panel-head"><h2>Runtime policy</h2></div>
      <form id="settings-form" class="panel-body form-grid">
        <div class="field"><label for="set-auth-mode">Authentication mode</label><select id="set-auth-mode"><option value="none">None</option><option value="apikey">API key</option><option value="oauth">OAuth</option></select></div>
        <div class="field"><label for="set-profile">Default profile</label><select id="set-profile"><option value="core">core</option></select></div>
        <div class="field"><label for="set-rate-limit">Requests per minute</label><input id="set-rate-limit" class="input" type="number" min="0" step="1" inputmode="numeric"></div>
        <div class="field"><label for="set-storage">Storage backend</label><select id="set-storage"><option value="sqlite">SQLite</option><option value="jsonl">JSONL</option></select></div>
        <div class="field field-wide"><label for="set-cors">CORS origins</label><textarea id="set-cors" rows="4" placeholder="One origin per line"></textarea></div>
      </form>
    </section>
    <section class="panel">
      <div class="panel-head"><h2>Effective configuration</h2></div>
      <div class="panel-body">
        <dl id="settings-effective" class="detail-list"><dt>Status</dt><dd>Loading settings…</dd></dl>
        <p class="callout">Public deployments reject authentication disabled, wildcard CORS, and unlimited request rates. An admin credential may be required to save changes.</p>
      </div>
    </section>
  </div>
</section>
"""

_HTML_SHELL_BOTTOM = r"""
</main>
<div class="command-bar">
  <span aria-hidden="true">:</span>
  <label class="sr-only" for="cmd-input">Command</label>
  <input id="cmd-input" type="text" placeholder="Command" autocomplete="off" spellcheck="false">
  <output id="telegraph" aria-live="polite">Type help for navigation commands</output>
</div>
<aside id="detail-drawer" class="drawer" aria-labelledby="detail-name" aria-hidden="true" hidden>
  <div class="drawer-head"><div><div class="field-label">Server detail</div><strong id="detail-name" class="mono">—</strong></div><button class="btn btn-small" type="button" data-close-drawer>Close</button></div>
  <div class="drawer-body">
    <div id="detail-badges"></div>
    <p id="detail-description" class="muted"></p>
    <dl id="detail-list" class="detail-list"></dl>
    <section><h2 class="field-label">Declared credentials</h2><div id="credential-fields" class="credential-fields"></div></section>
    <div class="view-actions"><button id="credentials-save" class="btn btn-primary" type="button">Save credentials</button><button id="detail-toggle" class="btn" type="button">—</button></div>
  </div>
</aside>
<div id="confirm" class="overlay" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-body" hidden>
  <div class="dialog">
    <h2 id="confirm-title">Confirm action</h2>
    <div id="confirm-body" class="dialog-body"></div>
    <div class="dialog-actions"><button id="confirm-cancel" class="btn" type="button">Cancel</button><button id="confirm-ok" class="btn btn-danger" type="button">Confirm</button></div>
  </div>
</div>
<div id="auth-gate" class="overlay" role="dialog" aria-modal="true" aria-labelledby="auth-title" hidden>
  <div class="dialog">
    <h2 id="auth-title">Authentication required</h2>
    <div class="dialog-body">
      <p>This gateway requires an operator credential.</p>
      <div class="field"><label for="auth-key">API key</label><input id="auth-key" class="input" type="password" autocomplete="current-password"></div>
    </div>
    <div class="dialog-actions"><button id="auth-oauth" class="btn" type="button">Continue with OAuth</button><button id="auth-key-submit" class="btn btn-primary" type="button">Use API key</button></div>
  </div>
</div>
<div id="toast" class="toast" role="status" aria-live="polite" hidden></div>
"""

_HTML = (
    _HTML_SHELL_TOP
    + _VIEW_DASHBOARD
    + _VIEW_CATALOG
    + _VIEW_EVALS
    + _VIEW_DEPLOY
    + _VIEW_SETTINGS
    + _HTML_SHELL_BOTTOM
)

_JS = r"""
'use strict';

const CONFIG = window.KATER_CONFIG || {wsPort: 9092};
const views = ['dashboard', 'catalog', 'evals', 'deploy', 'settings'];
const state = {
  token: sessionStorage.getItem('kater_auth') || '',
  catalog: [], profiles: [], backends: [], deploy: [], deployFormat: '',
  drawerServer: null,
  ws: null, wsConnecting: false, wsOpen: false, wsRetry: null, wsAttempt: 0, wsGeneration: 0,
  destroyed: false,
};
const timers = new Set();
const controllers = new Set();
const listeners = [];
let confirmCtx = null;

function $(id) { return document.getElementById(id); }
function qsa(selector, root) { return Array.from((root || document).querySelectorAll(selector)); }
function esc(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function pathPart(value) { return encodeURIComponent(String(value)); }
function safeUrl(value) {
  try {
    const url = new URL(String(value), location.origin);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : '';
  } catch (_) { return ''; }
}
function number(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : (fallback == null ? 0 : fallback);
}
function fmt(value) { return number(value).toLocaleString(); }
function duration(value) { return number(value).toFixed(0) + ' ms'; }
function time(value) {
  const raw = typeof value === 'number' ? value * 1000 : value;
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleTimeString([], {hour12: false});
}
function badge(label, kind) { return '<span class="badge ' + (kind || '') + '">' + esc(label) + '</span>'; }
function onEl(target, type, fn, options) {
  target.addEventListener(type, fn, options);
  listeners.push([target, type, fn, options]);
}
function trackedTimeout(fn, ms) {
  const id = setTimeout(() => { timers.delete(id); fn(); }, ms);
  timers.add(id);
  return id;
}
function trackedInterval(fn, ms) {
  const id = setInterval(fn, ms);
  timers.add(id);
  return id;
}
async function trackedFetch(path, options) {
  const controller = new AbortController();
  const timeout = trackedTimeout(() => controller.abort(), 10000);
  controllers.add(controller);
  const opts = Object.assign({}, options || {});
  opts.headers = Object.assign({}, state.token ? {Authorization: 'Bearer ' + state.token} : {}, opts.headers || {});
  opts.signal = controller.signal;
  try { return await fetch(path, opts); }
  finally { clearTimeout(timeout); timers.delete(timeout); controllers.delete(controller); }
}
async function request(path, options) {
  let response;
  try { response = await trackedFetch(path, options); }
  catch (error) {
    if (error.name === 'AbortError') throw new Error('Request timed out');
    throw error;
  }
  let data = {};
  try { data = await response.json(); } catch (_) {}
  if (!response.ok) {
    const error = new Error(data.error || data.message || ('Request failed (' + response.status + ')'));
    error.status = response.status;
    error.data = data;
    if (response.status === 401) showAuth();
    throw error;
  }
  return data;
}
function apiGet(path) { return request(path, {method: 'GET'}); }
function apiPost(path, body) {
  return request(path, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body || {}),
  });
}
function showToast(message, kind) {
  const toast = $('toast');
  toast.textContent = message;
  toast.className = 'toast ' + (kind || '');
  toast.hidden = false;
  if (toast._hideTimer) clearTimeout(toast._hideTimer);
  toast._hideTimer = trackedTimeout(() => { toast.hidden = true; }, 3600);
}
function errorMessage(error) { return error && error.message ? error.message : 'Unexpected error'; }
function setApiStatus(ok) {
  $('api-dot').className = 'dot ' + (ok ? 'ok' : 'bad');
  $('api-status').textContent = ok ? 'API online' : 'API unavailable';
}
function dialogFocusables(dialog) {
  return qsa('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])', dialog)
    .filter((element) => !element.hidden && element.getAttribute('aria-hidden') !== 'true');
}
function openDialog(dialog, initialFocus, onEscape) {
  if (dialog._dialogState) return;
  const priorFocus = document.activeElement;
  const background = Array.from(document.body.children).filter((element) => element !== dialog).map((element) => ({
    element,
    inert: element.inert,
    ariaHidden: element.getAttribute('aria-hidden'),
  }));
  background.forEach(({element}) => {
    element.inert = true;
    element.setAttribute('aria-hidden', 'true');
  });
  const keydown = (event) => {
    event.stopPropagation();
    if (event.key === 'Escape' && onEscape) {
      event.preventDefault();
      onEscape();
      return;
    }
    if (event.key !== 'Tab') return;
    const focusables = dialogFocusables(dialog);
    if (!focusables.length) { event.preventDefault(); dialog.focus(); return; }
    const first = focusables[0], last = focusables[focusables.length - 1];
    if (event.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) {
      event.preventDefault(); last.focus();
    } else if (!event.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) {
      event.preventDefault(); first.focus();
    }
  };
  dialog._dialogState = {background, priorFocus, keydown};
  dialog.hidden = false;
  dialog.addEventListener('keydown', keydown);
  const target = initialFocus || dialogFocusables(dialog)[0] || dialog;
  if (target === dialog && !dialog.hasAttribute('tabindex')) dialog.setAttribute('tabindex', '-1');
  target.focus();
}
function closeDialog(dialog) {
  const dialogState = dialog._dialogState;
  if (!dialogState) { dialog.hidden = true; return; }
  dialog.hidden = true;
  dialog.removeEventListener('keydown', dialogState.keydown);
  dialogState.background.forEach(({element, inert, ariaHidden}) => {
    element.inert = inert;
    if (ariaHidden == null) element.removeAttribute('aria-hidden');
    else element.setAttribute('aria-hidden', ariaHidden);
  });
  dialog._dialogState = null;
  const priorFocus = dialogState.priorFocus;
  if (priorFocus && priorFocus.isConnected && priorFocus.focus) priorFocus.focus();
}

function activateView(name, focus) {
  if (!views.includes(name)) return;
  qsa('[role="tab"][data-view]').forEach((tab) => {
    const active = tab.dataset.view === name;
    tab.setAttribute('aria-selected', String(active));
    tab.tabIndex = active ? 0 : -1;
    if (active && focus) tab.focus();
  });
  views.forEach((view) => { $('view-' + view).hidden = view !== name; });
  history.replaceState(null, '', '#' + name);
  if (name === 'catalog' && !state.catalog.length) loadCatalog();
  if (name === 'evals') loadEvals();
  if (name === 'deploy' && !state.deploy.length) loadDeployFormats();
  if (name === 'settings') loadSettings();
}
function initTabNavigation() {
  const tabs = qsa('[role="tab"][data-view]');
  tabs.forEach((tab, index) => {
    onEl(tab, 'click', () => activateView(tab.dataset.view, false));
    onEl(tab, 'keydown', (event) => {
      let next = null;
      if (event.key === 'ArrowRight') next = tabs[(index + 1) % tabs.length];
      if (event.key === 'ArrowLeft') next = tabs[(index - 1 + tabs.length) % tabs.length];
      if (event.key === 'Home') next = tabs[0];
      if (event.key === 'End') next = tabs[tabs.length - 1];
      if (next) { event.preventDefault(); next.focus(); }
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        activateView(tab.dataset.view, true);
      }
    });
  });
}

function renderStatus(data) {
  const servers = data.servers || {};
  const telemetry = data.telemetry || {};
  $('metric-servers').textContent = fmt(servers.enabled);
  $('metric-servers-meta').textContent = fmt(servers.total) + ' total · ' + fmt(servers.configured) + ' configured';
  $('metric-calls').textContent = fmt(telemetry.tool_calls);
  $('metric-success').textContent = number(telemetry.success_rate).toFixed(1) + '%';
  $('metric-errors').textContent = fmt(telemetry.errors);
  $('metric-profile').textContent = 'Profile ' + (data.profile || 'core') + ' · v' + (data.version || '—');
}
async function loadStatus() {
  try { renderStatus(await apiGet('/api/status')); setApiStatus(true); }
  catch (error) { setApiStatus(false); if (error.status !== 401) showToast(errorMessage(error), 'bad'); }
}
function backendRows(data) {
  const list = data.backends || data.servers || [];
  state.backends = list;
  $('backend-summary').textContent = list.length + ' backends';
  $('backend-body').innerHTML = list.length ? list.map((item) => {
    const healthy = item.healthy === true;
    const configured = item.configured === true;
    return '<tr><td class="mono">' + esc(item.name) + '</td>'
      + '<td>' + badge(healthy ? 'Healthy' : 'Unavailable', healthy ? 'ok' : 'bad') + '</td>'
      + '<td>' + badge(configured ? 'Ready' : 'Missing env', configured ? 'ok' : 'warn') + '</td>'
      + '<td class="num">' + fmt(item.tool_count) + '</td>'
      + '<td class="num">' + duration(item.latency_ms) + '</td>'
      + '<td>' + badge(item.breaker_state || 'unknown', item.breaker_state === 'open' ? 'bad' : '') + '</td></tr>';
  }).join('') : '<tr><td colspan="6" class="empty">No backend processes reported.</td></tr>';
  drawTopology();
}
async function loadBackends() {
  try { backendRows(await apiGet('/api/backends')); }
  catch (error) {
    state.backends = [];
    $('backend-body').innerHTML = '<tr><td colspan="6" class="empty danger">' + esc(errorMessage(error)) + '</td></tr>';
    drawTopology();
  }
}
function renderEvents(data) {
  const events = (data.events || []).filter((event) => event.type === 'tool_call' || event.name);
  $('events-body').innerHTML = events.length ? events.map((event) => {
    const ok = event.success === true;
    return '<tr><td class="mono">' + esc(time(event.timestamp)) + '</td><td class="mono">' + esc(event.name || '—')
      + '</td><td>' + esc(event.profile || '—') + '</td><td class="num">' + duration(event.duration_ms)
      + '</td><td>' + badge(ok ? 'Success' : 'Failed', ok ? 'ok' : 'bad') + '</td></tr>';
  }).join('') : '<tr><td colspan="5" class="empty">No recent tool calls.</td></tr>';
}
async function loadEvents() {
  try { renderEvents(await apiGet('/api/events?limit=50')); }
  catch (error) { $('events-body').innerHTML = '<tr><td colspan="5" class="empty danger">' + esc(errorMessage(error)) + '</td></tr>'; }
}

function tunnelRunning(info) { return !!(info && (info.running || info.status === 'running' || info.url)); }
function renderTunnels(data) {
  $('tunnel-domain').textContent = data.suggested_domain || '';
  const available = data.available || {};
  const rows = ['cloudflare', 'tailscale'].map((provider) => {
    const info = data[provider] || {};
    const running = tunnelRunning(info);
    const isAvailable = available[provider] !== false;
    return '<article class="tunnel"><div class="tunnel-top"><span class="mono">' + esc(provider) + '</span>'
      + badge(running ? 'Running' : (isAvailable ? 'Stopped' : 'Not installed'), running ? 'ok' : (isAvailable ? '' : 'warn')) + '</div>'
      + '<p class="tunnel-meta">' + esc(info.url || info.hostname || 'No active public endpoint') + '</p>'
      + '<button class="btn btn-small ' + (running ? 'btn-danger' : 'btn-primary') + '" type="button" data-confirm="tunnel" data-tunnel-provider="'
      + provider + '" data-tunnel-action="' + (running ? 'stop' : 'start') + '"' + (isAvailable ? '' : ' disabled')
      + '>' + (running ? 'Stop tunnel' : 'Start tunnel') + '</button></article>';
  });
  $('tunnel-grid').innerHTML = rows.join('');
}
async function loadTunnels() {
  try { renderTunnels(await apiGet('/api/tunnel')); }
  catch (error) { $('tunnel-grid').innerHTML = '<div class="tunnel danger">' + esc(errorMessage(error)) + '</div>'; }
}
async function changeTunnel(provider, action, button) {
  button.disabled = true;
  button.textContent = action === 'start' ? 'Starting…' : 'Stopping…';
  try {
    await apiPost('/api/tunnel/' + pathPart(provider) + '/' + action);
    showToast(provider + ' tunnel ' + (action === 'start' ? 'started' : 'stopped'), 'ok');
    await loadTunnels();
  } catch (error) { showToast(errorMessage(error), 'bad'); await loadTunnels(); }
}

function resizeCanvas(canvas) {
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.max(1, Math.round(rect.width * ratio));
  canvas.height = Math.max(1, Math.round(rect.height * ratio));
  const context = canvas.getContext('2d');
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  return [context, rect.width, rect.height];
}
function drawTopology() {
  const canvas = $('constellation-canvas');
  if (!canvas) return;
  const [ctx, width, height] = resizeCanvas(canvas);
  ctx.clearRect(0, 0, width, height);
  const center = {x: width / 2, y: height / 2};
  const list = state.backends.slice(0, 16);
  const radius = {x: width * .38, y: height * .34};
  ctx.font = '10px monospace';
  ctx.textAlign = 'center';
  list.forEach((server, index) => {
    const angle = (Math.PI * 2 * index / Math.max(list.length, 1)) - Math.PI / 2;
    const point = {x: center.x + Math.cos(angle) * radius.x, y: center.y + Math.sin(angle) * radius.y};
    ctx.strokeStyle = '#29313a'; ctx.beginPath(); ctx.moveTo(center.x, center.y); ctx.lineTo(point.x, point.y); ctx.stroke();
    ctx.fillStyle = server.healthy ? '#63c58b' : '#e06c75'; ctx.fillRect(point.x - 3, point.y - 3, 6, 6);
    ctx.fillStyle = '#87919c'; ctx.fillText(String(server.name || '').slice(0, 18), point.x, point.y + 15);
  });
  ctx.fillStyle = '#58c4d8'; ctx.fillRect(center.x - 5, center.y - 5, 10, 10);
  ctx.fillStyle = '#d8dee5'; ctx.fillText('gateway', center.x, center.y + 20);
}

function profileName(profile) { return typeof profile === 'string' ? profile : (profile.name || profile.id || ''); }
async function loadProfiles() {
  try {
    const data = await apiGet('/api/profiles');
    state.profiles = data.profiles || [];
    const options = state.profiles.map((profile) => '<option value="' + esc(profileName(profile)) + '">' + esc(profileName(profile)) + '</option>').join('');
    $('catalog-profile').innerHTML = '<option value="">All profiles</option>' + options;
    $('set-profile').innerHTML = options || '<option value="core">core</option>';
  } catch (_) {}
}
function catalogFiltered() {
  const query = $('catalog-search').value.trim().toLowerCase();
  const profile = $('catalog-profile').value;
  const status = $('catalog-status').value;
  return state.catalog.filter((server) => {
    const matchesText = !query || (server.name + ' ' + (server.description || '')).toLowerCase().includes(query);
    const matchesProfile = !profile || (server.profiles || []).includes(profile) || profile === 'core';
    const matchesStatus = !status
      || (status === 'enabled' && server.enabled) || (status === 'disabled' && !server.enabled)
      || (status === 'configured' && server.env_configured) || (status === 'missing' && !server.env_configured);
    return matchesText && matchesProfile && matchesStatus;
  });
}
function renderCatalog() {
  const list = catalogFiltered();
  $('catalog-count').textContent = list.length + ' of ' + state.catalog.length + ' servers';
  $('catalog-grid').innerHTML = list.length ? list.map((server) => {
    const pending = !!server._pending;
    return '<article class="server-row" data-server-row="' + esc(server.name) + '">'
      + '<div><button class="server-name btn btn-small" type="button" data-open-server="' + esc(server.name) + '">' + esc(server.name) + '</button></div>'
      + '<div class="server-desc">' + esc(server.description || 'No description provided.') + '</div>'
      + '<div class="server-transport">' + badge(server.transport || 'unknown', 'info') + '</div>'
      + '<div class="server-state">' + badge(server.env_configured ? 'Configured' : 'Needs env', server.env_configured ? 'ok' : 'warn') + '</div>'
      + '<div class="server-actions"><button class="switch' + (pending ? ' pending' : '') + '" type="button" role="switch" aria-label="'
      + (server.enabled ? 'Disable ' : 'Enable ') + esc(server.name) + '" aria-checked="' + String(!!server.enabled)
      + '" data-confirm="server" data-server-toggle="' + esc(server.name) + '"' + (pending ? ' disabled' : '') + '></button></div></article>';
  }).join('') : catalogEmptyHtml();
}
function catalogEmptyHtml() {
  const query = $('catalog-search').value.trim();
  if (query) {
    return '<div class="empty">No servers match "' + esc(query) + '".<br>'
      + '<button class="view-empty-link" type="button" onclick="clearCatalogSearch()">Clear search</button></div>';
  }
  return '<div class="empty">No servers match these filters.</div>';
}
function clearCatalogSearch() {
  const search = $('catalog-search');
  if (search) {
    search.value = '';
    renderCatalog();
    search.focus();
  }
}
async function loadCatalog() {
  try {
    const data = await apiGet('/api/catalog');
    state.catalog = data.servers || [];
    renderCatalog();
  } catch (error) { $('catalog-grid').innerHTML = '<div class="empty danger">' + esc(errorMessage(error)) + '</div>'; }
}
function serverByName(name) { return state.catalog.find((server) => server.name === name); }
function showServer(name) {
  const server = serverByName(name);
  if (!server) return;
  state.drawerServer = server;
  $('detail-name').textContent = server.name;
  $('detail-description').textContent = server.description || 'No description provided.';
  $('detail-badges').innerHTML = badge(server.enabled ? 'Enabled' : 'Disabled', server.enabled ? 'ok' : '')
    + ' ' + badge(server.env_configured ? 'Configured' : 'Needs credentials', server.env_configured ? 'ok' : 'warn')
    + ' ' + badge(server.risk || 'unknown risk', server.risk === 'high' ? 'bad' : '');
  const homepageUrl = safeUrl(server.homepage);
  const homepage = homepageUrl ? '<a href="' + esc(homepageUrl) + '" target="_blank" rel="noopener noreferrer">' + esc(server.homepage) + '</a>' : '—';
  $('detail-list').innerHTML = '<dt>Transport</dt><dd>' + esc(server.transport || '—') + '</dd><dt>Profiles</dt><dd>'
    + esc((server.profiles || []).join(', ') || 'core') + '</dd><dt>Context cost</dt><dd>' + esc(server.context_cost || '—')
    + '</dd><dt>Homepage</dt><dd>' + homepage + '</dd>';
  const fields = server.env_required || [];
  $('credential-fields').innerHTML = fields.length ? fields.map((key) =>
    '<div class="field"><label for="cred-' + esc(key) + '">' + esc(key) + '</label><input class="input" id="cred-'
    + esc(key) + '" type="password" autocomplete="off" data-credential-key="' + esc(key)
    + '" placeholder="' + (server.env_configured ? 'Configured — enter to replace' : 'Required') + '"></div>'
  ).join('') : '<p class="section-note">This server declares no credentials.</p>';
  $('credentials-save').hidden = !fields.length;
  $('detail-toggle').textContent = server.enabled ? 'Disable server' : 'Enable server';
  $('detail-toggle').className = 'btn ' + (server.enabled ? 'btn-danger' : 'btn-primary');
  const drawer = $('detail-drawer');
  drawer.hidden = false; drawer.setAttribute('aria-hidden', 'false');
  document.querySelector('[data-close-drawer]').focus();
}
function closeDrawer() {
  const drawer = $('detail-drawer');
  drawer.hidden = true; drawer.setAttribute('aria-hidden', 'true'); state.drawerServer = null;
}

function confirmAction(action, name, callback) {
  const labels = {enable: 'Enable server', disable: 'Disable server', 'save-credentials': 'Save credentials', 'start-tunnel': 'Start tunnel', 'stop-tunnel': 'Stop tunnel'};
  confirmCtx = {action, name, callback, ok: $('confirm-ok')};
  $('confirm-title').textContent = labels[action] || 'Confirm action';
  $('confirm-body').textContent = action === 'save-credentials'
    ? 'Credential values will be stored in Kater settings and applied to the live process.'
    : (labels[action] || 'Apply action') + (name ? ' “' + name + '”?' : '?');
  confirmCtx.ok.textContent = labels[action] || 'Confirm';
  openDialog($('confirm'), confirmCtx.ok, closeConfirm);
}
function closeConfirm() {
  confirmCtx = null;
  closeDialog($('confirm'));
}
async function runConfirmed() {
  if (!confirmCtx) return;
  const callback = confirmCtx.callback;
  closeConfirm();
  if (callback) await callback();
}
async function toggleServer(name, enabled) {
  const server = serverByName(name);
  if (!server || server._pending) return;
  const original = server.enabled;
  server.enabled = enabled; server._pending = true; renderCatalog();
  if (state.drawerServer && state.drawerServer.name === name) showServer(name);
  try {
    await apiPost('/api/mcp/servers/' + pathPart(name) + '/' + (enabled ? 'enable' : 'disable'));
    server._pending = false;
    showToast(name + (enabled ? ' enabled' : ' disabled'), 'ok');
    await Promise.all([loadCatalog(), loadStatus(), loadBackends()]);
    if ($('detail-drawer').hidden === false) showServer(name);
  } catch (error) {
    server.enabled = original; server._pending = false; renderCatalog();
    showToast(errorMessage(error), 'bad');
  }
}
async function saveCredentials() {
  const server = state.drawerServer;
  if (!server) return;
  const env = {};
  qsa('[data-credential-key]', $('credential-fields')).forEach((input) => { if (input.value.trim()) env[input.dataset.credentialKey] = input.value.trim(); });
  if (!Object.keys(env).length) { showToast('Enter at least one credential value', 'bad'); return; }
  try {
    await apiPost('/api/mcp/servers/' + pathPart(server.name) + '/credentials', {env});
    showToast('Credentials saved for ' + server.name, 'ok');
    await loadCatalog();
    showServer(server.name);
  } catch (error) { showToast(errorMessage(error), 'bad'); }
}

function renderEvals(data) {
  const tools = data.tool_calls || {};
  const summary = data.summary || {};
  $('eval-calls').textContent = fmt(summary.total_tool_calls);
  $('eval-tools').textContent = fmt(tools.unique_tools);
  $('eval-success').textContent = number(summary.overall_success_rate).toFixed(1) + '%';
  $('eval-errors').textContent = fmt(summary.total_errors);
  $('eval-span').textContent = number(data.time_span_s).toFixed(1) + ' second observation span';
  const rows = Object.entries(tools.per_tool || {}).sort((a, b) => number(b[1].total) - number(a[1].total));
  $('eval-body').innerHTML = rows.length ? rows.map(([name, item]) => '<tr><td class="mono">' + esc(name)
    + '</td><td class="num">' + fmt(item.total) + '</td><td class="num">' + fmt(item.success)
    + '</td><td class="num">' + fmt(item.failed) + '</td><td class="num">' + number(item.success_rate).toFixed(1)
    + '%</td><td class="num">' + duration(item.avg_duration_ms) + '</td></tr>').join('')
    : '<tr><td colspan="6" class="empty">No evaluation events recorded.</td></tr>';
}
async function loadEvals() {
  try { renderEvals(await apiGet('/api/evals')); }
  catch (error) { $('eval-body').innerHTML = '<tr><td colspan="6" class="empty danger">' + esc(errorMessage(error)) + '</td></tr>'; }
}

async function loadDeployFormats() {
  try {
    const data = await apiGet('/api/deploy');
    state.deploy = data.formats || [];
    $('deploy-tabs').innerHTML = state.deploy.map((format) => '<button class="deploy-tab" type="button" role="tab" aria-selected="false" data-deploy-format="'
      + esc(format.name) + '">' + esc(format.name) + '<small>' + esc(format.description || '') + '</small></button>').join('');
    if (state.deploy.length) selectDeploy(state.deploy[0].name);
  } catch (error) { $('deploy-code').textContent = errorMessage(error); }
}
async function selectDeploy(format) {
  state.deployFormat = format;
  qsa('[data-deploy-format]').forEach((tab) => {
    const active = tab.dataset.deployFormat === format;
    tab.classList.toggle('active', active); tab.setAttribute('aria-selected', String(active));
  });
  $('deploy-code').textContent = 'Loading ' + format + ' configuration…';
  try {
    const data = await apiGet('/api/deploy/' + pathPart(format));
    $('deploy-description').textContent = data.description || data.format || format;
    $('deploy-code').textContent = JSON.stringify(data, null, 2);
  } catch (error) { $('deploy-code').textContent = errorMessage(error); }
}
async function copyDeploy() {
  try { await navigator.clipboard.writeText($('deploy-code').textContent); showToast('Deployment configuration copied', 'ok'); }
  catch (_) { showToast('Clipboard access is unavailable', 'bad'); }
}

function setValue(id, value) { if (value != null) $(id).value = value; }
function renderEffectiveSettings(data) {
  $('settings-effective').innerHTML = '<dt>API</dt><dd class="mono">' + esc(data.host) + ':' + esc(data.api_port)
    + '</dd><dt>MCP</dt><dd class="mono">' + esc(data.host) + ':' + esc(data.mcp_port)
    + '</dd><dt>WebSocket</dt><dd class="mono">' + esc(data.host) + ':' + esc(data.ws_port)
    + '</dd><dt>Database</dt><dd class="mono">' + esc(data.db_path || '—')
    + '</dd><dt>API keys</dt><dd>' + fmt((data.auth || {}).api_keys) + ' configured</dd>';
}
async function loadSettings() {
  try {
    const data = await apiGet('/api/settings');
    setValue('set-auth-mode', (data.auth || {}).mode);
    setValue('set-profile', data.default_profile);
    setValue('set-rate-limit', data.rate_limit_per_min);
    setValue('set-storage', data.storage_backend);
    setValue('set-cors', (data.cors_origins || []).join('\n'));
    renderEffectiveSettings(data);
  } catch (error) { showToast(errorMessage(error), 'bad'); }
}
async function saveSettings() {
  const button = $('settings-save');
  const rate = Number.parseInt($('set-rate-limit').value, 10);
  if (!Number.isInteger(rate) || rate < 0) { showToast('Rate limit must be a non-negative integer', 'bad'); return; }
  const payload = {
    auth: {mode: $('set-auth-mode').value},
    default_profile: $('set-profile').value,
    cors_origins: $('set-cors').value.split(/\n|,/).map((item) => item.trim()).filter(Boolean),
    rate_limit_per_min: rate,
    storage_backend: $('set-storage').value,
  };
  button.disabled = true; button.textContent = 'Saving…';
  try { renderEffectiveSettings(await apiPost('/api/settings', payload)); showToast('Settings saved', 'ok'); }
  catch (error) { showToast(errorMessage(error), 'bad'); }
  finally { button.disabled = false; button.textContent = 'Save settings'; }
}

function pushFeed(event) {
  const feed = $('live-feed');
  if (feed.children.length === 1 && feed.textContent.includes('Waiting for events')) feed.textContent = '';
  const row = document.createElement('div');
  row.className = 'feed-row';
  const ok = event.success === true || /enabled|credentials/.test(event.type || '');
  const bad = event.success === false || event.type === 'error';
  const label = event.name || event.server || event.source || event.type || 'event';
  const message = event.message || event.detail || event.type || 'Update received';
  const timestamp = event.timestamp != null ? event.timestamp : (event.ts != null ? event.ts : Date.now() / 1000);
  row.innerHTML = '<span>' + esc(time(timestamp)) + '</span><span class="'
    + (bad ? 'bad' : (ok ? 'ok' : 'warn')) + '">' + esc(label) + '</span><span>' + esc(message) + '</span>';
  feed.prepend(row);
  while (feed.children.length > 100) feed.lastElementChild.remove();
}
async function websocketUrl() {
  const ticket = await apiPost('/api/ws-ticket');
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return protocol + '//' + location.hostname + ':' + CONFIG.wsPort + '/ws?ticket=' + encodeURIComponent(ticket.ticket);
}
function setWsStatus(status) {
  $('ws-dot').className = 'dot ' + (status === 'online' ? 'ok' : (status === 'connecting' ? 'warn' : 'bad'));
  $('ws-status').textContent = 'Live feed ' + status;
}
function clearWsRetry() {
  if (state.wsRetry == null) return;
  clearTimeout(state.wsRetry);
  timers.delete(state.wsRetry);
  state.wsRetry = null;
}
function scheduleWsReconnect() {
  if (state.destroyed || state.wsRetry != null || state.wsConnecting || state.wsOpen || state.ws) return;
  const wait = Math.min(30000, 1000 * Math.pow(2, state.wsAttempt++));
  state.wsRetry = trackedTimeout(() => {
    state.wsRetry = null;
    connectWebSocket();
  }, wait);
}
async function connectWebSocket() {
  if (state.destroyed || state.wsConnecting || state.wsOpen || state.ws) return;
  clearWsRetry();
  const generation = ++state.wsGeneration;
  state.wsConnecting = true;
  setWsStatus('connecting');
  try {
    const url = await websocketUrl();
    if (state.destroyed || generation !== state.wsGeneration) return;
    const socket = new WebSocket(url);
    state.ws = socket;
    socket.onopen = () => {
      if (state.ws !== socket || state.destroyed || generation !== state.wsGeneration) return;
      state.wsConnecting = false; state.wsOpen = true; state.wsAttempt = 0;
      clearWsRetry();
      setWsStatus('online');
    };
    socket.onmessage = (message) => {
      if (state.ws !== socket || state.destroyed || generation !== state.wsGeneration) return;
      try {
        const event = JSON.parse(message.data);
        pushFeed(event);
        if (/server_|credentials/.test(event.type || '')) { loadCatalog(); loadBackends(); loadStatus(); }
        if (event.type === 'tool_call' || event.type === 'error') { loadEvents(); loadStatus(); }
      } catch (_) {}
    };
    socket.onerror = () => { if (state.ws === socket) socket.close(); };
    socket.onclose = () => {
      if (state.ws !== socket || generation !== state.wsGeneration) return;
      state.ws = null; state.wsConnecting = false; state.wsOpen = false;
      if (state.destroyed) return;
      setWsStatus('offline');
      scheduleWsReconnect();
    };
  } catch (_) {
    if (generation !== state.wsGeneration) return;
    state.ws = null; state.wsConnecting = false; state.wsOpen = false;
    if (state.destroyed) return;
    setWsStatus('offline');
    scheduleWsReconnect();
  }
}

function base64url(bytes) {
  let binary = '';
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
async function beginOAuth() {
  const random = new Uint8Array(32);
  crypto.getRandomValues(random);
  const verifier = base64url(random);
  const challenge = base64url(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))));
  const oauthState = base64url(crypto.getRandomValues(new Uint8Array(20)));
  sessionStorage.setItem('kater_pkce_verifier', verifier);
  sessionStorage.setItem('kater_oauth_state', oauthState);
  const redirect = location.origin + location.pathname;
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: 'kater-dashboard',
    redirect_uri: redirect,
    code_challenge: challenge,
    code_challenge_method: 'S256',
    state: oauthState,
  });
  const url = '/authorize' + '?' + params.toString();
  location.assign(url);
}
async function finishOAuth() {
  const params = new URLSearchParams(location.search);
  const code = params.get('code');
  if (!code) return false;
  const expected = sessionStorage.getItem('kater_oauth_state');
  const verifier = sessionStorage.getItem('kater_pkce_verifier');
  if (!expected || params.get('state') !== expected || !verifier) {
    showToast('OAuth response validation failed', 'bad');
    history.replaceState(null, '', location.pathname);
    return false;
  }
  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    code,
    client_id: 'kater-dashboard',
    code_verifier: verifier,
  });
  const response = await trackedFetch('/token', {method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body: body.toString()});
  const data = await response.json();
  if (!response.ok || !data.access_token) throw new Error(data.error || 'OAuth exchange failed');
  state.token = data.access_token;
  sessionStorage.setItem('kater_auth', state.token);
  closeDialog($('auth-gate'));
  sessionStorage.removeItem('kater_oauth_state');
  sessionStorage.removeItem('kater_pkce_verifier');
  history.replaceState(null, '', location.pathname + (location.hash || ''));
  return true;
}
function showAuth() { openDialog($('auth-gate'), $('auth-key')); }
function submitApiKey() {
  const key = $('auth-key').value.trim();
  if (!key) return;
  state.token = key; sessionStorage.setItem('kater_auth', key);
  clearWsRetry();
  closeDialog($('auth-gate'));
  loadAll(); connectWebSocket();
}

function runCommand(command) {
  const parts = command.trim().toLowerCase().split(/\s+/);
  const aliases = {overview: 'dashboard', home: 'dashboard', servers: 'catalog', config: 'settings'};
  const target = aliases[parts[0]] || parts[0];
  if (views.includes(target)) {
    activateView(target, true);
    $('telegraph').textContent = 'Opened ' + target;
  } else if (target === 'refresh') {
    loadAll(); $('telegraph').textContent = 'Refresh requested';
  } else if (target === 'help') {
    $('telegraph').textContent = 'Commands: overview, catalog, evals, deploy, settings, refresh';
  } else {
    $('telegraph').textContent = 'Unknown local command. Type help.';
  }
}
async function loadAll() {
  await Promise.allSettled([loadStatus(), loadBackends(), loadEvents(), loadTunnels(), loadProfiles(), loadCatalog()]);
}
function initDelegation() {
  onEl(document, 'click', (event) => {
    const target = event.target;
    const confirm = target.closest('[data-confirm]');
    const refresh = target.closest('[data-refresh]');
    if (refresh) { refresh.dataset.refresh === 'evals' ? loadEvals() : loadAll(); return; }
    const opener = target.closest('[data-open-server]');
    if (opener) { showServer(opener.dataset.openServer); return; }
    const toggle = confirm && confirm.closest('[data-server-toggle]');
    if (toggle) {
      const name = toggle.dataset.serverToggle;
      const enabled = toggle.getAttribute('aria-checked') !== 'true';
      confirmAction(enabled ? 'enable' : 'disable', name, () => toggleServer(name, enabled));
      return;
    }
    const tunnel = confirm && confirm.closest('[data-tunnel-provider]');
    if (tunnel) {
      const provider = tunnel.dataset.tunnelProvider, action = tunnel.dataset.tunnelAction;
      confirmAction(action + '-tunnel', provider, () => changeTunnel(provider, action, tunnel));
      return;
    }
    const deploy = target.closest('[data-deploy-format]');
    if (deploy) { selectDeploy(deploy.dataset.deployFormat); return; }
    if (target.closest('[data-close-drawer]')) closeDrawer();
  });
}
function teardown() {
  state.destroyed = true;
  state.wsGeneration++;
  clearWsRetry();
  timers.forEach((id) => { clearTimeout(id); clearInterval(id); });
  timers.clear();
  controllers.forEach((controller) => controller.abort());
  controllers.clear();
  listeners.forEach(([target, type, fn, options]) => target.removeEventListener(type, fn, options));
  listeners.length = 0;
  state.wsConnecting = false; state.wsOpen = false;
  if (state.ws) { const socket = state.ws; state.ws = null; socket.onclose = null; socket.close(1000); }
}
async function init() {
  initTabNavigation();
  initDelegation();
  onEl($('catalog-search'), 'input', renderCatalog);
  onEl($('catalog-profile'), 'change', renderCatalog);
  onEl($('catalog-status'), 'change', renderCatalog);
  onEl($('credentials-save'), 'click', () => confirmAction('save-credentials', state.drawerServer && state.drawerServer.name, saveCredentials));
  onEl($('detail-toggle'), 'click', () => {
    const server = state.drawerServer;
    if (server) confirmAction(server.enabled ? 'disable' : 'enable', server.name, () => toggleServer(server.name, !server.enabled));
  });
  onEl($('confirm-cancel'), 'click', closeConfirm);
  onEl($('confirm-ok'), 'click', runConfirmed);
  onEl($('confirm'), 'click', (event) => { if (event.target === $('confirm')) closeConfirm(); });
  onEl($('settings-save'), 'click', saveSettings);
  onEl($('settings-form'), 'submit', (event) => { event.preventDefault(); saveSettings(); });
  onEl($('deploy-copy'), 'click', copyDeploy);
  onEl($('auth-oauth'), 'click', beginOAuth);
  onEl($('auth-key-submit'), 'click', submitApiKey);
  onEl($('auth-key'), 'keydown', (event) => { if (event.key === 'Enter') submitApiKey(); });
  onEl($('cmd-input'), 'keydown', (event) => {
    if (event.key === 'Enter') { event.preventDefault(); runCommand(event.target.value); event.target.value = ''; }
  });
  onEl(document, 'keydown', (event) => {
    if (event.key === 'Escape') { if (!$('confirm').hidden) closeConfirm(); else if (!$('detail-drawer').hidden) closeDrawer(); }
    if ((event.ctrlKey || event.metaKey) && event.key === 'k') { event.preventDefault(); $('cmd-input').focus(); }
    if (!event.ctrlKey && !event.metaKey && !event.altKey && /^[1-5]$/.test(event.key) && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) activateView(views[Number(event.key) - 1], true);
  });
  onEl(window, 'resize', drawTopology);
  onEl(window, 'beforeunload', teardown);
  try { await finishOAuth(); } catch (error) { showToast(errorMessage(error), 'bad'); }
  const initial = location.hash.slice(1);
  activateView(views.includes(initial) ? initial : 'dashboard', false);
  await loadAll();
  connectWebSocket();
  trackedInterval(loadStatus, 10000);
  trackedInterval(loadBackends, 15000);
  trackedInterval(loadEvents, 10000);
  trackedInterval(loadTunnels, 30000);
}
onEl(document, 'DOMContentLoaded', init);
"""


def render_dashboard(ws_port: int = 9092) -> str:
    """Render the self-contained operator dashboard for the configured WS port."""

    config = f"<script>window.KATER_CONFIG={{wsPort:{int(ws_port)}}};</script>\n"
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        "<title>Kater — Gateway control plane</title>\n"
        '<meta name="color-scheme" content="dark">\n'
        '<meta name="theme-color" content="#0b0e11">\n'
        f"<style>{_CSS}</style>\n"
        "</head>\n<body>\n"
        f"{_HTML}\n"
        f"{config}"
        f"<script>{_JS}</script>\n"
        "</body>\n</html>\n"
    )
