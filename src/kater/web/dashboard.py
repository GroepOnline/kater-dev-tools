from __future__ import annotations

_CSS = r"""
@import url("https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap");

:root {
  /* Cool near-black canvas with layered luminance steps (no color hierarchy). */
  --bg: #0b0d10;
  --surface: #111419;
  --surface-2: #171b22;
  --elevated: #1d222c;
  --border: rgba(255,255,255,0.07);
  --border-strong: rgba(255,255,255,0.13);
  --text: #e6e9ef;
  --text-muted: #98a1b1;
  --text-faint: #5d6675;
  /* One disciplined accent: teal = gateway / flow. Used as punctuation only. */
  --accent: #2dd4bf;
  --accent-dim: rgba(45,212,191,0.14);
  --accent-line: rgba(45,212,191,0.35);
  /* Inverted, near-white primary CTA (brand color stays as accent, not paint). */
  --cta: #f2f4f7;
  --cta-text: #0b0d10;
  /* Semantics: vivid, small-area, paired with icon + label (never color-alone). */
  --ok: #3ddc97;
  --ok-dim: rgba(61,220,151,0.13);
  --warn: #e8b84a;
  --warn-dim: rgba(232,184,74,0.13);
  --err: #f87171;
  --err-dim: rgba(248,113,113,0.13);
  --info: #6cb6ff;
  --idle: #5d6675;

  --sans: "Instrument Sans", system-ui, -apple-system, sans-serif;
  --mono: "JetBrains Mono", ui-monospace, "SF Mono", monospace;
  --sidebar-w: 216px;
  --cmd-h: 38px;
  --radius: 6px;
  --radius-sm: 4px;
  color-scheme: dark;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; overflow: hidden; }
body {
  font-family: var(--sans);
  font-size: 13px;
  line-height: 1.5;
  color: var(--text);
  background: var(--bg);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
.tnum { font-variant-numeric: tabular-nums; }

::selection { background: var(--accent-dim); }

/* Keep focused controls clear of host/topbar chrome (IDE browser overlays). */
a, button, input, select, textarea, [role="switch"], [tabindex] {
  scroll-margin-top: 64px;
}

::-webkit-scrollbar { width: 9px; height: 9px; }
::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 6px; }
::-webkit-scrollbar-track { background: transparent; }

a:focus-visible, button:focus-visible, input:focus-visible,
select:focus-visible, [role="switch"]:focus-visible, [tabindex]:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: var(--radius-sm);
}

.sr-only {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0;
}
.skip-link:focus {
  position: fixed; left: 12px; top: 8px; z-index: 999;
  width: auto; height: auto; padding: 8px 12px; clip: auto; overflow: visible;
  background: var(--elevated); color: var(--text); border: 1px solid var(--border-strong);
  text-decoration: none; border-radius: var(--radius-sm);
}

@media (prefers-reduced-motion: no-preference) {
  .interactive {
    transition: background-color 120ms ease, border-color 120ms ease,
                color 120ms ease, transform 80ms ease, opacity 120ms ease;
  }
  .interactive:active { transform: scale(0.985); }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    transition-duration: 0.001ms !important;
  }
}

#boot { display: none; }

/* ── App shell ──────────────────────────────────────────────── */
#app {
  display: grid;
  grid-template-columns: var(--sidebar-w) 1fr;
  height: 100vh;
}

.sidebar {
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  background: var(--surface);
  min-height: 0;
}
.sidebar-brand {
  padding: 18px 16px 14px;
  border-bottom: 1px solid var(--border);
}
.brand-row { display: flex; align-items: center; gap: 9px; }
.brand-mark {
  width: 22px; height: 22px; flex-shrink: 0;
  border-radius: 6px;
  background: linear-gradient(150deg, var(--accent), #119e8c);
  position: relative;
  box-shadow: 0 0 0 1px rgba(45,212,191,0.25), 0 4px 10px rgba(45,212,191,0.18);
}
.brand-mark::after {
  content: ""; position: absolute; inset: 6px;
  border-radius: 2px;
  border: 1.5px solid rgba(11,13,16,0.85);
  border-right-color: transparent; border-bottom-color: transparent;
}
.brand-name {
  font-family: var(--sans);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--text);
}
.brand-meta {
  margin-top: 8px;
  font-family: var(--mono);
  font-size: 10.5px;
  color: var(--text-faint);
  letter-spacing: 0.02em;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  padding: 10px;
  gap: 2px;
  flex: 1;
}
.nav-section {
  font-family: var(--mono); font-size: 9.5px; font-weight: 600;
  color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.08em;
  padding: 12px 10px 5px;
}
.tab {
  display: flex; align-items: center; gap: 9px;
  width: 100%; padding: 8px 10px;
  border: none; border-radius: var(--radius-sm);
  background: transparent; color: var(--text-muted);
  font-family: var(--sans); font-size: 13px; font-weight: 500;
  text-align: left; cursor: pointer;
  position: relative;
}
.tab:hover { background: var(--surface-2); color: var(--text); }
.tab.active { background: var(--surface-2); color: var(--text); }
.tab.active::before {
  content: ""; position: absolute; left: 0; top: 6px; bottom: 6px;
  width: 2px; border-radius: 2px; background: var(--accent);
}
.tab-icon { width: 15px; height: 15px; flex-shrink: 0; opacity: 0.85; }
.tab.active .tab-icon { opacity: 1; color: var(--accent); }
.tab-label { flex: 1; }
.tab-kbd {
  font-family: var(--mono); font-size: 10px; color: var(--text-faint);
  border: 1px solid var(--border); border-radius: 3px; padding: 0 4px; line-height: 16px;
}

.sidebar-foot {
  padding: 12px 14px;
  border-top: 1px solid var(--border);
  display: flex; flex-direction: column; gap: 8px;
}
.auth-badge {
  display: flex; align-items: center; gap: 8px;
  font-family: var(--mono); font-size: 11px; color: var(--text-muted);
}
.auth-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--ok); flex-shrink: 0; }
.foot-hint {
  font-family: var(--mono); font-size: 10px; color: var(--text-faint);
  display: flex; align-items: center; gap: 6px;
}
.foot-hint kbd {
  font-family: var(--mono); font-size: 9.5px;
  border: 1px solid var(--border); border-radius: 3px; padding: 0 4px; color: var(--text-muted);
}

/* ── Workspace ──────────────────────────────────────────────── */
.workspace { display: flex; flex-direction: column; min-width: 0; min-height: 0; }
.page-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; padding: 11px 18px;
  border-bottom: 1px solid var(--border);
  background: var(--bg);
}
.page-title {
  font-family: var(--sans); font-size: 14px; font-weight: 600;
  color: var(--text); letter-spacing: -0.01em;
}
.toolbar-right { display: flex; align-items: center; gap: 12px; }
.profile-pills { display: flex; gap: 5px; flex-wrap: wrap; }
.pill {
  font-family: var(--mono); font-size: 11px;
  padding: 4px 9px; border-radius: 999px;
  border: 1px solid var(--border); color: var(--text-muted);
  cursor: pointer; user-select: none; background: transparent;
}
.pill:hover { color: var(--text); border-color: var(--border-strong); }
.pill.active { background: var(--accent-dim); color: var(--accent); border-color: var(--accent-line); }
.palette-trigger {
  display: flex; align-items: center; gap: 8px;
  font-family: var(--sans); font-size: 12px; color: var(--text-muted);
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-sm); padding: 5px 9px; cursor: pointer;
}
.palette-trigger:hover { border-color: var(--border-strong); color: var(--text); }
.palette-trigger kbd {
  font-family: var(--mono); font-size: 10px; color: var(--text-faint);
  border: 1px solid var(--border); border-radius: 3px; padding: 0 4px;
}

.page-body { flex: 1; min-height: 0; overflow: hidden; display: flex; flex-direction: column; }

.view { display: none; flex: 1; min-height: 0; overflow: hidden; }
.view.active { display: flex; flex-direction: column; }
.view-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 18px 0;
}
.view-title { font-family: var(--sans); font-size: 13px; font-weight: 600; color: var(--text); }
.view-scroll {
  flex: 1; overflow-y: auto; min-height: 0;
  scrollbar-width: thin; scrollbar-color: var(--border-strong) transparent;
}
.view-empty {
  padding: 40px 18px; text-align: center;
  font-family: var(--mono); font-size: 12px; color: var(--text-muted);
}
.view-empty-link {
  color: var(--accent); text-decoration: underline; cursor: pointer;
  background: none; border: none; font: inherit; padding: 0; margin-left: 4px;
}
.view-empty-link:hover { color: var(--text); }

/* ── PR control (§3/§4/§6/§7) ──────────────────────────────── */
.pr-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; padding: 14px 18px; }
.pr-card {
  border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px;
  background: var(--panel); display: flex; flex-direction: column; gap: 8px;
}
.pr-card .pr-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.pr-card .pr-title { font-weight: 600; font-size: 13px; line-height: 1.3; }
.pr-card .pr-meta { font-family: var(--mono); font-size: 11px; color: var(--text-muted); }
.pr-card .pr-reasons { display: flex; flex-wrap: wrap; gap: 5px; }
.pr-card pre { margin: 0; font-family: var(--mono); font-size: 10px; color: var(--text-muted); white-space: pre-wrap; }
.pr-verdict { font-family: var(--mono); font-weight: 700; font-size: 12px; padding: 2px 8px; border-radius: 999px; }
.pr-verdict.PASS { background: rgba(34,197,94,.15); color: #4ade80; }
.pr-verdict.WARN { background: rgba(234,179,8,.15); color: #facc15; }
.pr-verdict.BLOCK { background: rgba(239,68,68,.15); color: #f87171; }
.pr-merge-btn { align-self: flex-start; margin-top: 2px; }
.pr-head-note { font-family: var(--mono); font-size: 10px; color: var(--text-muted); }

/* ── Overview ───────────────────────────────────────────────── */
#view-dashboard { padding: 14px 18px 0; gap: 14px; }

.exc-strip {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.exc-item {
  display: inline-flex; align-items: center; gap: 7px;
  font-family: var(--mono); font-size: 11.5px; color: var(--text-muted);
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 999px; padding: 5px 12px; cursor: pointer;
}
.exc-item:hover { border-color: var(--border-strong); color: var(--text); }
.exc-item.active { border-color: var(--accent-line); color: var(--text); background: var(--surface-2); }
.exc-item .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--idle); }
.exc-item.ok .dot { background: var(--ok); }
.exc-item.warn .dot { background: var(--warn); }
.exc-item.err .dot { background: var(--err); }
.exc-item .n { color: var(--text); font-weight: 600; }
.exc-spacer { flex: 1; }
.live-indicator {
  display: inline-flex; align-items: center; gap: 7px;
  font-family: var(--mono); font-size: 11px; color: var(--text-muted);
}
.live-dot {
  width: 7px; height: 7px; border-radius: 50%; background: var(--ok); position: relative;
}
.live-dot.stale { background: var(--idle); }
.live-dot::after {
  content: ''; position: absolute; inset: -3px; border-radius: 50%;
  border: 1px solid var(--ok); opacity: 0;
}
@media (prefers-reduced-motion: no-preference) {
  .live-dot:not(.stale)::after { animation: pulse 2.4s ease-out infinite; }
}
@keyframes pulse {
  0% { transform: scale(0.7); opacity: 0.7; }
  100% { transform: scale(2); opacity: 0; }
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.kpi {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 13px 15px 11px;
  display: flex; flex-direction: column; gap: 4px;
  min-height: 96px;
}
.kpi-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.kpi-label {
  font-family: var(--mono); font-size: 10px; color: var(--text-faint);
  text-transform: uppercase; letter-spacing: 0.07em;
}
.kpi-value {
  font-family: var(--mono); font-size: 27px; font-weight: 600; color: var(--text);
  letter-spacing: -0.02em; line-height: 1.1;
}
.kpi-value.warn { color: var(--warn); }
.kpi-value.err { color: var(--err); }
.kpi-value .unit { font-size: 14px; color: var(--text-muted); font-weight: 500; }
.kpi-sub { font-family: var(--mono); font-size: 10.5px; color: var(--text-muted); }
.kpi-spark { width: 100%; height: 30px; margin-top: auto; display: block; }
.trend {
  display: inline-flex; align-items: center; gap: 3px;
  font-family: var(--mono); font-size: 10.5px; font-weight: 600;
  padding: 1px 6px; border-radius: 999px;
}
.trend:empty { display: none; }
.trend.pos { color: var(--ok); background: var(--ok-dim); }
.trend.neg { color: var(--err); background: var(--err-dim); }
.trend.flat { color: var(--text-faint); background: rgba(125,133,150,0.1); }

.spark-line { fill: none; stroke-width: 1.6; }
.spark-area { stroke: none; }
.spark-dot { r: 2.4; }

.dash-cols {
  flex: 1; min-height: 0;
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 12px;
  padding-bottom: 12px;
}
.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  display: flex; flex-direction: column; min-height: 0; overflow: hidden;
}
.panel-head {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  padding: 11px 14px; border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.panel-title {
  font-family: var(--sans); font-size: 12px; font-weight: 600;
  color: var(--text); display: flex; align-items: center; gap: 8px;
}
.panel-meta { font-family: var(--mono); font-size: 11px; color: var(--text-faint); }
.panel-actions { display: flex; align-items: center; gap: 6px; }
.mini-btn {
  font-family: var(--mono); font-size: 10.5px;
  padding: 3px 8px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: transparent; color: var(--text-muted);
  cursor: pointer;
}
.mini-btn:hover { border-color: var(--border-strong); color: var(--text); }
.mini-btn.active { border-color: var(--accent-line); color: var(--accent); background: var(--accent-dim); }
.pr-header-actions { display: flex; align-items: center; gap: 12px; }

.server-map { flex: 1; overflow: auto; min-height: 0; }
.route-table { width: 100%; border-collapse: collapse; }
.route-table th {
  position: sticky; top: 0; z-index: 1;
  background: var(--surface);
  text-align: left; padding: 8px 14px;
  font-family: var(--mono); font-size: 9.5px; font-weight: 600;
  color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.06em;
  border-bottom: 1px solid var(--border);
}
.route-table td {
  padding: 10px 14px; border-bottom: 1px solid var(--border);
  font-size: 13px;
}
.route-table tbody tr { cursor: pointer; }
.route-table tbody tr:hover td { background: var(--surface-2); }
.route-table tbody tr.sel td { background: var(--accent-dim); }
.route-table tbody tr.sel td:first-child { box-shadow: inset 2px 0 0 var(--accent); }
.route-name { font-family: var(--mono); font-weight: 500; color: var(--text); }

.status-chip { display: inline-flex; align-items: center; gap: 7px; }
.status-dot {
  display: inline-block; width: 7px; height: 7px; border-radius: 50%;
  background: var(--idle); flex-shrink: 0;
}
.status-dot.ok { background: var(--ok); box-shadow: 0 0 0 3px var(--ok-dim); }
.status-dot.warn { background: var(--warn); box-shadow: 0 0 0 3px var(--warn-dim); }
.status-dot.err { background: var(--err); box-shadow: 0 0 0 3px var(--err-dim); }
.status-dot.off { background: var(--idle); }
.status-dot.info { background: var(--info); box-shadow: 0 0 0 3px rgba(108,182,255,0.13); }
.status-label { font-family: var(--mono); font-size: 11.5px; color: var(--text-muted); }

/* Activity log */
.log-panel .panel-head { gap: 8px; }
.latency-wrap { padding: 8px 12px 6px; border-bottom: 1px solid var(--border); flex-shrink: 0; }
.latency-cap {
  display: flex; align-items: center; justify-content: space-between;
  font-family: var(--mono); font-size: 9.5px; color: var(--text-faint);
  text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 5px;
}
#latency-strip { width: 100%; height: 32px; display: block; }
.telemetry-stream {
  flex: 1; overflow-y: auto; padding: 6px 8px; min-height: 0;
  font-family: var(--mono); font-size: 11px;
}
.telemetry-stream.errors-only .tlm-row:not(.is-err) { display: none; }
.tlm-empty { padding: 24px 10px; text-align: center; color: var(--text-faint); }
.tlm-row {
  display: flex; align-items: center; gap: 8px; padding: 4px 6px;
  white-space: nowrap; border-radius: var(--radius-sm);
}
.tlm-row.faded { opacity: 0.5; }
.tlm-row:hover { background: var(--surface-2); }
.tlm-row.new { animation: tlm-in 220ms ease-out; }
@keyframes tlm-in { from { opacity: 0; transform: translateY(-3px); } to { opacity: 1; transform: translateY(0); } }
.tlm-time { color: var(--text-faint); flex-shrink: 0; }
.tlm-icon { width: 12px; flex-shrink: 0; text-align: center; }
.tlm-icon.ok { color: var(--ok); }
.tlm-icon.err { color: var(--err); }
.tlm-name { overflow: hidden; text-overflow: ellipsis; color: var(--text); }
.tlm-count {
  font-size: 9.5px; color: var(--accent); background: var(--accent-dim);
  border-radius: 999px; padding: 0 5px; flex-shrink: 0;
}
.tlm-count:empty { display: none; }
.tlm-ms { margin-left: auto; flex-shrink: 0; }
.lat-pill {
  font-family: var(--mono); font-size: 10px;
  padding: 1px 6px; border-radius: 3px; border: 1px solid transparent;
}
.lat-pill.fast { color: var(--ok); border-color: var(--ok-dim); background: var(--ok-dim); }
.lat-pill.mid { color: var(--warn); border-color: var(--warn-dim); background: var(--warn-dim); }
.lat-pill.slow { color: var(--err); border-color: var(--err-dim); background: var(--err-dim); }

.tunnel-bar {
  display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
  padding: 11px 14px; margin-bottom: 12px;
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
}
.tunnel-bar .panel-title { margin-right: 4px; }
.tunnel-item { display: flex; align-items: center; gap: 9px; }
.tunnel-name { font-family: var(--mono); font-size: 12px; color: var(--text-muted); }
.btn-tunnel {
  font-family: var(--mono); font-size: 11px;
  padding: 4px 11px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: transparent;
  color: var(--text-muted); cursor: pointer;
}
.btn-tunnel:hover { border-color: var(--border-strong); color: var(--text); }
.btn-tunnel.active { border-color: var(--ok); color: var(--ok); background: var(--ok-dim); }

/* ── Catalog ────────────────────────────────────────────────── */
.catalog-toolbar { padding: 14px 18px 4px; display: flex; flex-direction: column; gap: 10px; }
#catalog-search {
  max-width: 380px;
  background: var(--surface); border: 1px solid var(--border);
}
.facet-row { display: flex; flex-wrap: wrap; gap: 6px; }
.facet {
  font-family: var(--mono); font-size: 11px;
  padding: 4px 10px; border-radius: 999px;
  border: 1px solid var(--border); background: transparent;
  color: var(--text-muted); cursor: pointer;
}
.facet:hover { color: var(--text); border-color: var(--border-strong); }
.facet.active { border-color: var(--accent-line); color: var(--accent); background: var(--accent-dim); }
.server-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px; padding: 12px 18px 18px;
}
.server-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 15px; cursor: pointer;
}
.server-card:hover { background: var(--surface-2); border-color: var(--border-strong); }
.server-card-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 9px; }
.server-card-name { font-family: var(--mono); font-size: 13px; font-weight: 600; color: var(--text); }
.server-card-desc { font-size: 12px; color: var(--text-muted); line-height: 1.5; min-height: 36px; }

.server-card-meta {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  margin-top: 10px; font-family: var(--mono); font-size: 10.5px; color: var(--text-faint);
}
.cost-dots { display: inline-flex; gap: 3px; align-items: center; }
.cost-dots i {
  display: inline-block; width: 5px; height: 5px; border-radius: 50%;
  background: var(--border-strong);
}
.cost-dots i.on { background: var(--accent); }
.route-meta { font-family: var(--mono); font-size: 11px; color: var(--text-muted); }
.route-cost { font-family: var(--mono); font-size: 11px; color: var(--text-faint); }

.toggle-switch {
  width: 36px; height: 20px; border-radius: 999px;
  background: var(--border-strong); position: relative; cursor: pointer; flex-shrink: 0;
}
.toggle-switch::after {
  content: ""; position: absolute; top: 2px; left: 2px;
  width: 16px; height: 16px; border-radius: 50%; background: var(--text-faint);
  transition: left 140ms ease, background 140ms ease;
}
.toggle-switch.on { background: var(--ok); }
.toggle-switch.on::after { left: 18px; background: #fff; }
.toggle-switch.pending { background: var(--warn); }
.toggle-switch.pending::after { left: 18px; background: #fff; }

.badges { display: flex; gap: 5px; flex-wrap: wrap; margin-bottom: 9px; }
.badge {
  font-family: var(--mono); font-size: 10px; font-weight: 500;
  padding: 2px 7px; border-radius: 999px;
  border: 1px solid var(--border); color: var(--text-muted);
  text-transform: lowercase;
}
.badge.stdio { border-color: var(--ok-dim); color: var(--ok); }
.badge.sse, .badge.http { border-color: var(--accent-line); color: var(--accent); }
.badge.native { border-color: var(--accent-line); color: var(--accent); }
.badge.high { border-color: var(--err-dim); color: var(--err); }
.badge.medium { border-color: var(--warn-dim); color: var(--warn); }
.badge.low { border-color: var(--ok-dim); color: var(--ok); }

/* ── Evals ──────────────────────────────────────────────────── */
.eval-summary {
  display: flex; gap: 12px; padding: 14px 18px; flex-wrap: wrap;
}
.eval-stat {
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 10px 16px; min-width: 110px;
}
.eval-stat .big-num { font-family: var(--mono); font-size: 22px; font-weight: 600; color: var(--text); display: block; letter-spacing: -0.02em; }
.eval-stat .lbl { font-family: var(--mono); font-size: 10px; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.06em; }
.eval-table { width: 100%; border-collapse: collapse; }
.eval-table th {
  text-align: left; padding: 9px 18px;
  font-family: var(--mono); font-size: 9.5px; font-weight: 600;
  color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.06em;
  border-bottom: 1px solid var(--border);
  position: sticky; top: 0; background: var(--bg);
}
.eval-table td {
  padding: 10px 18px; border-bottom: 1px solid var(--border);
  font-family: var(--mono); font-size: 12px;
}
.eval-table tr:hover td { background: var(--surface); }
.hbar { display: inline-flex; align-items: center; gap: 8px; }
.hbar-track {
  width: 64px; height: 6px; border-radius: 3px;
  background: var(--border-strong); overflow: hidden;
}
.hbar-fill { display: block; height: 100%; border-radius: 3px; }
.hbar-label { color: var(--text-muted); min-width: 34px; }

/* ── Deploy ─────────────────────────────────────────────────── */
.code-tabs { display: flex; gap: 5px; padding: 14px 18px 0; flex-wrap: wrap; }
.code-tab {
  font-family: var(--mono); font-size: 11px;
  padding: 6px 12px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: transparent;
  color: var(--text-muted); cursor: pointer;
}
.code-tab:hover { color: var(--text); }
.code-tab.active { border-color: var(--accent-line); color: var(--accent); background: var(--accent-dim); }
.code-preview { padding: 14px 18px 18px; }
.code-desc { font-family: var(--mono); font-size: 12px; color: var(--text-muted); margin-bottom: 9px; }
.code-wrap { position: relative; }
.code-block {
  margin: 0; padding: 14px;
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
  font-family: var(--mono); font-size: 11.5px; line-height: 1.6;
  overflow: auto; max-height: 60vh; white-space: pre;
}
.code-copy {
  position: absolute; top: 9px; right: 9px;
  font-family: var(--mono); font-size: 10px;
  padding: 5px 9px; border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--elevated); color: var(--text-muted); cursor: pointer;
}
.code-copy:hover { color: var(--text); border-color: var(--border-strong); }

/* ── Settings ───────────────────────────────────────────────── */
.settings-form { padding: 18px; max-width: 520px; }
.form-field { margin-bottom: 18px; }
.form-label {
  display: block; margin-bottom: 7px;
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.06em;
}
.form-input, .form-select {
  width: 100%; padding: 9px 11px;
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--surface); color: var(--text);
  font-family: var(--mono); font-size: 13px;
}
.form-input:focus, .form-select:focus { border-color: var(--accent-line); outline: none; }
.btn-save {
  font-family: var(--sans); font-size: 13px; font-weight: 600;
  padding: 9px 16px; border-radius: var(--radius-sm);
  border: 1px solid var(--cta); background: var(--cta); color: var(--cta-text);
  cursor: pointer;
}
.btn-save:hover { opacity: 0.9; }

/* ── Command bar ────────────────────────────────────────────── */
.command-bar {
  height: var(--cmd-h); min-height: var(--cmd-h);
  display: flex; align-items: center; gap: 9px;
  padding: 0 14px; border-top: 1px solid var(--border);
  background: var(--surface);
}
.cmd-prompt { font-family: var(--mono); color: var(--accent); }
#cmd-input {
  flex: 1; border: none; background: transparent; outline: none;
  font-family: var(--mono); font-size: 12px; color: var(--text);
}
#cmd-input::placeholder { color: var(--text-faint); }
.cmd-hint {
  font-family: var(--mono); font-size: 10px; color: var(--text-faint);
  padding: 2px 6px; border: 1px solid var(--border); border-radius: 3px;
}

/* ── Command palette ────────────────────────────────────────── */
.palette-overlay {
  position: fixed; inset: 0; z-index: 140;
  display: none; align-items: flex-start; justify-content: center;
  background: rgba(6,7,9,0.6); padding: 12vh 20px 20px;
  backdrop-filter: blur(2px);
}
.palette-overlay.show { display: flex; }
.palette {
  width: min(560px, 96vw);
  background: var(--elevated); border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  box-shadow: 0 16px 48px rgba(0,0,0,0.5), 0 2px 8px rgba(0,0,0,0.4);
  overflow: hidden;
}
@media (prefers-reduced-motion: no-preference) {
  .palette-overlay.show .palette { animation: pop 160ms cubic-bezier(0.175,0.885,0.32,1.1); }
}
@keyframes pop { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: translateY(0); } }
.palette-input {
  width: 100%; padding: 15px 16px;
  border: none; border-bottom: 1px solid var(--border);
  background: transparent; color: var(--text);
  font-family: var(--sans); font-size: 15px; outline: none;
}
.palette-input::placeholder { color: var(--text-faint); }
.palette-results { max-height: 340px; overflow-y: auto; padding: 6px; }
.palette-group {
  font-family: var(--mono); font-size: 9.5px; font-weight: 600;
  color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.07em;
  padding: 8px 10px 4px;
}
.palette-item {
  display: flex; align-items: center; gap: 10px;
  padding: 9px 10px; border-radius: var(--radius-sm); cursor: pointer;
}
.palette-item.sel { background: var(--accent-dim); }
.palette-item.sel .pi-label { color: var(--accent); }
.pi-label { flex: 1; font-size: 13px; color: var(--text); }
.pi-hint { font-family: var(--mono); font-size: 10.5px; color: var(--text-faint); }
.palette-empty { padding: 22px 12px; text-align: center; font-family: var(--mono); font-size: 12px; color: var(--text-faint); }
.palette-foot {
  display: flex; gap: 16px; padding: 8px 14px;
  border-top: 1px solid var(--border);
  font-family: var(--mono); font-size: 10px; color: var(--text-faint);
}
.palette-foot kbd {
  border: 1px solid var(--border); border-radius: 3px; padding: 0 4px; margin-right: 3px; color: var(--text-muted);
}

/* ── Detail drawer ──────────────────────────────────────────── */
.detail-panel {
  position: fixed; top: 0; right: 0; bottom: var(--cmd-h);
  width: 380px; z-index: 50;
  background: var(--surface);
  border-left: 1px solid var(--border-strong);
  box-shadow: -12px 0 32px rgba(0,0,0,0.35);
  transform: translateX(100%);
  transition: transform 180ms cubic-bezier(0.175,0.885,0.32,1.05);
  display: flex; flex-direction: column; overflow-y: auto;
}
.detail-panel.open { transform: translateX(0); }
.detail-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 18px; border-bottom: 1px solid var(--border);
  position: sticky; top: 0; background: var(--surface); z-index: 1;
}
.detail-name { font-family: var(--mono); font-size: 16px; font-weight: 600; color: var(--text); }
.detail-close {
  width: 28px; height: 28px; border: 1px solid var(--border);
  border-radius: var(--radius-sm); display: flex; align-items: center; justify-content: center;
  cursor: pointer; color: var(--text-muted); font-size: 18px;
}
.detail-close:hover { color: var(--text); border-color: var(--border-strong); }
.detail-section { padding: 14px 18px; border-bottom: 1px solid var(--border); }
.detail-label {
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.06em;
  margin-bottom: 7px;
}
.detail-value { font-family: var(--mono); font-size: 12px; word-break: break-all; color: var(--text); }
.detail-link { color: var(--accent); font-family: var(--mono); font-size: 12px; }
.detail-status { font-family: var(--mono); font-size: 12px; color: var(--text-muted); line-height: 1.5; }
.detail-status.ready { color: var(--ok); }
.detail-status.needs { color: var(--warn); }
.detail-status.off { color: var(--text-faint); }
.detail-actions { padding: 16px 18px; display: flex; gap: 9px; }
.btn-action {
  flex: 1; padding: 9px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: transparent;
  font-family: var(--mono); font-size: 11.5px; cursor: pointer; color: var(--text);
}
.btn-action:hover { border-color: var(--border-strong); }
.btn-action.primary { border-color: var(--ok); color: var(--ok); }
.btn-action.danger { border-color: var(--err); color: var(--err); }

/* ── Modal ──────────────────────────────────────────────────── */
.modal-overlay {
  position: fixed; inset: 0; z-index: 130;
  display: none; align-items: center; justify-content: center;
  background: rgba(6,7,9,0.72); padding: 20px;
}
.modal-overlay.show { display: flex; }
.modal-card {
  width: min(460px, 96vw);
  background: var(--elevated); border: 1px solid var(--border-strong); border-radius: var(--radius);
  padding: 22px; box-shadow: 0 16px 48px rgba(0,0,0,0.5);
}
.modal-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.modal-title { font-family: var(--mono); font-size: 15px; font-weight: 600; }
.modal-sub { color: var(--text-muted); font-size: 13px; margin-bottom: 16px; }
.modal-actions { display: flex; gap: 9px; margin-top: 10px; }
.modal-actions .btn-action { flex: 1; text-transform: none; }
.modal-actions .btn-action#cred-provider { flex: 0 0 auto; text-decoration: none; display: inline-flex; align-items: center; justify-content: center; }

/* ── Auth gate ──────────────────────────────────────────────── */
#auth-gate {
  position: fixed; inset: 0; z-index: 120;
  display: none; align-items: center; justify-content: center;
  background: rgba(6,7,9,0.92); padding: 20px;
}
#auth-gate.show { display: flex; }
.auth-card {
  width: min(420px, 92vw);
  background: var(--elevated); border: 1px solid var(--border-strong); border-radius: var(--radius);
  padding: 28px;
}
.auth-card h2 { font-size: 17px; font-weight: 600; margin-bottom: 8px; }
.auth-card p { color: var(--text-muted); font-size: 13px; margin-bottom: 18px; }
.auth-card input {
  width: 100%; padding: 9px 11px; margin-bottom: 13px;
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--surface); color: var(--text); font-family: var(--mono); font-size: 13px;
}
.auth-actions { display: flex; gap: 9px; flex-wrap: wrap; }

/* ── Toast ──────────────────────────────────────────────────── */
.toast-container {
  position: fixed; bottom: calc(var(--cmd-h) + 12px); left: 50%;
  transform: translateX(-50%); z-index: 200;
  display: flex; flex-direction: column; gap: 7px;
}
.toast {
  font-family: var(--mono); font-size: 12px;
  padding: 9px 14px; border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
  background: var(--elevated); color: var(--text);
  box-shadow: 0 8px 24px rgba(0,0,0,0.4);
}
@media (prefers-reduced-motion: no-preference) {
  .toast { animation: pop 150ms ease-out; }
}
.toast.success { border-color: var(--ok); }
.toast.error { border-color: var(--err); }

.big-num { font-family: var(--mono); font-weight: 600; }
.big-sub { font-family: var(--mono); font-size: 11px; color: var(--text-muted); }

@media (max-width: 1080px) {
  .dash-cols { grid-template-columns: 1fr; }
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 820px) {
  #app { grid-template-columns: 1fr; grid-template-rows: auto 1fr; }
  .sidebar { border-right: none; border-bottom: 1px solid var(--border); }
  .sidebar-nav { flex-direction: row; overflow-x: auto; }
  .nav-section { display: none; }
  .tab-kbd { display: none; }
  .profile-pills, .palette-trigger { display: none; }
  .detail-panel { width: 100%; }
  .kpi-grid { grid-template-columns: 1fr; }
}
"""


_HTML_SHELL_TOP = r"""
<div id="boot"></div>
<a href="#main-content" class="sr-only skip-link">Skip to content</a>

<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <defs>
    <linearGradient id="grad-teal" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#2dd4bf" stop-opacity="0.34"/>
      <stop offset="100%" stop-color="#2dd4bf" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="grad-ok" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#3ddc97" stop-opacity="0.32"/>
      <stop offset="100%" stop-color="#3ddc97" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="grad-warn" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#e8b84a" stop-opacity="0.32"/>
      <stop offset="100%" stop-color="#e8b84a" stop-opacity="0"/>
    </linearGradient>
  </defs>
</svg>

<div id="auth-gate">
  <div class="auth-card">
    <h2>Sign in</h2>
    <p>This gateway requires authentication before you can manage servers.</p>
    <label for="auth-key-input" class="sr-only">API key</label>
    <input type="password" id="auth-key-input" placeholder="API key" autocomplete="off">
    <div class="auth-actions">
      <button class="btn-save" id="auth-oauth-btn" type="button">OAuth</button>
      <button class="btn-save" id="auth-key-btn" type="button">Use API key</button>
    </div>
  </div>
</div>

<div id="app">
  <aside class="sidebar">
    <div class="sidebar-brand">
      <div class="brand-row">
        <div class="brand-mark" aria-hidden="true"></div>
        <div class="brand-name">Kater</div>
      </div>
      <div class="brand-meta">MCP gateway · <span id="version-tag">v0.0.0</span></div>
    </div>
    <nav class="sidebar-nav" aria-label="Views">
      <div class="nav-section">Operate</div>
      <button class="tab active interactive" data-view="dashboard" onclick="switchView('dashboard')">
        <svg class="tab-icon" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><rect x="1.5" y="1.5" width="5.5" height="5.5" rx="1"/><rect x="9" y="1.5" width="5.5" height="5.5" rx="1"/><rect x="1.5" y="9" width="5.5" height="5.5" rx="1"/><rect x="9" y="9" width="5.5" height="5.5" rx="1"/></svg>
        <span class="tab-label">Overview</span> <span class="tab-kbd">1</span>
      </button>
      <button class="tab interactive" data-view="catalog" onclick="switchView('catalog')">
        <svg class="tab-icon" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><rect x="1.5" y="2.5" width="13" height="3" rx="1"/><rect x="1.5" y="6.7" width="13" height="3" rx="1"/><rect x="1.5" y="10.9" width="13" height="3" rx="1"/></svg>
        <span class="tab-label">Servers</span> <span class="tab-kbd">2</span>
      </button>
      <button class="tab interactive" data-view="pr" onclick="switchView('pr')">
        <svg class="tab-icon" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><circle cx="8" cy="8" r="6"/><path d="M5 8l2 2 4-4"/></svg>
        <span class="tab-label">PR control</span>
      </button>
      <button class="tab interactive" data-view="evals" onclick="switchView('evals')">
        <svg class="tab-icon" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M1.5 14.5h13"/><path d="M3.5 11v3"/><path d="M7 7v7"/><path d="M10.5 9v5"/><path d="M14 4v10"/></svg>
        <span class="tab-label">Performance</span> <span class="tab-kbd">3</span>
      </button>
      <div class="nav-section">Configure</div>
      <button class="tab interactive" data-view="deploy" onclick="switchView('deploy')">
        <svg class="tab-icon" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M8 1.5l6 3v7l-6 3-6-3v-7z"/><path d="M2 4.5l6 3 6-3"/><path d="M8 7.5v7"/></svg>
        <span class="tab-label">Deploy</span> <span class="tab-kbd">4</span>
      </button>
      <button class="tab interactive" data-view="settings" onclick="switchView('settings')">
        <svg class="tab-icon" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><circle cx="8" cy="8" r="2.2"/><path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M12.6 3.4l-1.4 1.4M4.8 11.2l-1.4 1.4"/></svg>
        <span class="tab-label">Settings</span> <span class="tab-kbd">5</span>
      </button>
    </nav>
    <div class="sidebar-foot">
      <div class="auth-badge">
        <div class="auth-dot" id="auth-dot"></div>
        <span id="auth-mode">none</span>
      </div>
      <div class="foot-hint"><kbd>&#8984;</kbd><kbd>K</kbd> command palette</div>
    </div>
  </aside>

  <div class="workspace">
    <header class="page-toolbar">
      <span class="page-title" id="page-title">Overview</span>
      <div class="toolbar-right">
        <div class="profile-pills" id="profile-pills" role="group" aria-label="Profiles"></div>
        <button class="palette-trigger interactive" type="button" onclick="openPalette()" aria-label="Open command palette">
          <span>Search</span><kbd>&#8984;K</kbd>
        </button>
      </div>
    </header>
    <main class="page-body" id="main-content">
"""

_VIEW_DASHBOARD = r"""
<div class="view active" id="view-dashboard">
    <div class="exc-strip" id="exc-strip" role="group" aria-label="Server health summary">
      <button class="exc-item active interactive" data-filter="all" type="button" aria-pressed="true">
        <span class="dot"></span> all <span class="n" id="exc-all">0</span>
      </button>
      <button class="exc-item ok interactive" data-filter="ready" type="button" aria-pressed="false">
        <span class="dot"></span> ready <span class="n" id="exc-ready">0</span>
      </button>
      <button class="exc-item warn interactive" data-filter="needs" type="button" aria-pressed="false">
        <span class="dot"></span> need credentials <span class="n" id="exc-needs">0</span>
      </button>
      <button class="exc-item interactive" data-filter="disabled" type="button" aria-pressed="false">
        <span class="dot"></span> disabled <span class="n" id="exc-disabled">0</span>
      </button>
      <div class="exc-spacer"></div>
      <div class="live-indicator">
        <span class="live-dot stale" id="live-dot"></span> <span id="live-label">connecting</span>
      </div>
    </div>

    <div class="kpi-grid">
      <div class="kpi">
        <div class="kpi-top">
          <span class="kpi-label">Success rate</span>
          <span class="trend" id="trend-success"></span>
        </div>
        <div class="kpi-value tnum" id="stat-success">&mdash;</div>
        <svg class="kpi-spark" id="spark-success" viewBox="0 0 120 30" preserveAspectRatio="none" aria-hidden="true">
          <path class="spark-area" fill="url(#grad-ok)" d=""/>
          <path class="spark-line" stroke="#3ddc97" vector-effect="non-scaling-stroke" stroke-linecap="round" stroke-linejoin="round" d=""/>
          <circle class="spark-dot" fill="#3ddc97" style="opacity:0" cx="0" cy="0"/>
        </svg>
      </div>
      <div class="kpi">
        <div class="kpi-top">
          <span class="kpi-label">Live latency</span>
          <span class="trend" id="trend-latency"></span>
        </div>
        <div class="kpi-value tnum" id="stat-latency">&mdash;<span class="unit"> ms</span></div>
        <svg class="kpi-spark" id="spark-latency" viewBox="0 0 120 30" preserveAspectRatio="none" aria-hidden="true">
          <path class="spark-area" fill="url(#grad-teal)" d=""/>
          <path class="spark-line" stroke="#2dd4bf" vector-effect="non-scaling-stroke" stroke-linecap="round" stroke-linejoin="round" d=""/>
          <circle class="spark-dot" fill="#2dd4bf" style="opacity:0" cx="0" cy="0"/>
        </svg>
      </div>
      <div class="kpi">
        <div class="kpi-top"><span class="kpi-label">Servers enabled</span></div>
        <div class="kpi-value tnum"><span id="stat-enabled">0</span><span class="unit"> / <span id="stat-tools">0</span></span></div>
        <div class="kpi-sub" id="stat-servers-sub">routing coverage</div>
      </div>
      <div class="kpi">
        <div class="kpi-top">
          <span class="kpi-label">Events / poll</span>
          <span class="trend" id="trend-events"></span>
        </div>
        <div class="kpi-value tnum" id="stat-events">&mdash;</div>
        <div class="kpi-sub"><span id="stat-backends" class="tnum">0</span> tool calls · <span id="stat-events-total" class="tnum">0</span> events</div>
        <svg class="kpi-spark" id="spark-events" viewBox="0 0 120 30" preserveAspectRatio="none" aria-hidden="true">
          <path class="spark-area" fill="url(#grad-teal)" d=""/>
          <path class="spark-line" stroke="#2dd4bf" vector-effect="non-scaling-stroke" stroke-linecap="round" stroke-linejoin="round" d=""/>
          <circle class="spark-dot" fill="#2dd4bf" style="opacity:0" cx="0" cy="0"/>
        </svg>
      </div>
    </div>

    <div class="dash-cols">
      <section class="panel route-panel">
        <div class="panel-head">
          <span class="panel-title">Routing table</span>
          <span class="panel-meta tnum" id="node-count">0 servers</span>
        </div>
        <div class="server-map" id="server-map"></div>
      </section>
      <section class="panel log-panel">
        <div class="panel-head">
          <span class="panel-title">Activity</span>
          <div class="panel-actions">
            <button class="mini-btn interactive" id="btn-errors-only" type="button" onclick="toggleErrorsOnly()" aria-pressed="false">errors</button>
            <button class="mini-btn interactive" id="btn-pause" type="button" onclick="toggleStreamPause()" aria-pressed="false">pause</button>
            <button class="mini-btn interactive" id="btn-clear-stream" type="button" onclick="clearTelemetryStream()">clear</button>
          </div>
        </div>
        <div class="latency-wrap">
          <div class="latency-cap"><span>latency</span><span class="tnum" id="latency-now">&mdash;</span></div>
          <canvas id="latency-strip" height="32"></canvas>
        </div>
        <div class="telemetry-stream" id="telemetry-stream">
          <div class="tlm-empty">Waiting for tool calls&hellip;</div>
        </div>
      </section>
    </div>

    <div class="tunnel-bar">
      <span class="panel-title">Tunnels</span>
      <div class="tunnel-item">
        <span class="tunnel-name">cloudflare</span>
        <button class="btn-tunnel interactive" id="btn-cf" onclick="toggleTunnel('cloudflare')"
          aria-label="Start cloudflare tunnel">Start</button>
      </div>
      <div class="tunnel-item">
        <span class="tunnel-name">tailscale</span>
        <button class="btn-tunnel interactive" id="btn-ts" onclick="toggleTunnel('tailscale')"
          aria-label="Start tailscale tunnel">Start</button>
      </div>
    </div>
  </div>
"""

_VIEW_CATALOG = r"""
<div class="view" id="view-catalog">
    <div class="view-header">
      <span class="view-title">Server catalog</span>
      <span class="panel-meta tnum" id="catalog-count" role="status">0 servers</span>
    </div>
    <div class="view-scroll">
      <div class="catalog-toolbar">
        <input class="form-input" id="catalog-search" type="search"
          placeholder="Search servers..." autocomplete="off"
          aria-label="Search servers">
        <div class="facet-row" id="catalog-facets" role="group" aria-label="Filter by status">
          <button class="facet active interactive" type="button" data-cfilter="all" aria-pressed="true">All</button>
          <button class="facet interactive" type="button" data-cfilter="ready" aria-pressed="false">Ready</button>
          <button class="facet interactive" type="button" data-cfilter="needs" aria-pressed="false">Needs credentials</button>
          <button class="facet interactive" type="button" data-cfilter="disabled" aria-pressed="false">Disabled</button>
        </div>
      </div>
      <div class="server-grid" id="catalog-grid">
        <div class="view-empty">Loading catalog...</div>
      </div>
    </div>
  </div>
"""

_VIEW_EVALS = r"""
  <div class="view" id="view-evals">
    <div class="view-header">
      <span class="view-title">Tool performance</span>
    </div>
    <div class="view-scroll">
      <div class="eval-summary" id="eval-summary"></div>
      <table class="eval-table">
        <thead><tr>
          <th>Tool</th><th>Calls</th><th>Success</th><th>Avg latency</th>
        </tr></thead>
        <tbody id="eval-tbody"></tbody>
      </table>
    </div>
  </div>
"""


_VIEW_DEPLOY = r"""
  <div class="view" id="view-deploy">
    <div class="view-header">
      <span class="view-title">Deployment configs</span>
    </div>
    <div class="view-scroll">
      <div class="code-tabs" id="deploy-tabs" role="tablist" aria-label="Deployment formats"></div>
      <div class="code-preview" role="tabpanel" id="deploy-panel">
        <div class="code-desc" id="deploy-desc"></div>
        <div class="code-wrap">
          <button class="code-copy interactive" onclick="copyDeployCode(this)"
            aria-label="Copy deployment code">Copy</button>
          <pre class="code-block" id="deploy-code">Select a format above.</pre>
        </div>
      </div>
    </div>
  </div>
"""


_VIEW_SETTINGS = r"""
  <div class="view" id="view-settings">
    <div class="view-header">
      <span class="view-title">Settings</span>
    </div>
    <div class="view-scroll">
      <div class="settings-form">
        <div class="form-field">
          <label class="form-label" for="set-auth-mode">Auth mode</label>
          <select class="form-select" id="set-auth-mode">
            <option value="none">none</option>
            <option value="apikey">apikey</option>
            <option value="oauth">oauth</option>
          </select>
        </div>
        <div class="form-field">
          <label class="form-label" for="set-profile">Default profile</label>
          <input class="form-input" id="set-profile" type="text" />
        </div>
        <div class="form-field">
          <label class="form-label" for="set-cors">CORS origins (comma-separated)</label>
          <input class="form-input" id="set-cors" type="text" />
        </div>
        <div class="form-field">
          <label class="form-label" for="set-rate-limit">Rate limit / min (0 = off)</label>
          <input class="form-input" id="set-rate-limit" type="number" min="0" />
        </div>
        <div class="form-field">
          <label class="form-label" for="set-storage">Storage backend</label>
          <select class="form-select" id="set-storage">
            <option value="sqlite">sqlite</option>
            <option value="jsonl">jsonl</option>
          </select>
        </div>
        <button class="btn-save interactive" onclick="saveSettings(this)">Save settings</button>
      </div>
    </div>
  </div>
"""

_VIEW_PR = r"""
<div class="view" id="view-pr">
    <div class="view-header">
      <span class="view-title">PR control</span>
      <div class="pr-header-actions">
        <span class="panel-meta tnum" id="pr-count" role="status">loading PRs…</span>
        <button class="mini-btn interactive" id="btn-pr-refresh" type="button"
          onclick="loadPRView(this)" aria-label="Refresh pull requests">Refresh</button>
      </div>
    </div>
    <div class="view-scroll">
      <div class="pr-grid" id="pr-grid">
        <div class="view-empty">Loading pull requests…</div>
      </div>
    </div>
  </div>
"""


_HTML_SHELL_BOTTOM = r"""
    </main>
  <div class="command-bar">
    <span class="cmd-prompt">&gt;</span>
    <label for="cmd-input" class="sr-only">Command</label>
    <input id="cmd-input"
      placeholder="type a command... (toggle github, profile ops)"
      autocomplete="off" />
    <span class="cmd-hint">tab</span>
  </div>
  </div>
</div>

<div class="palette-overlay" id="cmd-palette" role="dialog" aria-modal="true" aria-label="Command palette">
  <div class="palette">
    <input id="palette-input" class="palette-input" type="text"
      placeholder="Search commands, servers, views..." autocomplete="off"
      aria-label="Command palette search" />
    <div class="palette-results" id="palette-results"></div>
    <div class="palette-foot">
      <span><kbd>&#8593;</kbd><kbd>&#8595;</kbd> navigate</span>
      <span><kbd>&#8629;</kbd> run</span>
      <span><kbd>esc</kbd> close</span>
    </div>
  </div>
</div>

<div class="detail-panel" id="detail-panel">
  <div class="detail-header">
    <span class="detail-name" id="detail-name">-</span>
    <div class="detail-close interactive" onclick="closeDetail()" role="button"
      tabindex="0" aria-label="Close details"
      onkeydown="btnKey(event,closeDetail)">&times;</div>
  </div>
  <div class="detail-section">
    <div class="detail-label">Status</div>
    <div class="detail-status" id="detail-status">-</div>
  </div>
  <div class="detail-section">
    <div class="detail-label">Transport / Risk</div>
    <div class="badges" id="detail-badges"></div>
  </div>
  <div class="detail-section">
    <div class="detail-label">Description</div>
    <div class="detail-value" id="detail-desc">-</div>
  </div>
  <div class="detail-section">
    <div class="detail-label">Environment</div>
    <div class="detail-value" id="detail-env">-</div>
  </div>
  <div class="detail-section">
    <div class="detail-label">Launch command</div>
    <div class="detail-value" id="detail-cmd">-</div>
  </div>
  <div class="detail-section">
    <div class="detail-label">Profiles</div>
    <div class="detail-value" id="detail-profiles">-</div>
  </div>
  <div class="detail-section" id="detail-homepage-row" style="display:none">
    <div class="detail-label">Homepage</div>
    <a class="detail-link" id="detail-homepage" href="#" target="_blank" rel="noopener">-</a>
  </div>
  <div class="detail-section" id="detail-connect-row" style="display:none">
    <button class="btn-action primary interactive" id="btn-connect" type="button"
      onclick="connectSelected()" style="width:100%">Connect&hellip;</button>
  </div>
  <div class="detail-actions">
    <button class="btn-action primary interactive" id="btn-enable" onclick="detailToggle(true, this)">Enable</button>
    <button class="btn-action danger interactive" id="btn-disable"
      onclick="detailToggle(false, this)">Disable</button>
  </div>
</div>

<div class="modal-overlay" id="cred-modal" role="dialog" aria-modal="true"
  aria-labelledby="cred-title">
  <div class="modal-card">
    <div class="modal-head">
      <span class="modal-title" id="cred-title">Connect</span>
      <div class="detail-close interactive" onclick="closeCredentialsModal()" role="button"
        tabindex="0" aria-label="Close"
        onkeydown="btnKey(event,closeCredentialsModal)">&times;</div>
    </div>
    <p class="modal-sub" id="cred-sub">Paste a token to connect this server.</p>
    <div id="cred-fields"></div>
    <div class="modal-actions">
      <a class="btn-action" id="cred-provider" href="#" target="_blank"
        rel="noopener" style="display:none">Get a token &#8599;</a>
      <button class="btn-action primary interactive" id="cred-save" type="button"
        onclick="saveCredentials(this)">Save &amp; connect</button>
    </div>
  </div>
</div>

<div class="toast-container" id="toast-container" aria-live="polite"></div>
"""

_HTML = (
    _HTML_SHELL_TOP
    + _VIEW_DASHBOARD
    + _VIEW_CATALOG
    + _VIEW_EVALS
    + _VIEW_DEPLOY
    + _VIEW_SETTINGS
    + _VIEW_PR
    + _HTML_SHELL_BOTTOM
)


_JS = r"""

const API = '';
const MONO_FONT = "'JetBrains Mono',ui-monospace,monospace";
const AUTH_STORAGE = 'kater_bearer';
const WS_PORT = (window.KATER_CONFIG && window.KATER_CONFIG.wsPort) || 9092;
const WS_SCHEME = location.protocol === 'https:' ? 'wss' : 'ws';
const WS_URL = (location.protocol === 'https:')
  ? ('wss://' + location.host + '/ws')
  : (WS_SCHEME + '://' + location.hostname + ':' + WS_PORT + '/ws');
let ws = null;
let wsRetry = 0;
let wsTimer = null;
let appReady = false;
let catalogQuery = '';
let catalogReloadTimer = null;
let catalogSearchTimer = null;
const recentTelemetry = new Map();
const TELEMETRY_DEDUPE_MS = 2500;
let servers = [];
let profiles = [];
let activeProfile = 'core';
let selectedNode = null;

// Overview live state.
let routeFilter = 'all';
let routeSel = -1;
let routeRows = [];
let streamPaused = false;
let streamErrorsOnly = false;
let catalogFilter = 'all';
let catalogItems = [];
let catalogLoadSeq = 0;
let prLoadSeq = 0;
let lastEventTotal = null;
let lastLiveMs = 0;
const HIST = 40;
const histSuccess = [];
const histEvents = [];
const histLatency = [];
const recentActivity = new Map(); // serverName -> last call ms age marker
const IS_APPLE = /Mac|iPhone|iPad|iPod/.test(navigator.platform || '');
const MOD_KEY = IS_APPLE ? '\u2318' : 'Ctrl';

// ── Helpers ────────────────────────────
class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

// HTML-escape for the few places we still build markup from server data.
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// Sanitize a value before it becomes a CSS class (badge transport/risk).
function cls(s) {
  return String(s == null ? '' : s).replace(/[^a-z0-9_-]/gi, '');
}

function pad2(n) { return String(n).padStart(2, '0'); }

function authHeaders() {
  const h = {};
  const token = sessionStorage.getItem(AUTH_STORAGE);
  if (token) h['Authorization'] = 'Bearer ' + token;
  return h;
}

function wsUrlWithAuth() {
  const token = sessionStorage.getItem(AUTH_STORAGE);
  if (!token) return WS_URL;
  const sep = WS_URL.includes('?') ? '&' : '?';
  return WS_URL + sep + 'token=' + encodeURIComponent(token);
}

function b64url(bytes) {
  let s = btoa(String.fromCharCode(...bytes));
  return s.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function pkceChallenge(verifier) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
  return b64url(new Uint8Array(digest));
}

function randomVerifier() {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return b64url(bytes);
}

async function exchangeOAuthCode(code) {
  const verifier = sessionStorage.getItem('pkce_verifier') || '';
  const clientId = sessionStorage.getItem('oauth_client_id') || '';
  const redirect = location.origin + location.pathname;
  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    code: code,
    client_id: clientId,
    redirect_uri: redirect,
    code_verifier: verifier,
  });
  const r = await fetch('/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    throw new ApiError(data.error || 'token exchange failed', r.status, data);
  }
  if (data.access_token) {
    sessionStorage.setItem(AUTH_STORAGE, data.access_token);
  }
  sessionStorage.removeItem('pkce_verifier');
}

async function startOAuthLogin() {
  const verifier = randomVerifier();
  const challenge = await pkceChallenge(verifier);
  sessionStorage.setItem('pkce_verifier', verifier);
  const redirect = location.origin + location.pathname;
  const regResp = await fetch('/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      client_name: 'kater-dashboard',
      redirect_uris: [redirect],
    }),
  });
  const reg = await regResp.json().catch(() => ({}));
  if (!regResp.ok || !reg.client_id) {
    toast('OAuth registration failed: ' + (reg.error || regResp.status), 'error');
    return;
  }
  sessionStorage.setItem('oauth_client_id', reg.client_id);
  const q = new URLSearchParams({
    response_type: 'code',
    client_id: reg.client_id,
    redirect_uri: redirect,
    code_challenge: challenge,
    code_challenge_method: 'S256',
    scope: 'tools',
  });
  location.href = '/authorize?' + q.toString();
}

async function handleAuthBootstrap() {
  const params = new URLSearchParams(location.search);
  if (params.get('api_key')) {
    sessionStorage.setItem(AUTH_STORAGE, params.get('api_key'));
    params.delete('api_key');
    history.replaceState({}, '', location.pathname + (params.toString() ? '?' + params : ''));
  }
  if (params.get('code') && sessionStorage.getItem('pkce_verifier')) {
    try {
      await exchangeOAuthCode(params.get('code'));
      params.delete('code');
      history.replaceState({}, '', location.pathname);
    } catch (e) {
      sessionStorage.removeItem(AUTH_STORAGE);
      throw e;
    }
  }
  if (params.get('error')) {
    toast('OAuth denied: ' + params.get('error'), 'error');
    params.delete('error');
    history.replaceState({}, '', location.pathname);
  }
}

function showAuthGate() {
  const gate = document.getElementById('auth-gate');
  gate.classList.add('show');
  document.getElementById('boot').style.display = 'none';
  document.getElementById('auth-oauth-btn').onclick = () => startOAuthLogin();
  document.getElementById('auth-key-btn').onclick = async () => {
    const key = document.getElementById('auth-key-input').value.trim();
    if (!key) { toast('Enter an API key', 'error'); return; }
    sessionStorage.setItem(AUTH_STORAGE, key);
    gate.classList.remove('show');
    if (appReady) {
      try { await loadCatalog(); await loadStatus(); initWebSocket(); }
      catch (e) { toast('Login refresh failed', 'error'); }
      return;
    }
    init();
  };
}

// Fail-aware fetch: throws ApiError on !ok or non-JSON, so callers can't
// mistake a 401/500 for success and silently render undefined.
async function api(path, opts = {}) {
  opts.headers = { ...authHeaders(), ...(opts.headers || {}) };
  const r = await fetch(API + path, opts);
  const text = await r.text();
  let data = null;
  if (text) {
    try { data = JSON.parse(text); } catch (e) { data = null; }
  }
  if (!r.ok) {
    const msg = (data && data.error) ? data.error : ('HTTP ' + r.status);
    throw new ApiError(msg, r.status, data);
  }
  return data || {};
}

async function apiPost(path, body) {
  return api(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {})
  });
}

function toast(msg, type = '') {
  const c = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = 'toast ' + type;
  t.setAttribute('role', 'status');
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function btnKey(e, fn) {
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fn(); }
}

function makeBadge(klass, text) {
  const b = document.createElement('span');
  b.className = 'badge ' + cls(klass);
  b.textContent = text;
  return b;
}

function td(text) {
  const t = document.createElement('td');
  if (text != null) t.textContent = text;
  return t;
}

function filterServers(all) {
  // 'core' is the superset; any other profile filters to its members. Makes
  // the profile pills actually do something (the catalog payload carries a
  // `profiles` list per server).
  const seen = new Set();
  return (activeProfile === 'core'
    ? all
    : all.filter(s => (s.profiles || []).indexOf(activeProfile) !== -1)
  ).filter(s => {
    if (seen.has(s.name)) return false;
    seen.add(s.name);
    return true;
  });
}

function catalogApiPath() {
  const params = new URLSearchParams();
  if (catalogQuery) params.set('q', catalogQuery);
  if (activeProfile && activeProfile !== 'core') params.set('profile', activeProfile);
  const q = params.toString();
  return '/api/catalog' + (q ? '?' + q : '');
}

function clearCatalogSearch() {
  const input = document.getElementById('catalog-search');
  if (input) input.value = '';
  catalogQuery = '';
  writeUrlState();
  if (currentView === 'catalog') loadCatalogView();
}
function resetCatalogFilter() { setCatalogFilter('all'); }
function resetRouteFilter() { setRouteFilter('all'); }

function scheduleCatalogReload() {
  if (catalogReloadTimer) return;
  catalogReloadTimer = setTimeout(async () => {
    catalogReloadTimer = null;
    try {
      await loadCatalog();
      if (currentView === 'catalog') await loadCatalogView();
    } catch (e) { /* ignore background refresh errors */ }
  }, 300);
}

// ── Sparklines (dependency-free inline SVG) ──────────────────
function pushHist(arr, v) {
  arr.push(v);
  while (arr.length > HIST) arr.shift();
}

function updateSpark(id, data) {
  const svg = document.getElementById(id);
  if (!svg) return;
  const line = svg.querySelector('.spark-line');
  const area = svg.querySelector('.spark-area');
  const dot = svg.querySelector('.spark-dot');
  if (!data || data.length < 2) {
    if (line) line.setAttribute('d', '');
    if (area) area.setAttribute('d', '');
    if (dot) dot.style.opacity = '0';
    return;
  }
  const w = 120, h = 30, pad = 3;
  let mn = Math.min.apply(null, data), mx = Math.max.apply(null, data);
  if (mn === mx) { mn -= 1; mx += 1; }
  const X = i => pad + (i / (data.length - 1)) * (w - 2 * pad);
  const Y = v => pad + (1 - (v - mn) / (mx - mn)) * (h - 2 * pad);
  let d = '';
  for (let i = 0; i < data.length; i++) {
    d += (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(data[i]).toFixed(1) + ' ';
  }
  let ar = 'M' + X(0).toFixed(1) + ' ' + (h - pad);
  for (let i = 0; i < data.length; i++) ar += ' L' + X(i).toFixed(1) + ' ' + Y(data[i]).toFixed(1);
  ar += ' L' + X(data.length - 1).toFixed(1) + ' ' + (h - pad) + ' Z';
  if (line) line.setAttribute('d', d);
  if (area) area.setAttribute('d', ar);
  if (dot) {
    dot.setAttribute('cx', X(data.length - 1).toFixed(1));
    dot.setAttribute('cy', Y(data[data.length - 1]).toFixed(1));
    dot.style.opacity = '1';
  }
}

function updateTrend(id, cur, prev, opts) {
  const el = document.getElementById(id);
  if (!el) return;
  opts = opts || {};
  if (prev == null || isNaN(prev) || cur == null || isNaN(cur)) {
    el.textContent = ''; el.className = 'trend'; return;
  }
  const diff = cur - prev;
  const flat = Math.abs(diff) < (opts.eps || 0.5);
  if (flat) { el.className = 'trend flat'; el.textContent = '\u2192 0' + (opts.unit || ''); return; }
  const up = diff > 0;
  // Higher is better unless invert (latency: lower is better).
  const good = opts.invert ? !up : up;
  el.className = 'trend ' + (good ? 'pos' : 'neg');
  const mag = opts.pct ? Math.abs(diff).toFixed(1) : Math.round(Math.abs(diff));
  el.textContent = (up ? '\u25B2 ' : '\u25BC ') + mag + (opts.unit || '');
}

function latencyClass(ms) { return ms < 250 ? 'fast' : ms < 900 ? 'mid' : 'slow'; }

// ── Boot Sequence ──────────────────────
async function bootSequence() {
  const boot = document.getElementById('boot');
  if (boot) boot.style.display = 'none';
}

// ── Init ───────────────────────────────
async function init() {
  if (appReady) return;
  try { await handleAuthBootstrap(); } catch (e) {
    console.error('auth bootstrap:', e);
    toast((e instanceof ApiError ? e.message : 'Login failed'), 'error');
  }
  try { await bootSequence(); } catch (e) {
    console.error('boot failed:', e);
  }
  applyModKeyHints();
  restoreUrlState();
  // Server map MUST exist before loadCatalog() calls buildNodes().
  initCanvas();
  initExceptionStrip();
  initCatalogFacets();
  initLatencyStrip();
  initPalette();
  try {
    await loadProfiles();
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) { showAuthGate(); return; }
    console.error('profiles:', e);
  }
  try {
    await loadCatalog();
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) { showAuthGate(); return; }
    console.error('catalog:', e);
  }
  try {
    await loadStatus();
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) { showAuthGate(); return; }
    console.error('status:', e);
  }
  try { await loadTunnelStatus(); } catch (e) { console.error('tunnel:', e); }
  initDelegation();
  initCommandBar();
  initCatalogSearch();
  initKeyboard();
  initWebSocket();
  window.addEventListener('popstate', onPopState);

  setInterval(loadStatusSafe, 5000);
  appReady = true;
  // Apply restored view after data is loaded.
  if (currentView && currentView !== 'dashboard') switchView(currentView);
  else writeUrlState(true);
}

function applyModKeyHints() {
  document.querySelectorAll('.foot-hint, .palette-trigger').forEach(el => {
    el.innerHTML = el.innerHTML.replace(/\u2318/g, MOD_KEY).replace(/Ctrl/g, MOD_KEY);
  });
}

function restoreUrlState() {
  const p = new URLSearchParams(location.search);
  const view = p.get('view');
  if (view && ['dashboard','catalog','evals','deploy','settings','pr'].indexOf(view) !== -1) {
    currentView = view;
  }
  const profile = p.get('profile');
  if (profile) activeProfile = profile;
  const q = p.get('q');
  if (q) {
    catalogQuery = q;
    const input = document.getElementById('catalog-search');
    if (input) input.value = q;
  }
  const rf = p.get('filter');
  if (rf && ['all','ready','needs','disabled'].indexOf(rf) !== -1) routeFilter = rf;
  const cf = p.get('cfilter');
  if (cf && ['all','ready','needs','disabled'].indexOf(cf) !== -1) catalogFilter = cf;
}

function writeUrlState(replace) {
  const p = new URLSearchParams();
  if (currentView && currentView !== 'dashboard') p.set('view', currentView);
  if (activeProfile && activeProfile !== 'core') p.set('profile', activeProfile);
  if (catalogQuery) p.set('q', catalogQuery);
  if (routeFilter && routeFilter !== 'all') p.set('filter', routeFilter);
  if (catalogFilter && catalogFilter !== 'all') p.set('cfilter', catalogFilter);
  if (selectedNode && selectedNode.name) p.set('server', selectedNode.name);
  const qs = p.toString();
  const url = location.pathname + (qs ? '?' + qs : '');
  if (replace) history.replaceState({}, '', url);
  else if (url !== location.pathname + location.search) history.pushState({}, '', url);
}

function onPopState() {
  restoreUrlState();
  document.querySelectorAll('.pill').forEach(el => {
    el.classList.toggle('active', el.dataset.profile === activeProfile);
  });
  setRouteFilter(routeFilter, true);
  setCatalogFilter(catalogFilter, true);
  switchView(currentView, true);
  const server = new URLSearchParams(location.search).get('server');
  if (server) openServerDetail(server);
  else closeDetail();
}

async function loadStatusSafe() {
  try { await loadStatus(); } catch (e) { /* swallow polled errors */ }
}

async function loadProfiles() {
  const data = await api('/api/profiles');
  profiles = data.profiles || [];
  const el = document.getElementById('profile-pills');
  el.innerHTML = '';
  for (const p of profiles) {
    const pill = document.createElement('div');
    const on = p === activeProfile;
    pill.className = 'pill interactive' + (on ? ' active' : '');
    pill.textContent = p;
    pill.dataset.profile = p;
    pill.setAttribute('tabindex', '0');
    pill.setAttribute('role', 'button');
    pill.setAttribute('aria-pressed', String(on));
    el.appendChild(pill);
  }
}

function switchProfile(p) {
  if (profiles.indexOf(p) === -1) { toast('unknown profile: ' + p, 'error'); return; }
  activeProfile = p;
  document.querySelectorAll('.pill').forEach(el => {
    const on = el.dataset.profile === p;
    el.classList.toggle('active', on);
    el.setAttribute('aria-pressed', String(on));
  });
  writeUrlState();
  loadCatalog();
  if (currentView === 'catalog') loadCatalogView();
  toast('profile: ' + p);
}

async function loadCatalog() {
  const data = await api(catalogApiPath());
  servers = filterServers(data.servers || []);
  buildNodes();
  document.getElementById('node-count').textContent = servers.length + ' servers';
}

async function loadStatus() {
  const data = await api('/api/status');
  document.getElementById('version-tag').textContent = 'v' + (data.version || '');
  document.getElementById('auth-mode').textContent = data.auth_mode || 'none';
  const total = (data.servers && data.servers.total) || 0;
  const enabled = (data.servers && data.servers.enabled) || 0;
  const success = (data.telemetry && data.telemetry.success_rate) || 0;
  const calls = (data.telemetry && data.telemetry.tool_calls) || 0;
  const events = (data.telemetry && data.telemetry.total_events) || 0;

  document.getElementById('stat-tools').textContent = total;
  document.getElementById('stat-enabled').textContent = enabled;
  const successEl = document.getElementById('stat-success');
  // Don't show a scary red 0% when no calls have been made yet.
  if (!calls) {
    successEl.textContent = '\u2014';
    successEl.className = 'kpi-value tnum';
  } else {
    successEl.textContent = success + '%';
    successEl.className = 'kpi-value tnum' + (success >= 90 ? '' : success >= 50 ? ' warn' : ' err');
  }
  document.getElementById('stat-backends').textContent = calls;
  const totalEl = document.getElementById('stat-events-total');
  if (totalEl) totalEl.textContent = events;
  document.getElementById('auth-dot').style.background =
    data.auth_mode === 'none' ? 'var(--ok)' : 'var(--info)';

  // Success rate trend + sparkline (only after we have real call volume).
  if (calls) {
    const prevSuccess = histSuccess.length ? histSuccess[histSuccess.length - 1] : null;
    pushHist(histSuccess, success);
    updateSpark('spark-success', histSuccess);
    updateTrend('trend-success', success, prevSuccess, { unit: '%', pct: true, eps: 0.4 });
  }

  // Events/poll: delta since last poll — matches the sparkline and trend.
  const eventsEl = document.getElementById('stat-events');
  if (lastEventTotal != null) {
    const delta = Math.max(0, events - lastEventTotal);
    const prevDelta = histEvents.length ? histEvents[histEvents.length - 1] : null;
    pushHist(histEvents, delta);
    updateSpark('spark-events', histEvents);
    updateTrend('trend-events', delta, prevDelta, { eps: 0.9 });
    if (eventsEl) eventsEl.textContent = delta;
  } else if (eventsEl) {
    eventsEl.textContent = '\u2014';
  }
  lastEventTotal = events;
}

// ── Exception strip ──────────────────────
function initExceptionStrip() {
  const strip = document.getElementById('exc-strip');
  if (!strip || strip.dataset.bound) return;
  strip.dataset.bound = '1';
  strip.addEventListener('click', (e) => {
    const item = e.target.closest('.exc-item');
    if (!item) return;
    setRouteFilter(item.dataset.filter || 'all');
  });
}

function setRouteFilter(filter, quiet) {
  routeFilter = filter;
  document.querySelectorAll('#exc-strip .exc-item').forEach(el => {
    const on = el.dataset.filter === filter;
    el.classList.toggle('active', on);
    el.setAttribute('aria-pressed', String(on));
  });
  routeSel = -1;
  renderServerMap();
  if (!quiet) writeUrlState();
}

function serverState(s) {
  if (!s.enabled) return 'disabled';
  if (s.env_configured === false) return 'needs';
  return 'ready';
}

function updateExceptionStrip() {
  let ready = 0, needs = 0, disabled = 0;
  for (const s of servers) {
    const st = serverState(s);
    if (st === 'ready') ready++;
    else if (st === 'needs') needs++;
    else disabled++;
  }
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  set('exc-all', servers.length);
  set('exc-ready', ready);
  set('exc-needs', needs);
  set('exc-disabled', disabled);
}

// ── Server routing table ─────────────────
function initCanvas() {
  const el = document.getElementById('server-map');
  if (!el || el.dataset.bound) return;
  el.dataset.bound = '1';
  el.addEventListener('click', onServerMapClick);
  el.addEventListener('focusin', (e) => {
    const row = e.target.closest('tr[data-name]');
    if (!row) return;
    const idx = routeRows.indexOf(row);
    if (idx >= 0) { routeSel = idx; highlightRouteRow(); }
  });
  el.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      const row = e.target.closest('tr[data-name]');
      if (!row) return;
      e.preventDefault();
      routeSel = routeRows.indexOf(row);
      openSelectedRoute();
    }
  });
}

function visibleRouteServers() {
  if (routeFilter === 'all') return servers;
  return servers.filter(s => serverState(s) === routeFilter);
}

function renderServerMap() {
  const el = document.getElementById('server-map');
  if (!el) return;
  el.innerHTML = '';
  routeRows = [];
  const list = visibleRouteServers();
  if (!list.length) {
    const empty = document.createElement('div');
    empty.className = 'view-empty';
    if (servers.length) {
      empty.textContent = 'No servers match this filter.';
      if (routeFilter !== 'all') {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'view-empty-link';
        btn.textContent = 'Switch filter to all';
        btn.onclick = resetRouteFilter;
        empty.appendChild(btn);
      }
    } else { empty.textContent = 'No servers in this profile.'; }
    el.appendChild(empty);
    return;
  }
  const table = document.createElement('table');
  table.className = 'route-table';
  const thead = document.createElement('thead');
  const hr = document.createElement('tr');
  for (const h of ['Server', 'Transport', 'Risk', 'Cost', 'Status']) {
    const th = document.createElement('th');
    th.textContent = h;
    hr.appendChild(th);
  }
  thead.appendChild(hr);
  table.appendChild(thead);
  const tbody = document.createElement('tbody');
  for (const s of list) {
    const tr = document.createElement('tr');
    tr.dataset.name = s.name;
    tr.tabIndex = 0;
    tr.setAttribute('role', 'button');
    const name = document.createElement('td');
    name.className = 'route-name';
    name.textContent = s.name;
    const transport = document.createElement('td');
    transport.appendChild(makeBadge(s.transport, s.transport));
    const risk = document.createElement('td');
    risk.appendChild(makeBadge(s.risk || 'low', s.risk || 'low'));
    const cost = document.createElement('td');
    cost.className = 'route-cost';
    const c = Math.max(0, Math.min(5, Number(s.context_cost) || 0));
    cost.textContent = c ? ('\u25CF'.repeat(c) + '\u25CB'.repeat(Math.max(0, 5 - c))) : '\u2014';
    cost.title = c ? ('context cost ' + c + '/5') : 'no cost data';
    const status = document.createElement('td');
    const chip = document.createElement('span');
    chip.className = 'status-chip';
    const dot = document.createElement('span');
    dot.className = 'status-dot';
    const label = document.createElement('span');
    label.className = 'status-label';
    const st = serverState(s);
    if (st === 'disabled') { dot.classList.add('off'); label.textContent = 'Disabled'; }
    else if (st === 'needs') { dot.classList.add('warn'); label.textContent = 'Needs credentials'; }
    else { dot.classList.add('ok'); label.textContent = 'Ready'; }
    chip.appendChild(dot);
    chip.appendChild(label);
    status.appendChild(chip);
    tr.appendChild(name);
    tr.appendChild(transport);
    tr.appendChild(risk);
    tr.appendChild(cost);
    tr.appendChild(status);
    tbody.appendChild(tr);
    routeRows.push(tr);
  }
  table.appendChild(tbody);
  el.appendChild(table);
  highlightRouteRow();
}

function highlightRouteRow() {
  routeRows.forEach((tr, i) => tr.classList.toggle('sel', i === routeSel));
  if (routeSel >= 0 && routeRows[routeSel]) {
    routeRows[routeSel].scrollIntoView({ block: 'nearest' });
    try { routeRows[routeSel].focus({ preventScroll: true }); } catch (e) {}
  }
}

function moveRouteSel(delta) {
  if (!routeRows.length) return;
  routeSel = Math.max(0, Math.min(routeRows.length - 1,
    routeSel < 0 ? 0 : routeSel + delta));
  highlightRouteRow();
}

async function openSelectedRoute() {
  if (routeSel < 0 || !routeRows[routeSel]) return;
  const name = routeRows[routeSel].dataset.name;
  let node = servers.find(s => s.name === name);
  if (!node) return;
  if (!node.mcp) {
    try { node = await api('/api/mcp/servers/' + encodeURIComponent(node.name)); }
    catch (err) { /* fall back */ }
  }
  openDetail(node);
}

function buildNodes() {
  renderServerMap();
  updateExceptionStrip();
  const count = document.getElementById('node-count');
  if (count) count.textContent = servers.length + ' servers';
}

async function onServerMapClick(e) {
  const row = e.target.closest('tr[data-name]');
  if (!row) {
    if (selectedNode) closeDetail();
    return;
  }
  routeSel = routeRows.indexOf(row);
  highlightRouteRow();
  let node = servers.find(s => s.name === row.dataset.name);
  if (!node) return;
  if (!node.mcp) {
    try { node = await api('/api/mcp/servers/' + encodeURIComponent(node.name)); }
    catch (err) { /* fall back */ }
  }
  openDetail(node);
}

function startAnimationLoop() {}


// ── Detail Panel ───────────────────────
function formatLaunch(node) {
  if (node.mcp && node.mcp.command) {
    return node.mcp.command + ' ' + (node.mcp.args || []).join(' ');
  }
  if (node.mcp && node.mcp.url) return node.mcp.url;
  return '-';
}

function openDetail(node) {
  selectedNode = node;
  document.getElementById('detail-name').textContent = node.name || '-';
  document.getElementById('detail-desc').textContent = node.description || '-';

  const badges = document.getElementById('detail-badges');
  badges.innerHTML = '';
  badges.appendChild(makeBadge(node.transport, node.transport));
  badges.appendChild(makeBadge(node.risk, node.risk));
  badges.appendChild(makeBadge(
    node.env_configured ? 'low' : 'high',
    node.env_configured ? 'configured' : 'missing env'
  ));

  const reqs = node.env_required || [];
  const configured = !!node.env_configured;
  const missing = configured ? [] : reqs;

  const envEl = document.getElementById('detail-env');
  envEl.innerHTML = '';
  if (reqs.length) {
    for (const e of reqs) {
      const line = document.createElement('div');
      const nameEl = document.createElement('span');
      nameEl.textContent = e + ': ';
      const val = document.createElement('span');
      val.style.color = configured ? 'var(--ok)' : 'var(--err)';
      val.textContent = configured ? 'set' : 'not set';
      line.appendChild(nameEl);
      line.appendChild(val);
      envEl.appendChild(line);
    }
  } else {
    envEl.textContent = 'No credentials required.';
  }

  // Status reads like a sentence the operator can act on.
  const statusEl = document.getElementById('detail-status');
  statusEl.className = 'detail-status';
  if (!node.enabled) {
    statusEl.classList.add('off');
    statusEl.textContent = 'Disabled. Enable it to include it in this profile.';
  } else if (missing.length) {
    statusEl.classList.add('needs');
    statusEl.textContent = 'Enabled, but not connected. Set ' + missing.join(', ') + '.';
  } else if (reqs.length) {
    statusEl.classList.add('ready');
    statusEl.textContent = 'Enabled and configured. Ready to connect.';
  } else {
    statusEl.classList.add('ready');
    statusEl.textContent = 'Enabled. No credentials needed.';
  }

  document.getElementById('detail-cmd').textContent = formatLaunch(node);
  document.getElementById('detail-profiles').textContent =
    (node.profiles || []).join(', ') || '-';

  const homeRow = document.getElementById('detail-homepage-row');
  const homeLink = document.getElementById('detail-homepage');
  if (node.homepage) {
    homeLink.href = node.homepage;
    homeLink.textContent = node.homepage;
    homeRow.style.display = '';
  } else {
    homeRow.style.display = 'none';
  }

  // Offer "Connect…" only when the server is missing the credentials it needs.
  const connectRow = document.getElementById('detail-connect-row');
  connectRow.style.display = (reqs.length && missing.length) ? '' : 'none';

  const enableBtn = document.getElementById('btn-enable');
  const disableBtn = document.getElementById('btn-disable');
  enableBtn.disabled = !!node.enabled;
  disableBtn.disabled = !node.enabled;
  enableBtn.style.opacity = node.enabled ? '0.4' : '1';
  disableBtn.style.opacity = node.enabled ? '1' : '0.4';

  document.getElementById('detail-panel').classList.add('open');
  writeUrlState();
}

function closeDetail() {
  document.getElementById('detail-panel').classList.remove('open');
  selectedNode = null;
  writeUrlState();
}

// ── Credentials modal ──────────────────
let credServer = null;

function connectSelected() {
  if (selectedNode && selectedNode.name) promptCredentials(selectedNode.name);
}

async function promptCredentials(name) {
  // Always work from the full server doc: the catalog payload omits the list
  // of required env vars, the detail endpoint has it.
  try {
    const server = await api('/api/mcp/servers/' + encodeURIComponent(name));
    if (server && !server.error) openCredentialsModal(server);
  } catch (e) {
    toast('Could not load ' + name + ': ' + (e.message || 'failed'), 'error');
  }
}

function openCredentialsModal(server) {
  credServer = server;
  const reqs = server.env_required || [];
  document.getElementById('cred-title').textContent = 'Connect ' + server.name;
  const sub = document.getElementById('cred-sub');
  const fields = document.getElementById('cred-fields');
  fields.innerHTML = '';
  if (!reqs.length) {
    sub.textContent = server.name + ' needs no credentials — just enable it.';
  } else {
    sub.textContent = 'Paste ' + (reqs.length > 1 ? 'these tokens' : 'a token')
      + ' to connect ' + server.name + ', or open the provider to create one.';
    for (const v of reqs) {
      const wrap = document.createElement('div');
      wrap.className = 'form-field';
      const label = document.createElement('label');
      label.className = 'form-label';
      label.textContent = v;
      const input = document.createElement('input');
      input.className = 'form-input';
      input.type = 'password';
      input.autocomplete = 'off';
      input.spellcheck = false;
      input.dataset.env = v;
      input.placeholder = server.env_configured
        ? 'set — leave blank to keep current'
        : 'paste value';
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') saveCredentials();
      });
      wrap.appendChild(label);
      wrap.appendChild(input);
      fields.appendChild(wrap);
    }
  }
  const prov = document.getElementById('cred-provider');
  if (server.homepage) { prov.href = server.homepage; prov.style.display = ''; }
  else { prov.style.display = 'none'; }
  document.getElementById('cred-modal').classList.add('show');
  const first = fields.querySelector('input');
  if (first) first.focus();
}

function closeCredentialsModal() {
  document.getElementById('cred-modal').classList.remove('show');
  credServer = null;
}

async function saveCredentials(btn) {
  if (!credServer) return;
  const originalText = btn ? btn.textContent : 'Save & connect';
  const inputs = document.querySelectorAll('#cred-fields input[data-env]');
  const env = {};
  let any = false;
  inputs.forEach((i) => {
    const val = i.value.trim();
    if (val) { env[i.dataset.env] = val; any = true; }
  });
  if (!any) { toast('Enter at least one value to save.', 'error'); return; }
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Saving...';
    btn.setAttribute('aria-busy', 'true');
  }
  const name = credServer.name;
  try {
    const data = await apiPost(
      '/api/mcp/servers/' + encodeURIComponent(name) + '/credentials', { env }
    );
    toast(name + (data.env_configured ? ' connected.' : ' credentials saved.'), 'success');
    closeCredentialsModal();
    await loadCatalog();
    if (currentView === 'catalog') await loadCatalogView();
    if (selectedNode && selectedNode.name === name) openServerDetail(name);
  } catch (e) {
    toast('Could not save credentials: ' + (e.message || 'failed'), 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = originalText;
      btn.removeAttribute('aria-busy');
    }
  }
}

async function detailToggle(enable, btn) {
  if (!selectedNode) return;
  const name = selectedNode.name;
  const action = enable ? 'enable' : 'disable';
  const originalText = btn ? btn.textContent : (enable ? 'Enable' : 'Disable');
  if (btn) {
    btn.disabled = true;
    btn.textContent = (enable ? 'Enabling...' : 'Disabling...');
    btn.setAttribute('aria-busy', 'true');
  }
  try {
    await apiPost('/api/mcp/servers/' + encodeURIComponent(name) + '/' + action, {});
    toast(enableHint(name, enable), enable ? 'success' : '');
  } catch (e) {
    toast(name + ': ' + (e.message || 'failed'), 'error');
    if (btn) {
      btn.disabled = false;
      btn.textContent = originalText;
      btn.removeAttribute('aria-busy');
    }
    return;
  }
  // Reload, then re-resolve selectedNode from the FRESH server list so we
  // don't keep rendering a stale, optimistically-mutated object.
  try { await loadCatalog(); } catch (e) { /* handled */ }
  const fresh = servers.find(s => s.name === name);
  if (fresh) openDetail(fresh);
  // Enabling something that still needs a token? Bring up the connect popup.
  if (enable && fresh && fresh.env_configured === false) promptCredentials(name);
}

function initCatalogSearch() {
  const input = document.getElementById('catalog-search');
  if (!input || input.dataset.bound) return;
  input.dataset.bound = '1';
  input.addEventListener('input', () => {
    // Invalidate any in-flight catalog load now, so a response for the previous
    // query can't render during the debounce window before the reload below starts.
    catalogLoadSeq++;
    if (catalogSearchTimer) clearTimeout(catalogSearchTimer);
    catalogSearchTimer = setTimeout(async () => {
      catalogSearchTimer = null;
      catalogQuery = input.value.trim();
      writeUrlState();
      try {
        // Only refresh the catalog view — don't refilter the Overview
        // routing table with the search query.
        if (currentView === 'catalog') await loadCatalogView();
      } catch (e) { /* ignore search errors while typing */ }
    }, 200);
  });
}

function initCatalogFacets() {
  const row = document.getElementById('catalog-facets');
  if (!row || row.dataset.bound) return;
  row.dataset.bound = '1';
  row.addEventListener('click', (e) => {
    const btn = e.target.closest('.facet');
    if (!btn) return;
    setCatalogFilter(btn.dataset.cfilter || 'all');
  });
  setCatalogFilter(catalogFilter, true);
}

function setCatalogFilter(filter, quiet) {
  catalogFilter = filter || 'all';
  document.querySelectorAll('#catalog-facets .facet').forEach(el => {
    const on = el.dataset.cfilter === catalogFilter;
    el.classList.toggle('active', on);
    el.setAttribute('aria-pressed', String(on));
  });
  if (currentView === 'catalog') loadCatalogView();
  if (!quiet) writeUrlState();
}

// ── Event delegation (catalog cards, deploy tabs, profile pills) ──
function initDelegation() {
  const grid = document.getElementById('catalog-grid');
  grid.addEventListener('click', (e) => {
    const toggle = e.target.closest('.toggle-switch');
    if (toggle && toggle.dataset.name) {
      e.stopPropagation();
      toggleServerCard(toggle.dataset.name, toggle);
      return;
    }
    const card = e.target.closest('.server-card');
    if (card && card.dataset.name) openServerDetail(card.dataset.name);
  });
  grid.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      const toggle = e.target.closest('.toggle-switch');
      if (toggle && toggle.dataset.name) {
        e.preventDefault();
        e.stopPropagation();
        toggleServerCard(toggle.dataset.name, toggle);
        return;
      }
      const card = e.target.closest('.server-card');
      if (card && card.dataset.name && e.target === card) {
        e.preventDefault();
        openServerDetail(card.dataset.name);
      }
    }
  });

  const tabs = document.getElementById('deploy-tabs');
  tabs.addEventListener('click', (e) => {
    const t = e.target.closest('.code-tab');
    if (t && t.dataset.fmt) selectDeployFormat(t.dataset.fmt);
  });

  const pills = document.getElementById('profile-pills');
  pills.addEventListener('click', (e) => {
    const p = e.target.closest('.pill');
    if (p && p.dataset.profile) switchProfile(p.dataset.profile);
  });
  pills.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      const p = e.target.closest('.pill');
      if (p && p.dataset.profile) {
        e.preventDefault();
        switchProfile(p.dataset.profile);
      }
    }
  });
}

// ── Command Bar ────────────────────────
const commands = [
  { cmd: 'toggle', desc: 'toggle <server> — switch server on/off' },
  { cmd: 'enable', desc: 'enable <server>' },
  { cmd: 'disable', desc: 'disable <server>' },
  { cmd: 'profile', desc: 'profile <name> — switch active profile' },
  { cmd: 'status', desc: 'show instance status' },
  { cmd: 'refresh', desc: 'reload catalog' },
];

function initCommandBar() {
  const input = document.getElementById('cmd-input');
  input.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter') {
      await runCommand(input.value.trim());
      input.value = '';
    } else if (e.key === 'Tab') {
      e.preventDefault();
      const parts = input.value.trim().split(/\s+/);
      if (parts.length === 1) {
        const match = commands.find(c => c.cmd.startsWith(parts[0]));
        if (match) input.value = match.cmd + ' ';
      } else if (parts.length === 2) {
        const match = servers.find(s => s.name.startsWith(parts[1]));
        if (match) input.value = parts[0] + ' ' + match.name;
      }
    }
  });

  const credModal = document.getElementById('cred-modal');
  credModal.addEventListener('click', (e) => {
    if (e.target === credModal) closeCredentialsModal();
  });
}

async function runCommand(input) {
  if (!input) return;
  const parts = input.split(/\s+/);
  const cmd = parts[0];

  if ((cmd === 'toggle' || cmd === 'enable' || cmd === 'disable') && parts[1]) {
    const server = parts[1];
    const action = cmd === 'toggle' ? 'toggle' : cmd;
    try {
      await apiPost('/api/mcp/servers/' + encodeURIComponent(server) + '/' + action, {});
      toast(server + ': ' + action + 'd', 'success');
      await loadCatalog();
    } catch (e) {
      toast(server + ': ' + (e.message || 'failed'), 'error');
    }
  } else if (cmd === 'profile' && parts[1]) {
    switchProfile(parts[1]);
  } else if (cmd === 'status') {
    try {
      const data = await api('/api/status');
      toast((data.servers.enabled) + '/' + (data.servers.total) + ' servers | '
        + (data.telemetry.success_rate || 0) + '% success');
    } catch (e) {
      toast('status: ' + (e.message || 'failed'), 'error');
    }
  } else if (cmd === 'refresh') {
    try { await loadCatalog(); toast('catalog refreshed'); }
    catch (e) { toast('refresh failed', 'error'); }
  } else {
    toast('unknown: ' + input, 'error');
  }
}

// ── Command palette (⌘K) ───────────────
let paletteItems = [];
let paletteFiltered = [];
let paletteSel = 0;

function initPalette() {
  const input = document.getElementById('palette-input');
  const overlay = document.getElementById('cmd-palette');
  if (!input || input.dataset.bound) return;
  input.dataset.bound = '1';
  input.addEventListener('input', () => renderPalette(input.value));
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); paletteSel = Math.min(paletteFiltered.length - 1, paletteSel + 1); paintPalette(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); paletteSel = Math.max(0, paletteSel - 1); paintPalette(); }
    else if (e.key === 'Enter') { e.preventDefault(); runPaletteSel(); }
    else if (e.key === 'Escape') { e.preventDefault(); closePalette(); }
  });
  overlay.addEventListener('click', (e) => { if (e.target === overlay) closePalette(); });
  document.getElementById('palette-results').addEventListener('click', (e) => {
    const it = e.target.closest('.palette-item');
    if (!it) return;
    paletteSel = parseInt(it.dataset.idx, 10) || 0;
    runPaletteSel();
  });
}

function buildPaletteItems() {
  const items = [];
  const views = [
    ['dashboard', 'Overview'], ['catalog', 'Servers'],
    ['evals', 'Performance'], ['deploy', 'Deploy'], ['settings', 'Settings'],
  ];
  for (const [v, label] of views) {
    items.push({ group: 'Navigate', label: 'Go to ' + label, hint: 'view', run: () => switchView(v) });
  }
  items.push({ group: 'Actions', label: 'Refresh catalog', hint: 'refresh', run: () => loadCatalog().then(() => toast('catalog refreshed')) });
  items.push({ group: 'Actions', label: 'Start cloudflare tunnel', hint: 'tunnel', run: () => toggleTunnel('cloudflare') });
  items.push({ group: 'Actions', label: 'Start tailscale tunnel', hint: 'tunnel', run: () => toggleTunnel('tailscale') });
  for (const p of profiles) {
    items.push({ group: 'Profiles', label: 'Profile: ' + p, hint: 'profile', run: () => switchProfile(p) });
  }
  for (const s of servers) {
    const st = serverState(s);
    const verb = s.enabled ? 'Disable' : 'Enable';
    items.push({
      group: 'Servers', label: verb + ' ' + s.name,
      hint: st === 'needs' ? 'needs creds' : (s.transport || ''),
      run: () => openServerDetail(s.name),
    });
  }
  return items;
}

function openPalette() {
  paletteItems = buildPaletteItems();
  paletteSel = 0;
  document.getElementById('cmd-palette').classList.add('show');
  const input = document.getElementById('palette-input');
  input.value = '';
  renderPalette('');
  setTimeout(() => input.focus(), 0);
}

function closePalette() {
  document.getElementById('cmd-palette').classList.remove('show');
}

function paletteIsOpen() {
  return document.getElementById('cmd-palette').classList.contains('show');
}

function renderPalette(q) {
  q = (q || '').trim().toLowerCase();
  paletteFiltered = q
    ? paletteItems.filter(it => it.label.toLowerCase().includes(q))
    : paletteItems.slice();
  paletteSel = 0;
  paintPalette();
}

function paintPalette() {
  const box = document.getElementById('palette-results');
  box.innerHTML = '';
  if (!paletteFiltered.length) {
    const e = document.createElement('div');
    e.className = 'palette-empty';
    e.textContent = 'No matches.';
    box.appendChild(e);
    return;
  }
  let lastGroup = null;
  paletteFiltered.forEach((it, i) => {
    if (it.group !== lastGroup) {
      lastGroup = it.group;
      const g = document.createElement('div');
      g.className = 'palette-group';
      g.textContent = it.group;
      box.appendChild(g);
    }
    const row = document.createElement('div');
    row.className = 'palette-item' + (i === paletteSel ? ' sel' : '');
    row.dataset.idx = i;
    const lbl = document.createElement('span');
    lbl.className = 'pi-label';
    lbl.textContent = it.label;
    const hint = document.createElement('span');
    hint.className = 'pi-hint';
    hint.textContent = it.hint || '';
    row.appendChild(lbl);
    row.appendChild(hint);
    box.appendChild(row);
  });
  const sel = box.querySelector('.palette-item.sel');
  if (sel) sel.scrollIntoView({ block: 'nearest' });
}

function runPaletteSel() {
  const it = paletteFiltered[paletteSel];
  if (!it) return;
  closePalette();
  try { it.run(); } catch (e) { toast('command failed', 'error'); }
}

// ── WebSocket ──────────────────────────
function setLive(connected) {
  const dot = document.getElementById('live-dot');
  const label = document.getElementById('live-label');
  if (dot) dot.classList.toggle('stale', !connected);
  if (label) label.textContent = connected ? 'live' : 'reconnecting';
}

function closeWebSocket() {
  if (wsTimer) { clearTimeout(wsTimer); wsTimer = null; }
  if (!ws) return;
  const old = ws;
  ws = null;
  old.onopen = null;
  old.onmessage = null;
  old.onerror = null;
  old.onclose = null;
  try { old.close(1000); } catch (e) {}
}

function initWebSocket() {
  closeWebSocket();
  try {
    ws = new WebSocket(wsUrlWithAuth());
  } catch (e) {
    setLive(false);
    scheduleReconnect();
    return;
  }
  ws.onopen = () => {
    wsRetry = 0;
    setLive(true);
    // subscribe_all so we receive every broadcast without a `type` filter
    // (the previous {cmd:'subscribe'} was missing the required type field).
    try { ws.send(JSON.stringify({ cmd: 'subscribe_all' })); } catch (e) {}
  };
  ws.onmessage = (e) => {
    try { handleWSMessage(JSON.parse(e.data)); } catch (err) {}
  };
  ws.onclose = (e) => {
    ws = null;
    setLive(false);
    // 1000 = clean close; don't auto-reconnect that. Everything else backs off.
    if (e.code !== 1000) scheduleReconnect();
  };
  ws.onerror = () => { try { ws.close(); } catch (e) {} };
}

function scheduleReconnect() {
  if (wsTimer) return;
  // Exponential backoff with jitter, capped at 30s — prevents tight retry
  // loops when the WS port is unreachable (e.g. behind a tunnel).
  const delay = Math.min(30000, 1000 * Math.pow(2, wsRetry++) + Math.random() * 500);
  wsTimer = setTimeout(() => { wsTimer = null; initWebSocket(); }, delay);
}

function handleWSMessage(data) {
  if (data.type === 'server_enabled'
      || data.type === 'server_disabled'
      || data.type === 'server_toggled') {
    // The initiating action already toasts; just keep the view in sync, and
    // refresh the open detail panel so its status reflects the change.
    scheduleCatalogReload();
    if (selectedNode && selectedNode.name === data.name) {
      openServerDetail(data.name);
    }
  }
  if (data.type === 'server_credentials') {
    scheduleCatalogReload();
    if (selectedNode && selectedNode.name === data.name) {
      openServerDetail(data.name);
    }
  }
  if (data.type === 'tool_call' || data.type === 'chain_run'
      || data.type === 'telemetry') {
    appendTelemetry(data);
  }
}

// ── Telemetry: rAF-batched stream + canvas latency strip ─────
const streamBuf = [];
let streamRaf = null;
const latencyRing = new Float32Array(256);
let latIdx = 0, latLen = 0;

function appendTelemetry(event) {
  const stamp = event.ts || event.timestamp || (Date.now() / 1000);
  const bucket = Math.round(Number(stamp) * 2);
  const key = (event.type || '') + '|' + (event.name || '') + '|' + bucket;
  const nowMs = Date.now();
  const prev = recentTelemetry.get(key);
  if (prev && nowMs - prev < TELEMETRY_DEDUPE_MS) return;
  recentTelemetry.set(key, nowMs);
  if (recentTelemetry.size > 200) {
    for (const [k, t] of recentTelemetry) {
      if (nowMs - t > TELEMETRY_DEDUPE_MS) recentTelemetry.delete(k);
    }
  }
  const ms = Math.round(event.duration_ms || 0);
  const isToolCall = event.type === 'tool_call' || (event.type === 'telemetry' && event.duration_ms != null);
  // Only feed real tool-call latencies into the oscilloscope / KPI — chain_run
  // events often arrive with 0ms and would flatten the chart.
  if (isToolCall && ms > 0) {
    latencyRing[latIdx] = ms;
    latIdx = (latIdx + 1) % latencyRing.length;
    latLen = Math.min(latLen + 1, latencyRing.length);
    lastLiveMs = ms;
  }
  // Infer server name from tool prefix (e.g. github.search -> github).
  const toolName = event.name || '';
  const serverGuess = toolName.includes('.') || toolName.includes('__')
    ? toolName.split(/[.__]/)[0]
    : '';
  if (serverGuess) recentActivity.set(serverGuess, nowMs);

  streamBuf.push({
    name: toolName || event.type || '',
    ok: event.success !== false,
    ms: ms,
    ts: Number(stamp) * (Number(stamp) > 1e12 ? 1 : 1000), // accept s or ms
    kind: event.type || 'tool_call',
  });
  if (streamBuf.length > 120) streamBuf.splice(0, streamBuf.length - 120);
  if (!streamRaf) streamRaf = requestAnimationFrame(flushStream);
}

function flushStream() {
  streamRaf = null;
  const batch = streamBuf.splice(0, streamBuf.length);
  if (!batch.length) return;

  // Rolling latency average for the KPI tile + sparkline.
  let sum = 0;
  for (const b of batch) sum += b.ms;
  const avg = Math.round(sum / batch.length);
  const latEl = document.getElementById('stat-latency');
  if (latEl) latEl.innerHTML = avg + '<span class="unit"> ms</span>';
  const nowEl = document.getElementById('latency-now');
  if (nowEl) nowEl.textContent = lastLiveMs + ' ms';
  const prevLat = histLatency.length ? histLatency[histLatency.length - 1] : null;
  pushHist(histLatency, avg);
  updateSpark('spark-latency', histLatency);
  updateTrend('trend-latency', avg, prevLat, { unit: 'ms', invert: true, eps: 5 });

  drawLatencyStrip();

  if (!streamPaused) {
    const stream = document.getElementById('telemetry-stream');
    const placeholder = stream.querySelector('.tlm-empty');
    if (placeholder) placeholder.remove();
    const frag = document.createDocumentFragment();
    for (const ev of batch) {
      // Burst grouping: same name+status as the current top row -> bump count.
      const top = stream.firstChild;
      if (top && top.classList && top.classList.contains('tlm-row')
          && top.dataset.name === ev.name
          && top.dataset.ok === String(ev.ok)) {
        const c = top.querySelector('.tlm-count');
        const n = (parseInt(top.dataset.count, 10) || 1) + 1;
        top.dataset.count = n;
        c.textContent = '\u00d7' + n;
        const msEl = top.querySelector('.tlm-ms');
        msEl.className = 'tlm-ms lat-pill ' + latencyClass(ev.ms);
        msEl.textContent = ev.ms + 'ms';
        continue;
      }
      frag.insertBefore(makeTlmRow(ev), frag.firstChild);
    }
    if (frag.childNodes.length) stream.insertBefore(frag, stream.firstChild);
    while (stream.children.length > 80) stream.lastChild.remove();
    ensureStreamEmptyHint();
  }
}

function makeTlmRow(ev) {
  const row = document.createElement('div');
  row.className = 'tlm-row new' + (ev.ok ? '' : ' is-err');
  row.dataset.name = ev.name;
  row.dataset.ok = String(ev.ok);
  row.dataset.count = '1';
  const when = new Date(ev.ts || Date.now());
  const ts = pad2(when.getHours()) + ':' + pad2(when.getMinutes()) + ':' + pad2(when.getSeconds());

  const t = document.createElement('span'); t.className = 'tlm-time'; t.textContent = ts;
  const ic = document.createElement('span');
  ic.className = 'tlm-icon ' + (ev.ok ? 'ok' : 'err');
  ic.textContent = ev.ok ? '\u2713' : '\u2717';
  const nm = document.createElement('span');
  nm.className = 'tlm-name';
  nm.textContent = ev.name;
  const cnt = document.createElement('span');
  cnt.className = 'tlm-count';
  const ms = document.createElement('span');
  ms.className = 'tlm-ms lat-pill ' + latencyClass(ev.ms);
  ms.textContent = (ev.ms > 0 ? ev.ms + 'ms' : ev.kind || '');

  row.appendChild(t); row.appendChild(ic); row.appendChild(nm);
  row.appendChild(cnt); row.appendChild(ms);
  row.addEventListener('animationend', () => row.classList.remove('new'), { once: true });
  setTimeout(() => row.classList.add('faded'), 8000);
  return row;
}

function initLatencyStrip() {
  drawLatencyStrip();
  window.addEventListener('resize', () => { if (currentView === 'dashboard') drawLatencyStrip(); });
}

function drawLatencyStrip() {
  const canvas = document.getElementById('latency-strip');
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const cssW = canvas.clientWidth || 320;
  const cssH = 32;
  if (canvas.width !== Math.round(cssW * dpr)) {
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
  }
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);

  // Baseline.
  ctx.strokeStyle = 'rgba(255,255,255,0.07)';
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(0, cssH - 0.5); ctx.lineTo(cssW, cssH - 0.5); ctx.stroke();

  if (latLen < 2) return;
  const samples = [];
  const start = latLen < latencyRing.length ? 0 : latIdx;
  for (let n = 0; n < latLen; n++) samples.push(latencyRing[(start + n) % latencyRing.length]);
  let max = 100;
  for (const v of samples) if (v > max) max = v;

  const cols = Math.max(1, Math.floor(cssW));
  const spp = samples.length / cols;
  ctx.strokeStyle = '#2dd4bf';
  ctx.lineWidth = 1;
  for (let col = 0; col < cols; col++) {
    const a = Math.floor(col * spp), b = Math.floor((col + 1) * spp);
    let lo = Infinity, hi = -Infinity;
    for (let j = a; j < b; j++) { if (samples[j] < lo) lo = samples[j]; if (samples[j] > hi) hi = samples[j]; }
    if (lo === Infinity) continue;
    const y1 = cssH - (hi / max) * (cssH - 4) - 2;
    const y2 = cssH - (lo / max) * (cssH - 4) - 2;
    ctx.beginPath(); ctx.moveTo(col + 0.5, y1); ctx.lineTo(col + 0.5, y2 + 0.6); ctx.stroke();
  }
}

function toggleStreamPause() {
  streamPaused = !streamPaused;
  const btn = document.getElementById('btn-pause');
  btn.classList.toggle('active', streamPaused);
  btn.setAttribute('aria-pressed', String(streamPaused));
  btn.textContent = streamPaused ? 'paused' : 'pause';
}

function toggleErrorsOnly() {
  streamErrorsOnly = !streamErrorsOnly;
  const btn = document.getElementById('btn-errors-only');
  btn.classList.toggle('active', streamErrorsOnly);
  btn.setAttribute('aria-pressed', String(streamErrorsOnly));
  const stream = document.getElementById('telemetry-stream');
  stream.classList.toggle('errors-only', streamErrorsOnly);
  ensureStreamEmptyHint();
}

function clearTelemetryStream() {
  const stream = document.getElementById('telemetry-stream');
  stream.innerHTML = '';
  ensureStreamEmptyHint();
}

function ensureStreamEmptyHint() {
  const stream = document.getElementById('telemetry-stream');
  if (!stream) return;
  const visible = Array.from(stream.children).filter(el => {
    if (el.classList.contains('tlm-empty')) return false;
    if (streamErrorsOnly && !el.classList.contains('is-err')) return false;
    return true;
  });
  let hint = stream.querySelector('.tlm-empty');
  if (visible.length) {
    if (hint) hint.remove();
    return;
  }
  if (!hint) {
    hint = document.createElement('div');
    hint.className = 'tlm-empty';
    stream.appendChild(hint);
  }
  hint.textContent = streamErrorsOnly
    ? 'No errors in the current stream.'
    : (streamPaused ? 'Stream paused.' : 'Waiting for tool calls\u2026');
}

// ── Tunnels ────────────────────────────
function tunnelBtn(provider) {
  return document.getElementById(provider === 'cloudflare' ? 'btn-cf' : 'btn-ts');
}

function setTunnelButton(provider, running) {
  const btn = tunnelBtn(provider);
  if (!btn) return;
  btn.classList.toggle('active', !!running);
  // Visible label matches the action announced to assistive tech.
  btn.textContent = running ? 'Stop' : 'Start';
  btn.setAttribute('aria-label', (running ? 'Stop ' : 'Start ') + provider + ' tunnel');
  btn.disabled = false;
}

async function loadTunnelStatus() {
  try {
    const data = await api('/api/tunnel');
    setTunnelButton('cloudflare', !!(data.cloudflare && data.cloudflare.running));
    const ts = data.tailscale || {};
    setTunnelButton('tailscale', !!ts.funnel);
  } catch (e) { /* tiles just stay as-is */ }
}

async function toggleTunnel(provider) {
  const btn = tunnelBtn(provider);
  if (!btn) return;
  const running = btn.classList.contains('active');
  const action = running ? 'stop' : 'start';
  // Stopping the cloudflare tunnel takes the public site offline — confirm it.
  if (action === 'stop' && provider === 'cloudflare') {
    if (!confirm('Stop the cloudflare tunnel? This takes the public site offline.')) {
      return;
    }
  }
  const pendingLabel = (action === 'start' ? 'Starting' : 'Stopping') + '…';
  btn.textContent = pendingLabel;
  btn.setAttribute('aria-label', (action === 'start' ? 'Starting ' : 'Stopping ') + provider + ' tunnel');
  btn.disabled = true;
  toast('tunnel ' + provider + ': ' + action + 'ing...');
  try {
    const data = await apiPost(
      '/api/tunnel/' + encodeURIComponent(provider) + '/' + action, {}
    );
    if (action === 'stop') {
      setTunnelButton(provider, false);
      toast('tunnel ' + provider + ' stopped.', '');
    } else if (data.url || data.running) {
      setTunnelButton(provider, true);
      toast('tunnel: ' + (data.url || 'started'), 'success');
    } else {
      setTunnelButton(provider, false);
      toast('tunnel ' + provider + ': ' + (data.error || 'no url'), 'error');
    }
  } catch (e) {
    toast('tunnel ' + provider + ': ' + (e.message || 'failed'), 'error');
  } finally {
    // Reconcile with reality (e.g. a managed unit that refused to die).
    await loadTunnelStatus();
  }
}

// ── View Navigation ────────────────────
let currentView = 'dashboard';

const viewTitles = {
  dashboard: 'Overview',
  catalog: 'Servers',
  evals: 'Performance',
  deploy: 'Deploy',
  settings: 'Settings',
  pr: 'PR control',
};

function switchView(name, quiet) {
  currentView = name;
  const title = document.getElementById('page-title');
  if (title) title.textContent = viewTitles[name] || name;
  document.querySelectorAll('.view').forEach(v => {
    v.classList.toggle('active', v.id === 'view-' + name);
  });
  document.querySelectorAll('.sidebar-nav .tab').forEach(t => {
    const on = t.dataset.view === name;
    t.classList.toggle('active', on);
    if (on) t.setAttribute('aria-current', 'page');
    else t.removeAttribute('aria-current');
  });
  if (name === 'dashboard') setTimeout(drawLatencyStrip, 0);
  loadViewData(name);
  if (!quiet) writeUrlState();
}

async function loadViewData(name) {
  try {
    if (name === 'catalog') await loadCatalogView();
    else if (name === 'evals') await loadEvalsView();
    else if (name === 'deploy') await loadDeployView();
    else if (name === 'settings') await loadSettingsView();
    else if (name === 'pr') await loadPRView();
  } catch (e) {
    console.error('view load error:', e);
  }
}

async function loadCatalogView() {
  const search = document.getElementById('catalog-search');
  if (search && search.value.trim() !== catalogQuery) {
    catalogQuery = search.value.trim();
  }
  const seq = ++catalogLoadSeq;
  const data = await api(catalogApiPath());
  if (seq !== catalogLoadSeq) return;  // superseded by a newer search/filter load; ignore stale response
  const grid = document.getElementById('catalog-grid');
  catalogItems = filterServers(data.servers || []);
  const items = catalogFilter === 'all'
    ? catalogItems
    : catalogItems.filter(s => serverState(s) === catalogFilter);
  const serverCount = items.length;
  document.getElementById('catalog-count').textContent =
    serverCount === 1 ? '1 server' : serverCount + ' servers';
  grid.innerHTML = '';
  if (!items.length) {
    const empty = document.createElement('div');
    empty.className = 'view-empty';
    empty.style.gridColumn = '1 / -1';
    const addLink = (label, handler) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'view-empty-link';
      btn.textContent = label;
      btn.onclick = handler;
      empty.appendChild(btn);
    };
    const hasQuery = !!catalogQuery;
    const hasFilter = catalogFilter !== 'all';
    if (hasQuery && hasFilter) {
      // Both constraints are active, so either could be the cause: describe the
      // combined state and offer both recovery actions rather than only one.
      empty.textContent = 'No servers match "' + catalogQuery + '" in this status.';
      addLink('Clear search', clearCatalogSearch);
      addLink('Switch filter to all', resetCatalogFilter);
    } else if (hasQuery) {
      empty.textContent = 'No servers match "' + catalogQuery + '".';
      addLink('Clear search', clearCatalogSearch);
    } else if (hasFilter) {
      empty.textContent = 'No servers in this status.';
      addLink('Switch filter to all', resetCatalogFilter);
    } else {
      empty.textContent = 'No servers in this profile. Switch profiles in the top bar.';
    }
    grid.appendChild(empty);
    return;
  }
  for (const s of items) {
    const card = document.createElement('div');
    card.className = 'server-card interactive';
    card.dataset.name = s.name;
    card.tabIndex = 0;
    card.setAttribute('role', 'button');
    card.setAttribute('aria-label', s.name + ', ' + serverState(s));

    const head = document.createElement('div');
    head.className = 'server-card-head';
    const nameEl = document.createElement('span');
    nameEl.className = 'server-card-name';
    nameEl.textContent = s.name;
    const toggle = document.createElement('div');
    const pending = s.enabled && s.env_configured === false;
    toggle.className = 'toggle-switch'
      + (s.enabled ? (pending ? ' pending' : ' on') : '');
    toggle.setAttribute('role', 'switch');
    toggle.setAttribute('aria-checked', String(!!s.enabled));
    // Action verb matches visible palette language (Enable/Disable), not a
    // generic "Toggle", so screen readers and sighted UI stay consistent.
    toggle.setAttribute(
      'aria-label', (s.enabled ? 'Disable ' : 'Enable ') + s.name + ' server'
    );
    toggle.setAttribute('tabindex', '0');
    toggle.title = pending ? 'On, but needs credentials to connect' : '';
    toggle.dataset.name = s.name;
    head.appendChild(nameEl);
    head.appendChild(toggle);
    card.appendChild(head);

    const badges = document.createElement('div');
    badges.className = 'badges';
    badges.appendChild(makeBadge(s.transport, s.transport));
    badges.appendChild(makeBadge(s.risk, s.risk));
    const st = serverState(s);
    badges.appendChild(makeBadge(
      st === 'ready' ? 'low' : (st === 'needs' ? 'medium' : 'high'),
      st === 'ready' ? 'ready' : (st === 'needs' ? 'needs credentials' : 'disabled')
    ));
    card.appendChild(badges);

    const desc = document.createElement('div');
    desc.className = 'server-card-desc';
    desc.textContent = s.description || '';
    card.appendChild(desc);

    const meta = document.createElement('div');
    meta.className = 'server-card-meta';
    const cost = document.createElement('span');
    cost.className = 'cost-dots';
    cost.title = 'context cost';
    const c = Math.max(0, Math.min(5, Number(s.context_cost) || 0));
    for (let i = 0; i < 5; i++) {
      const d = document.createElement('i');
      if (i < c) d.className = 'on';
      cost.appendChild(d);
    }
    const stChip = document.createElement('span');
    stChip.className = 'status-chip';
    const dot = document.createElement('span');
    dot.className = 'status-dot ' + (st === 'ready' ? 'ok' : st === 'needs' ? 'warn' : 'off');
    const lbl = document.createElement('span');
    lbl.className = 'status-label';
    lbl.textContent = st === 'ready' ? 'Ready' : st === 'needs' ? 'Needs credentials' : 'Disabled';
    stChip.appendChild(dot); stChip.appendChild(lbl);
    meta.appendChild(cost);
    meta.appendChild(stChip);
    card.appendChild(meta);

    grid.appendChild(card);
  }
}

function enableHint(name, enabled) {
  // Tell the operator the truth: enabling a server with missing credentials
  // does not connect it. Point them at exactly what's needed.
  if (!enabled) return name + ' disabled.';
  const s = servers.find(x => x.name === name);
  if (s && s.env_required && s.env_required.length && !s.env_configured) {
    return name + ' enabled. Set ' + s.env_required.join(', ') + ' to connect it.';
  }
  return name + ' enabled.';
}

async function toggleServerCard(name, el) {
  try {
    const data = await apiPost(
      '/api/mcp/servers/' + encodeURIComponent(name) + '/toggle', {}
    );
    // Keep the in-memory catalog in sync even if WS is down.
    const s = servers.find(x => x.name === name);
    if (s) s.enabled = !!data.enabled;
    const ci = catalogItems.find(x => x.name === name);
    if (ci) ci.enabled = !!data.enabled;
    const pending = data.enabled && s && s.env_configured === false;
    el.classList.remove('on', 'pending');
    if (data.enabled) el.classList.add(pending ? 'pending' : 'on');
    el.setAttribute('aria-checked', String(!!data.enabled));
    el.setAttribute(
      'aria-label', (data.enabled ? 'Disable ' : 'Enable ') + name + ' server'
    );
    el.title = pending ? 'On, but needs credentials to connect' : '';
    toast(enableHint(name, !!data.enabled), data.enabled ? 'success' : '');
    buildNodes();
    if (currentView === 'catalog') await loadCatalogView();
    // Enabling something that still needs a token? Bring up the connect popup.
    if (pending) promptCredentials(name);
  } catch (e) {
    toast(name + ': ' + (e.message || 'failed'), 'error');
  }
}

async function openServerDetail(name) {
  try {
    const data = await api('/api/mcp/servers/' + encodeURIComponent(name));
    openDetail(data);
  } catch (e) {
    toast(name + ': ' + (e.message || 'not found'), 'error');
  }
}

async function loadEvalsView() {
  const data = await api('/api/evals');
  const summary = data.summary || {};
  const tc = data.tool_calls || {};

  const sumEl = document.getElementById('eval-summary');
  sumEl.innerHTML = '';
  const stats = [
    ['calls', tc.total || 0],
    ['tools', tc.unique_tools || 0],
    ['success', (summary.overall_success_rate || 0) + '%'],
    ['errors', summary.total_errors || 0],
  ];
  for (const [label, val] of stats) {
    const stat = document.createElement('div');
    stat.className = 'eval-stat';
    const big = document.createElement('span');
    big.className = 'big-num tnum';
    big.textContent = val;
    const lbl = document.createElement('span');
    lbl.className = 'lbl';
    lbl.textContent = label;
    stat.appendChild(big);
    stat.appendChild(lbl);
    sumEl.appendChild(stat);
  }

  const perTool = tc.per_tool || {};
  const entries = Object.entries(perTool).sort((a, b) => b[1].total - a[1].total);
  const tbody = document.getElementById('eval-tbody');
  tbody.innerHTML = '';
  if (!entries.length) {
    const tr = document.createElement('tr');
    const cell = td('');
    cell.colSpan = 4;
    cell.className = 'view-empty';
    cell.textContent = 'No tool calls recorded yet. Run a tool to see it here.';
    tr.appendChild(cell);
    tbody.appendChild(tr);
    return;
  }
  for (const [name, s] of entries) {
    const rate = s.success_rate || 0;
    const color = rate >= 90 ? 'var(--ok)' : rate >= 50 ? 'var(--warn)' : 'var(--err)';
    const avg = Math.round(s.avg_duration_ms || 0);
    const tr = document.createElement('tr');
    tr.appendChild(td(name));
    tr.appendChild(td(String(s.total)));
    const c = td('');
    const hbar = document.createElement('span');
    hbar.className = 'hbar';
    const track = document.createElement('span');
    track.className = 'hbar-track';
    const fill = document.createElement('span');
    fill.className = 'hbar-fill';
    fill.style.width = rate + '%';
    fill.style.background = color;
    track.appendChild(fill);
    const lbl = document.createElement('span');
    lbl.className = 'hbar-label';
    lbl.textContent = rate + '%';
    hbar.appendChild(track);
    hbar.appendChild(lbl);
    c.appendChild(hbar);
    tr.appendChild(c);
    const latCell = td('');
    const pill = document.createElement('span');
    pill.className = 'lat-pill ' + latencyClass(avg);
    pill.textContent = avg + 'ms';
    latCell.appendChild(pill);
    tr.appendChild(latCell);
    tbody.appendChild(tr);
  }
}

let deployFormats = [];

async function loadDeployView() {
  const data = await api('/api/deploy');
  deployFormats = data.formats || [];
  const tabs = document.getElementById('deploy-tabs');
  tabs.textContent = '';
  document.getElementById('deploy-panel').removeAttribute('aria-labelledby');
  const usedTabIds = new Set();
  for (const f of deployFormats) {
    const btn = document.createElement('button');
    btn.className = 'code-tab interactive';
    btn.dataset.fmt = f.name;
    btn.textContent = f.name;
    let tabId = 'tab-deploy-' + f.name.replace(/[^a-z0-9]/gi, '-');
    if (usedTabIds.has(tabId)) {
      let suffix = 2;
      while (usedTabIds.has(tabId + '-' + suffix)) suffix++;
      tabId += '-' + suffix;
    }
    usedTabIds.add(tabId);
    btn.id = tabId;
    btn.setAttribute('role', 'tab');
    btn.setAttribute('aria-selected', 'false');
    btn.setAttribute('aria-controls', 'deploy-panel');
    tabs.appendChild(btn);
  }
  if (deployFormats[0]) await selectDeployFormat(deployFormats[0].name);
}

async function selectDeployFormat(fmt) {
  document.querySelectorAll('.code-tab').forEach(t => {
    const active = t.dataset.fmt === fmt;
    t.classList.toggle('active', active);
    t.setAttribute('aria-selected', active ? 'true' : 'false');
    if (active) {
      document.getElementById('deploy-panel').setAttribute('aria-labelledby', t.id);
    }
  });
  const code = document.getElementById('deploy-code');
  const desc = document.getElementById('deploy-desc');
  try {
    const data = await api('/api/deploy/' + encodeURIComponent(fmt));
    code.textContent = JSON.stringify(data, null, 2);
    desc.textContent = data.description
      || (deployFormats.find(f => f.name === fmt) || {}).description
      || '';
  } catch (e) {
    code.textContent = '# ' + (e.message || 'error');
    desc.textContent = '';
  }
}

function copyDeployCode(btn) {
  if (btn.dataset.copying) return;
  const text = document.getElementById('deploy-code').textContent || '';
  if (navigator.clipboard && navigator.clipboard.writeText) {
    btn.dataset.copying = '1';
    const originalText = btn.textContent;
    navigator.clipboard.writeText(text).then(
      () => {
        toast('copied to clipboard', 'success');
        btn.textContent = 'Copied!';
        setTimeout(() => {
          btn.textContent = originalText;
          delete btn.dataset.copying;
        }, 2000);
      },
      () => {
        toast('clipboard access denied', 'error');
        delete btn.dataset.copying;
      }
    );
  } else {
    toast('clipboard unavailable', 'error');
  }
}

async function loadSettingsView() {
  const data = await api('/api/settings');
  const auth = data.auth || {};
  document.getElementById('set-auth-mode').value = (auth.mode in { none: 1, apikey: 1, oauth: 1 })
    ? auth.mode : 'none';
  document.getElementById('set-cors').value = (data.cors_origins || []).join(', ');
  document.getElementById('set-rate-limit').value = data.rate_limit_per_min || 0;
  document.getElementById('set-profile').value = data.default_profile || 'core';
  document.getElementById('set-storage').value = data.storage_backend || 'sqlite';
}

async function loadPRView(btn) {
  const originalText = btn ? btn.textContent : null;
  const originalAria = btn ? btn.getAttribute('aria-label') : null;
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Refreshing…';
    btn.setAttribute('aria-label', 'Refreshing pull requests…');
    btn.setAttribute('aria-busy', 'true');
  }
  const grid = document.getElementById('pr-grid');
  const count = document.getElementById('pr-count');
  const seq = ++prLoadSeq;
  try {
    const data = await api('/api/pr/list?state=open&limit=30');
    if (seq !== prLoadSeq) return;  // superseded by a newer refresh; ignore stale response
    const pulls = data.pulls || [];
    const total = data.count ?? pulls.length;
    count.textContent = total + ' open PR' + (total === 1 ? '' : 's');
    grid.replaceChildren();
    if (!pulls.length) {
      const empty = document.createElement('div');
      empty.className = 'view-empty';
      empty.textContent = 'No open pull requests.';
      grid.appendChild(empty);
      return;
    }
    for (const pr of pulls) {
      const card = document.createElement('div');
      card.className = 'pr-card';
      const verdict = (pr.gate && pr.gate.verdict) || 'WARN';
      const reasons = (pr.gate && pr.gate.reasons) || [];
      const top = document.createElement('div');
      top.className = 'pr-top';
      const title = document.createElement('div');
      title.className = 'pr-title';
      title.textContent = '#' + pr.number + ' ' + (pr.title || '');
      const badge = document.createElement('span');
      badge.className = 'pr-verdict ' + verdict;
      badge.textContent = verdict;
      top.appendChild(title);
      top.appendChild(badge);
      card.appendChild(top);

      const meta = document.createElement('div');
      meta.className = 'pr-meta';
      meta.textContent = (pr.head_ref || '') + ' → ' + (pr.base_ref || '') +
        (pr.head_sha ? '  (' + pr.head_sha.slice(0, 7) + ')' : '');
      card.appendChild(meta);

      if (reasons.length) {
        const rc = document.createElement('div');
        rc.className = 'pr-reasons';
        for (const r of reasons) {
          const chip = document.createElement('span');
          chip.className = 'badge warn';
          chip.textContent = r;
          rc.appendChild(chip);
        }
        card.appendChild(rc);
      }

      if (verdict === 'PASS') {
        const mergeBtn = document.createElement('button');
        mergeBtn.className = 'btn-save interactive pr-merge-btn';
        mergeBtn.textContent = 'Merge (squash)';
        mergeBtn.setAttribute('data-pr', String(pr.number));
        mergeBtn.setAttribute('data-head', pr.head_sha || '');
        mergeBtn.addEventListener('click', onMergeClick);
        card.appendChild(mergeBtn);
        if (pr.head_sha) {
          const note = document.createElement('div');
          note.className = 'pr-head-note';
          note.textContent = 'will merge head ' + pr.head_sha.slice(0, 7);
          card.appendChild(note);
        }
      }
      grid.appendChild(card);
    }
  } catch (e) {
    if (seq !== prLoadSeq) return;  // superseded by a newer refresh; ignore stale error
    count.textContent = 'PR list unavailable';
    grid.replaceChildren();
    const empty = document.createElement('div');
    empty.className = 'view-empty';
    empty.textContent = 'PR control needs the gh CLI and a GitHub token. ' +
      'Run `kater pr` tools or check the server environment.';
    grid.appendChild(empty);
  } finally {
    if (btn && originalText !== null) {
      btn.disabled = false;
      btn.textContent = originalText;
      if (originalAria) btn.setAttribute('aria-label', originalAria);
      btn.removeAttribute('aria-busy');
    }
  }
}

async function onMergeClick(e) {
  const btn = e.currentTarget;
  const number = parseInt(btn.dataset.pr);
  const head = btn.dataset.head || '';
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Merging...';
  btn.setAttribute('aria-busy', 'true');
  try {
    await apiPost('/api/pr/' + number + '/merge', { expected_head_sha: head, actor: 'dashboard' });
    toast('merged #' + number, 'success');
    await loadPRView();
  } catch (err) {
    const detail = (err.data && err.data.error) ? err.data.error : (err.message || 'failed');
    toast('merge blocked: ' + detail, 'error');
    btn.disabled = false;
    btn.textContent = originalText;
    btn.removeAttribute('aria-busy');
  }
}


async function saveSettings(btn) {
  const originalText = btn ? btn.textContent : 'Save settings';
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Saving...';
    btn.setAttribute('aria-busy', 'true');
  }
  const body = {
    auth: { mode: document.getElementById('set-auth-mode').value },
    cors_origins: document.getElementById('set-cors').value
      .split(',').map(s => s.trim()).filter(Boolean),
    rate_limit_per_min: parseInt(document.getElementById('set-rate-limit').value) || 0,
    default_profile: document.getElementById('set-profile').value,
    storage_backend: document.getElementById('set-storage').value,
  };
  try {
    await apiPost('/api/settings', body);
    toast('settings saved', 'success');
  } catch (e) {
    toast('failed to save settings: ' + (e.message || ''), 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = originalText;
      btn.removeAttribute('aria-busy');
    }
  }
}

function initKeyboard() {
  document.addEventListener('keydown', (e) => {
    // Command palette: ⌘K / Ctrl+K toggles.
    if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
      e.preventDefault();
      if (paletteIsOpen()) closePalette(); else openPalette();
      return;
    }
    if (e.key === 'Escape') {
      if (paletteIsOpen()) { closePalette(); return; }
      if (document.getElementById('cred-modal').classList.contains('show')) {
        closeCredentialsModal(); return;
      }
      closeDetail();
      return;
    }
    const tag = e.target.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (paletteIsOpen()) return;

    if (e.key >= '1' && e.key <= '5') {
      const views = ['dashboard', 'catalog', 'evals', 'deploy', 'settings'];
      const v = views[parseInt(e.key) - 1];
      if (v) switchView(v);
      return;
    }
    // Overview list navigation (vim-style).
    if (currentView === 'dashboard') {
      if (e.key === 'j') { e.preventDefault(); moveRouteSel(1); return; }
      if (e.key === 'k') { e.preventDefault(); moveRouteSel(-1); return; }
      if (e.key === 'Enter') { e.preventDefault(); openSelectedRoute(); return; }
    }
    if (e.key === '/') {
      if (currentView === 'catalog') {
        e.preventDefault();
        const s = document.getElementById('catalog-search');
        if (s) s.focus();
      } else {
        e.preventDefault();
        openPalette();
      }
      return;
    }
    if (e.key === 'r') { loadViewData(currentView); loadStatusSafe(); }
  });
}

// ── Start ──────────────────────────────
window.addEventListener('DOMContentLoaded', init);

"""


def render_dashboard(ws_port: int = 9092) -> str:
    config = f"<script>window.KATER_CONFIG={{wsPort:{int(ws_port)}}}</script>\n"
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        "<title>Kater — MCP Gateway</title>\n"
        '<meta name="color-scheme" content="dark">\n'
        f"<style>{_CSS}</style>\n"
        "</head>\n<body>\n"
        f"{_HTML}\n"
        f"{config}"
        f"<script>{_JS}</script>\n"
        "</body>\n</html>\n"
    )
