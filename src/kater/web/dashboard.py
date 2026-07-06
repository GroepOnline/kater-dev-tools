from __future__ import annotations

_CSS = r"""
:root {
  /* ── Design tokens ──────────────────────────────────────────────
     Amber-console identity, enterprise discipline:
     one accent (amber), semantic status colors only (jade/coral/ice),
     neutral graphite surfaces, no decorative gradients or glows. */

  /* Surfaces (graphite, solid — crisp borders, no blur-dependence) */
  --bg: #0b0c0e;
  --surface: #121316;
  --surface-2: #17181c;
  --surface-3: #1d1f24;
  --border: #24262c;
  --border-strong: #32353d;

  /* Text — AA on dark surfaces */
  --text: #e8e9ec;
  --text-dim: #a0a4ad;
  --text-bright: #f7f8fa;

  /* Single accent */
  --accent: #ffb224;
  --accent-hover: #ffc14d;
  --accent-soft: rgba(255, 178, 36, 0.12);

  /* Semantic status — meaning only, never decoration */
  --ok: #3ecf8e;
  --ok-soft: rgba(62, 207, 142, 0.12);
  --err: #f2695c;
  --err-soft: rgba(242, 105, 92, 0.12);
  --info: #6fb7e0;
  --info-soft: rgba(111, 183, 224, 0.12);

  /* 4px spacing scale */
  --sp-1: 4px; --sp-2: 8px; --sp-3: 12px; --sp-4: 16px;
  --sp-5: 20px; --sp-6: 24px; --sp-8: 32px;

  /* Radius scale */
  --radius-sm: 4px;
  --radius: 6px;
  --radius-lg: 8px;

  /* Two font stacks: UI sans + mono. Nothing external. */
  --font: ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  --mono: ui-monospace, 'SF Mono', 'Cascadia Code', 'JetBrains Mono', 'Consolas', monospace;

  /* Motion: purposeful micro-transitions only */
  --t-fast: 120ms ease;
  --t-med: 150ms ease;

  --shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  color-scheme: dark;
}

* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { height: 100%; overflow: hidden; }
body {
  font-family: var(--font);
  background: var(--bg);
  color: var(--text);
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

::selection { background: var(--accent-soft); color: var(--text-bright); }

/* Quality floor: every interactive element shows a visible focus ring. */
a:focus-visible, button:focus-visible, input:focus-visible,
select:focus-visible, [role="switch"]:focus-visible, [tabindex]:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: var(--radius-sm);
}

/* Visually hidden but accessible to screen readers. */
.sr-only {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
}
.skip-link:focus {
  position: fixed; left: var(--sp-3); top: var(--sp-2); z-index: 999;
  width: auto; height: auto; margin: 0; padding: var(--sp-2) var(--sp-4);
  clip: auto; overflow: visible; white-space: nowrap;
  background: var(--accent); color: #000; border-radius: var(--radius);
  font-family: var(--mono); font-size: 13px; text-decoration: none;
}

/* Respect reduced motion: kill every transition and animation. */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
  }
}

/* ── Boot ───────────────────────────────────────────── */
#boot {
  position: fixed; inset: 0; z-index: 100;
  background: var(--bg);
  display: flex; align-items: center; justify-content: center;
  font-family: var(--mono); font-size: 13px; color: var(--text-dim);
}
#boot.done { opacity: 0; pointer-events: none; transition: opacity var(--t-med); }

/* ── Layout ─────────────────────────────────────────── */
#app {
  position: relative; z-index: 1;
  height: 100vh;
  display: flex; flex-direction: column;
}

/* ── Topbar ─────────────────────────────────────────── */
.topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 var(--sp-5); min-height: 56px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  gap: var(--sp-4);
}
.topbar-left { display: flex; align-items: center; gap: var(--sp-4); }
.brand {
  font-family: var(--mono); font-weight: 700; font-size: 14px;
  letter-spacing: 2px; color: var(--text-bright);
  display: flex; align-items: center; gap: var(--sp-2);
}
.brand-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--accent);
}
.version-tag {
  font-family: var(--mono); font-size: 11px; color: var(--text-dim);
  padding: 2px var(--sp-2); border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  font-variant-numeric: tabular-nums;
}
.profile-pills { display: flex; gap: var(--sp-1); flex-wrap: wrap; }
.pill {
  font-family: var(--mono); font-size: 11px;
  padding: 4px 10px; border-radius: 999px;
  border: 1px solid var(--border); color: var(--text-dim);
  background: transparent;
  cursor: pointer; user-select: none;
  transition: color var(--t-fast), border-color var(--t-fast), background-color var(--t-fast);
}
.pill:hover {
  color: var(--text); border-color: var(--border-strong); background: var(--surface-2);
}
.pill:active { background: var(--surface-3); }
.pill.active { background: var(--accent); color: #000; border-color: var(--accent); }
.pill.active:hover { background: var(--accent-hover); border-color: var(--accent-hover); }
.topbar-right { display: flex; align-items: center; justify-content: flex-end; gap: var(--sp-2); }
.status-chip, .auth-badge {
  font-family: var(--mono); font-size: 11px; color: var(--text-dim);
  display: flex; align-items: center; gap: 7px;
  min-height: 30px; padding: 0 var(--sp-3);
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface-2);
}
.auth-dot, .status-dot {
  width: 6px; height: 6px; border-radius: 50%; background: var(--ok);
  flex-shrink: 0;
}
.status-dot.off { background: var(--text-dim); }
.status-dot.warn { background: var(--accent); }
.status-dot.on { background: var(--ok); }

/* ── Panel grid ─────────────────────────────────────── */
.bento {
  flex: 1; display: grid;
  grid-template-columns: 1fr 340px;
  grid-template-rows: 1fr auto;
  gap: var(--sp-3); padding: var(--sp-3);
  overflow: hidden;
}
.tile {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  display: flex; flex-direction: column;
  overflow: hidden;
}
.tile-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--sp-2) var(--sp-4); min-height: 36px;
  border-bottom: 1px solid var(--border);
}
.tile-title {
  font-family: var(--mono); font-size: 11px; font-weight: 600;
  letter-spacing: 1px; text-transform: uppercase; color: var(--text-dim);
  font-variant-numeric: tabular-nums;
}

/* ── Topology panel ─────────────────────────────────── */
.constellation-tile { grid-column: 1; grid-row: 1; }
#constellation-canvas { flex: 1; width: 100%; cursor: pointer; }

/* ── Telemetry panel ────────────────────────────────── */
.telemetry-tile { grid-column: 2; grid-row: 1; }
.telemetry-stream {
  flex: 1; overflow-y: auto;
  font-family: var(--mono); font-size: 11px;
  font-variant-numeric: tabular-nums;
  padding: var(--sp-2) var(--sp-3);
  scrollbar-width: thin;
  scrollbar-color: var(--border-strong) transparent;
}
.telemetry-stream::-webkit-scrollbar { width: 4px; }
.telemetry-stream::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 2px; }
.tlm-row {
  display: flex; align-items: center; gap: var(--sp-2);
  padding: 3px 0;
  white-space: nowrap;
  transition: opacity var(--t-med);
}
.tlm-row.faded { opacity: 0.45; }
.tlm-time { color: var(--text-dim); flex-shrink: 0; }
.tlm-icon { flex-shrink: 0; width: 14px; text-align: center; }
.tlm-icon.ok { color: var(--ok); }
.tlm-icon.err { color: var(--err); }
.tlm-name { color: var(--text); overflow: hidden; text-overflow: ellipsis; }
.tlm-ms { color: var(--text-dim); margin-left: auto; flex-shrink: 0; }

/* ── Metric cards ───────────────────────────────────── */
.stats-row {
  grid-column: 1 / -1; grid-row: 2;
  display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--sp-3);
}
.mini-tile {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--sp-4);
}
.mini-label {
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  letter-spacing: 1px; text-transform: uppercase; color: var(--text-dim);
  margin-bottom: var(--sp-2);
}
.mini-content { display: flex; align-items: baseline; gap: var(--sp-5); }
.big-num {
  font-family: var(--mono); font-size: 26px; font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--text-bright); line-height: 1;
}
.big-sub { font-family: var(--mono); font-size: 12px; color: var(--text-dim); }
.btn-tunnel {
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  letter-spacing: 0.5px; text-transform: uppercase;
  padding: 4px 10px; border-radius: var(--radius-sm); cursor: pointer;
  border: 1px solid var(--border-strong); color: var(--text);
  background: transparent;
  transition: color var(--t-fast), border-color var(--t-fast), background-color var(--t-fast);
}
.btn-tunnel:hover { border-color: var(--accent); color: var(--accent); }
.btn-tunnel:active { background: var(--accent-soft); }
.btn-tunnel:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-tunnel.active { background: var(--ok-soft); border-color: var(--ok); color: var(--ok); }
.tunnel-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--sp-1) 0;
}
.tunnel-name { font-family: var(--mono); font-size: 12px; color: var(--text); }

/* ── Command bar ────────────────────────────────────── */
.command-bar {
  height: 40px; min-height: 40px;
  display: flex; align-items: center;
  padding: 0 var(--sp-4); gap: var(--sp-2);
  background: var(--surface);
  border-top: 1px solid var(--border);
}
.cmd-prompt { font-family: var(--mono); font-weight: 700; color: var(--accent); }
#cmd-input {
  flex: 1; background: transparent; border: none; outline: none;
  font-family: var(--mono); font-size: 13px; color: var(--text);
}
#cmd-input::placeholder { color: var(--text-dim); }

/* ── Detail panel ───────────────────────────────────── */
.detail-panel {
  position: fixed; top: 95px; right: 0; bottom: 40px;
  width: 320px; z-index: 50;
  background: var(--surface-2);
  border-left: 1px solid var(--border-strong);
  box-shadow: var(--shadow);
  transform: translateX(100%);
  transition: transform var(--t-med);
  display: flex; flex-direction: column;
  overflow-y: auto;
}
.detail-panel.open { transform: translateX(0); }
.detail-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--sp-4); border-bottom: 1px solid var(--border);
}
.detail-name {
  font-family: var(--mono); font-size: 15px; font-weight: 700;
  color: var(--text-bright);
}
.detail-close {
  cursor: pointer; color: var(--text-dim); font-size: 18px;
  width: 28px; height: 28px; border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center;
  transition: color var(--t-fast), background-color var(--t-fast);
}
.detail-close:hover { color: var(--text-bright); background: var(--surface-3); }
.detail-close:active { background: var(--border); }
.detail-section { padding: var(--sp-3) var(--sp-4); border-bottom: 1px solid var(--border); }
.detail-label {
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  letter-spacing: 1px; text-transform: uppercase; color: var(--text-dim);
  margin-bottom: var(--sp-2);
}
.detail-value {
  font-family: var(--mono); font-size: 12px; color: var(--text);
  word-break: break-all;
}
.detail-link {
  font-family: var(--mono); font-size: 12px; color: var(--accent);
  text-decoration: none; word-break: break-all;
}
.detail-link:hover { text-decoration: underline; color: var(--accent-hover); }
.detail-status {
  display: inline-flex; align-items: center; gap: var(--sp-2);
  font-size: 12px; color: var(--text); line-height: 1.45;
}
.detail-status::before {
  content: ''; width: 8px; height: 8px; border-radius: 50%;
  background: var(--text-dim); flex-shrink: 0;
}
.detail-status.ready { color: var(--ok); }
.detail-status.ready::before { background: var(--ok); }
.detail-status.needs { color: var(--accent); }
.detail-status.needs::before { background: var(--accent); }
.detail-status.off { color: var(--text-dim); }
.badges { display: flex; gap: 6px; flex-wrap: wrap; }
.badge {
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  padding: 2px var(--sp-2); border-radius: var(--radius-sm);
  text-transform: uppercase; letter-spacing: 0.5px;
}
.badge.stdio { background: var(--ok-soft); color: var(--ok); }
.badge.sse, .badge.http { background: var(--info-soft); color: var(--info); }
.badge.native, .badge.local { background: var(--accent-soft); color: var(--accent); }
.badge.high { background: var(--err-soft); color: var(--err); }
.badge.medium { background: var(--accent-soft); color: var(--accent); }
.badge.low { background: var(--ok-soft); color: var(--ok); }
.detail-actions { padding: var(--sp-4); display: flex; gap: var(--sp-2); }
.btn-action {
  flex: 1; font-family: var(--mono); font-size: 12px; font-weight: 600;
  padding: var(--sp-2); border-radius: var(--radius-sm); cursor: pointer;
  border: 1px solid var(--border-strong); background: transparent; color: var(--text);
  text-transform: uppercase; letter-spacing: 0.5px;
  transition: color var(--t-fast), border-color var(--t-fast),
    background-color var(--t-fast), opacity var(--t-fast);
}
.btn-action:hover { border-color: var(--text-dim); background: var(--surface-3); }
.btn-action:active { background: var(--border); }
.btn-action:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-action.primary { background: var(--accent); border-color: var(--accent); color: #000; }
.btn-action.primary:hover:not(:disabled) {
  background: var(--accent-hover); border-color: var(--accent-hover);
}
.btn-action.danger {
  background: transparent; border-color: var(--err); color: var(--err);
}
.btn-action.danger:hover:not(:disabled) { background: var(--err-soft); }

/* ── Toast ──────────────────────────────────────────── */
.toast-container {
  position: fixed; bottom: 52px; left: 50%;
  transform: translateX(-50%); z-index: 200;
  display: flex; flex-direction: column; gap: var(--sp-2); align-items: center;
}
.toast {
  font-family: var(--mono); font-size: 12px;
  padding: var(--sp-2) var(--sp-4); border-radius: var(--radius);
  background: var(--surface-2); border: 1px solid var(--border-strong);
  box-shadow: var(--shadow);
  animation: toast-in 120ms ease-out, toast-out 120ms ease-in 2.5s forwards;
}
.toast.success { border-color: var(--ok); }
.toast.error { border-color: var(--err); }
@keyframes toast-in { from { opacity: 0; transform: translateY(6px); } }
@keyframes toast-out { to { opacity: 0; transform: translateY(6px); } }

/* ── Nav tabs ───────────────────────────────────────── */
.nav-tabs {
  display: flex; gap: 0; padding: 0 var(--sp-3); align-items: stretch;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  min-height: 38px;
  overflow-x: auto;
}
.tab {
  font-family: var(--mono); font-size: 11px; font-weight: 600;
  letter-spacing: 1px; text-transform: uppercase; color: var(--text-dim);
  min-height: 44px; padding: 0 var(--sp-4); cursor: pointer;
  border: none; background: transparent;
  display: flex; align-items: center; position: relative;
  white-space: nowrap;
  transition: color var(--t-fast);
}
.tab:hover { color: var(--text); }
.tab.active { color: var(--text-bright); }
.tab.active::after {
  content: ''; position: absolute; bottom: 0; left: 14px; right: 14px;
  height: 2px; background: var(--accent); border-radius: 2px 2px 0 0;
}
.tab-num {
  font-family: var(--mono); font-size: 9px; margin-left: var(--sp-2);
  padding: 1px 4px; border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  color: var(--text-dim);
  transition: color var(--t-fast), border-color var(--t-fast);
}
.tab.active .tab-num { border-color: var(--accent); color: var(--accent); }

/* ── Views ──────────────────────────────────────────── */
.view { display: none; flex: 1; overflow: hidden; }
.view.active { display: flex; flex-direction: column; }
.view-scroll {
  flex: 1; overflow-y: auto;
  scrollbar-width: thin; scrollbar-color: var(--border-strong) transparent;
}
.view-scroll::-webkit-scrollbar { width: 6px; }
.view-scroll::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 3px; }
.view-header {
  padding: var(--sp-3) var(--sp-4); border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
  min-height: 38px;
}
.view-title {
  font-family: var(--mono); font-size: 13px; font-weight: 700;
  color: var(--text-bright);
}
.view-empty {
  padding: 48px var(--sp-5); text-align: center;
  font-family: var(--mono); font-size: 12px; color: var(--text-dim);
}
.view-empty-link {
  color: var(--accent); cursor: pointer; text-decoration: underline;
  background: transparent; border: none; font-family: inherit; font-size: inherit;
  padding: 0; margin-left: var(--sp-1);
}
.view-empty-link:hover { color: var(--accent-hover); }
.catalog-toolbar {
  padding: var(--sp-3) var(--sp-3) 0;
  position: sticky; top: 0; z-index: 2;
  background: var(--bg);
}
#catalog-search { width: 100%; max-width: 420px; }

/* ── Server grid (Catalog) ──────────────────────────── */
.server-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--sp-3); padding: var(--sp-3);
}
.server-card {
  position: relative;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); padding: var(--sp-4); cursor: pointer;
  overflow: hidden;
  transition: border-color var(--t-fast), background-color var(--t-fast);
}
.server-card::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 2px;
  background: var(--accent); opacity: 0;
  transition: opacity var(--t-fast);
}
.server-card:hover { border-color: var(--border-strong); background: var(--surface-2); }
.server-card:hover::before { opacity: 1; }
.server-card-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: var(--sp-2); gap: var(--sp-2);
}
.server-card-name {
  font-family: var(--mono); font-size: 13px; font-weight: 700;
  color: var(--text-bright);
  overflow: hidden; text-overflow: ellipsis;
}
.server-card-desc {
  font-size: 12px; color: var(--text-dim); line-height: 1.45;
  display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; overflow: hidden;
}
.toggle-switch {
  width: 40px; height: 22px; border-radius: 11px;
  background: var(--border-strong); position: relative; cursor: pointer;
  flex-shrink: 0;
  transition: background-color var(--t-fast);
}
.toggle-switch::after {
  content: ''; position: absolute; top: 2px; left: 2px;
  width: 18px; height: 18px; border-radius: 50%;
  background: var(--text-dim);
  transition: left var(--t-fast), background-color var(--t-fast);
}
.toggle-switch:hover { background: var(--text-dim); }
.toggle-switch:hover::after { background: var(--text); }
.toggle-switch.on, .toggle-switch.on:hover { background: var(--ok); }
.toggle-switch.on::after { left: 20px; background: #fff; }
/* Mid-stage: switched on, but missing credentials — not actually connected. */
.toggle-switch.pending, .toggle-switch.pending:hover { background: var(--accent); }
.toggle-switch.pending::after { left: 20px; background: #000; }

/* ── Eval table ─────────────────────────────────────── */
.eval-table {
  width: 100%; border-collapse: collapse; font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.eval-table th {
  text-align: left; padding: var(--sp-2) var(--sp-3);
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  letter-spacing: 1px; text-transform: uppercase; color: var(--text-dim);
  border-bottom: 1px solid var(--border);
  position: sticky; top: 0; background: var(--surface-2);
}
.eval-table td {
  padding: var(--sp-2) var(--sp-3); border-bottom: 1px solid var(--border);
  font-family: var(--mono); color: var(--text);
}
/* Numeric columns right-align for scannability. */
.eval-table th:nth-child(2), .eval-table td:nth-child(2),
.eval-table th:nth-child(4), .eval-table td:nth-child(4) { text-align: right; }
.eval-table tr:hover td { background: var(--surface-2); }
.success-bar {
  display: inline-block; width: 60px; height: 4px;
  background: var(--border); border-radius: 2px; overflow: hidden;
  vertical-align: middle; margin-right: var(--sp-2);
}
.success-bar-fill { height: 100%; border-radius: 2px; display: block; }
.eval-summary {
  display: flex; gap: var(--sp-6); padding: var(--sp-3) var(--sp-4); flex-wrap: wrap;
  border-bottom: 1px solid var(--border);
}
.eval-stat { font-family: var(--mono); font-size: 12px; color: var(--text-dim); }
.eval-stat .big-num { font-size: 20px; }

/* ── Code preview (Deploy) ──────────────────────────── */
.code-tabs { display: flex; gap: var(--sp-1); padding: var(--sp-3) var(--sp-3) 0; flex-wrap: wrap; }
.code-tab {
  font-family: var(--mono); font-size: 11px; font-weight: 600;
  padding: 6px var(--sp-3); border-radius: var(--radius); cursor: pointer;
  border: 1px solid var(--border); background: transparent;
  color: var(--text-dim);
  transition: color var(--t-fast), border-color var(--t-fast), background-color var(--t-fast);
}
.code-tab:hover {
  color: var(--text); border-color: var(--border-strong); background: var(--surface-2);
}
.code-tab:active { background: var(--surface-3); }
.code-tab.active { background: var(--accent); color: #000; border-color: var(--accent); }
.code-preview { padding: 0 var(--sp-3) var(--sp-3); }
.code-desc {
  font-size: 12px; color: var(--text-dim);
  padding: var(--sp-2) 0 0;
}
.code-wrap { position: relative; margin-top: var(--sp-3); }
.code-block {
  margin: 0; padding: var(--sp-4);
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius);
  font-family: var(--mono); font-size: 12px; color: var(--text);
  white-space: pre; overflow-x: auto; max-height: 55vh;
  scrollbar-width: thin; scrollbar-color: var(--border-strong) transparent;
}
.code-block::-webkit-scrollbar { height: 6px; width: 6px; }
.code-block::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 3px; }
.code-copy {
  position: absolute; top: var(--sp-2); right: var(--sp-2); z-index: 2;
  font-family: var(--mono); font-size: 10px; text-transform: uppercase;
  padding: 4px 10px; border-radius: var(--radius-sm); cursor: pointer;
  border: 1px solid var(--border); background: var(--surface-2);
  color: var(--text-dim);
  transition: color var(--t-fast), border-color var(--t-fast);
}
.code-copy:hover { color: var(--text); border-color: var(--border-strong); }
.code-copy:active { background: var(--surface-3); }

/* ── Settings form ──────────────────────────────────── */
.settings-form { padding: var(--sp-4); max-width: 560px; }
.form-field { margin-bottom: var(--sp-5); }
.form-label {
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  letter-spacing: 1px; text-transform: uppercase; color: var(--text-dim);
  display: block; margin-bottom: var(--sp-2);
}
.form-help {
  color: var(--text-dim); font-size: 12px; line-height: 1.45;
  margin-top: var(--sp-2);
}
.form-input, .form-select {
  width: 100%; min-height: 40px; padding: var(--sp-2) var(--sp-3);
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius);
  font-family: var(--mono); font-size: 13px; color: var(--text);
  outline: none;
  transition: border-color var(--t-fast);
}
.form-input:hover, .form-select:hover { border-color: var(--border-strong); }
.form-input:focus, .form-select:focus { border-color: var(--accent); }
.form-input:disabled, .form-select:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-save {
  font-family: var(--mono); font-size: 12px; font-weight: 600;
  min-height: 40px; padding: var(--sp-2) var(--sp-5);
  border-radius: var(--radius); cursor: pointer;
  border: 1px solid var(--accent); background: var(--accent); color: #000;
  text-transform: uppercase; letter-spacing: 0.5px;
  transition: background-color var(--t-fast), border-color var(--t-fast), opacity var(--t-fast);
}
.btn-save:hover { background: var(--accent-hover); border-color: var(--accent-hover); }
.btn-save:active { background: var(--accent); }
.btn-save:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── Modal (credentials) ────────────────────────────── */
.modal-overlay {
  position: fixed; inset: 0; z-index: 130;
  display: none; align-items: center; justify-content: center;
  background: rgba(5, 6, 8, 0.7);
  padding: var(--sp-5);
}
.modal-overlay.show { display: flex; animation: toast-in 120ms ease-out; }
.modal-card {
  width: min(460px, 96vw);
  background: var(--surface-2);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow);
  padding: var(--sp-6);
}
.modal-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: var(--sp-2);
}
.modal-title {
  font-family: var(--mono); font-size: 15px; font-weight: 700;
  letter-spacing: 0.5px; color: var(--text-bright);
}
.modal-sub {
  color: var(--text-dim); font-size: 13px; line-height: 1.5;
  margin-bottom: var(--sp-4);
}
.modal-actions { display: flex; gap: var(--sp-2); align-items: center; margin-top: var(--sp-2); }
.modal-actions .btn-action { flex: 1; text-transform: none; letter-spacing: 0; }
.modal-actions .btn-action#cred-provider {
  flex: 0 0 auto; text-decoration: none; display: inline-flex;
  align-items: center; justify-content: center;
}

/* ── Auth gate ──────────────────────────────────────── */
#auth-gate {
  position: fixed; inset: 0; z-index: 120;
  display: none; align-items: center; justify-content: center;
  background: rgba(5, 6, 8, 0.85);
}
#auth-gate.show { display: flex; }
.auth-card {
  width: min(460px, 92vw);
  background: var(--surface-2);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-lg);
  padding: var(--sp-8);
  box-shadow: var(--shadow);
}
.auth-card h2 { font-size: 18px; color: var(--text-bright); margin-bottom: var(--sp-2); }
.auth-card p { color: var(--text-dim); margin-bottom: var(--sp-5); font-size: 13px; }
.auth-card input {
  width: 100%; padding: var(--sp-2) var(--sp-3); margin-bottom: var(--sp-3);
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); color: var(--text);
  font-family: var(--mono); font-size: 13px;
  transition: border-color var(--t-fast);
}
.auth-card input:hover { border-color: var(--border-strong); }
.auth-card input:focus { border-color: var(--accent); outline: none; }
.auth-actions { display: grid; grid-template-columns: 1fr 1fr; gap: var(--sp-2); }

/* ── Responsive ─────────────────────────────────────── */
@media (max-width: 980px) {
  .topbar { align-items: flex-start; flex-direction: column; padding: var(--sp-3) var(--sp-4); }
  .topbar-left, .topbar-right { width: 100%; flex-wrap: wrap; }
  .topbar-right { justify-content: flex-start; }
  .profile-pills { max-width: 100%; overflow-x: auto; padding-bottom: 2px; }
}
@media (max-width: 768px) {
  html, body { overflow: auto; }
  #app { height: auto; min-height: 100dvh; }
  .nav-tabs { padding: 0 var(--sp-2); }
  .tab { flex: 1 0 auto; justify-content: center; padding: 0 var(--sp-3); }
  .tab-num { display: none; }
  .bento { grid-template-columns: 1fr; grid-template-rows: 1fr 200px auto; }
  .constellation-tile { grid-column: 1; }
  .telemetry-tile { grid-column: 1; grid-row: 2; }
  .stats-row { grid-column: 1; grid-row: 3; grid-template-columns: 1fr; }
  .detail-panel { top: 0; bottom: 0; width: 100%; }
  .command-bar { min-height: 48px; }
  .auth-actions { grid-template-columns: 1fr; }
}
"""


_HTML_SHELL_TOP = r"""
<div id="boot"><div class="boot-text" id="boot-text"></div></div>

<a href="#app" class="sr-only skip-link">Skip to content</a>

<div id="auth-gate">
  <div class="auth-card">
    <h2>Sign in to Kater</h2>
    <p>This gateway requires authentication. Use OAuth or paste an API key.</p>
    <label for="auth-key-input" class="sr-only">API key</label>
    <input type="password" id="auth-key-input" placeholder="API key (optional)" autocomplete="off">
    <div class="auth-actions">
      <button class="btn-save" id="auth-oauth-btn" type="button">Sign in with OAuth</button>
      <button class="btn-save" id="auth-key-btn" type="button">Use API key</button>
    </div>
  </div>
</div>

<div id="app">
  <div class="topbar">
    <div class="topbar-left">
      <div class="brand">
        <div class="brand-dot"></div>
        KATER
        <span class="version-tag" id="version-tag">v0.0.0</span>
      </div>
      <div class="profile-pills" id="profile-pills" role="group" aria-label="Profiles"></div>
    </div>
    <div class="topbar-right">
      <div class="status-chip">
        <div class="status-dot off" id="ws-dot"></div>
        <span id="ws-status">ws offline</span>
      </div>
      <div class="auth-badge">
        <div class="auth-dot" id="auth-dot"></div>
        <span id="auth-mode">none</span>
      </div>
    </div>
  </div>

  <div class="nav-tabs" role="tablist" aria-label="Dashboard views">
    <button class="tab active" type="button" data-view="dashboard" id="tab-dashboard" role="tab"
      aria-selected="true" aria-controls="view-dashboard" tabindex="0"
      onclick="switchView('dashboard')">Dashboard
      <span class="tab-num" aria-hidden="true">1</span></button>
    <button class="tab" type="button" data-view="catalog" id="tab-catalog" role="tab"
      aria-selected="false" aria-controls="view-catalog" tabindex="-1"
      onclick="switchView('catalog')">Catalog
      <span class="tab-num" aria-hidden="true">2</span></button>
    <button class="tab" type="button" data-view="evals" id="tab-evals" role="tab"
      aria-selected="false" aria-controls="view-evals" tabindex="-1"
      onclick="switchView('evals')">Evals
      <span class="tab-num" aria-hidden="true">3</span></button>
    <button class="tab" type="button" data-view="deploy" id="tab-deploy" role="tab"
      aria-selected="false" aria-controls="view-deploy" tabindex="-1"
      onclick="switchView('deploy')">Deploy
      <span class="tab-num" aria-hidden="true">4</span></button>
    <button class="tab" type="button" data-view="settings" id="tab-settings" role="tab"
      aria-selected="false" aria-controls="view-settings" tabindex="-1"
      onclick="switchView('settings')">Settings
      <span class="tab-num" aria-hidden="true">5</span></button>
  </div>
"""

_VIEW_DASHBOARD = r"""
  <div class="view active" id="view-dashboard" role="tabpanel"
    aria-labelledby="tab-dashboard" tabindex="0">
  <div class="bento">
    <div class="tile constellation-tile">
      <div class="tile-header">
        <span class="tile-title">Constellation</span>
        <span class="tile-title" id="node-count">0 nodes</span>
      </div>
      <canvas id="constellation-canvas"></canvas>
    </div>

    <div class="tile telemetry-tile">
      <div class="tile-header">
        <span class="tile-title">Live Stream</span>
      </div>
      <div class="telemetry-stream" id="telemetry-stream"></div>
    </div>

    <div class="stats-row">
      <div class="mini-tile">
        <div class="mini-label">Overview</div>
        <div class="mini-content">
          <div><span class="big-num" id="stat-tools">0</span>
            <span class="big-sub">tools</span></div>
          <div><span class="big-num" id="stat-enabled">0</span>
            <span class="big-sub">enabled</span></div>
          <div><span class="big-num" id="stat-success">0%</span>
            <span class="big-sub">success</span></div>
        </div>
      </div>
      <div class="mini-tile">
        <div class="mini-label">Tunnels</div>
        <div class="tunnel-item">
          <span class="tunnel-name">cloudflare</span>
          <button class="btn-tunnel" id="btn-cf" onclick="toggleTunnel('cloudflare')">START</button>
        </div>
        <div class="tunnel-item">
          <span class="tunnel-name">tailscale</span>
          <button class="btn-tunnel" id="btn-ts" onclick="toggleTunnel('tailscale')">START</button>
        </div>
      </div>
      <div class="mini-tile">
        <div class="mini-label">System</div>
        <div class="mini-content">
          <div><span class="big-num" id="stat-backends">0</span>
            <span class="big-sub">backends</span></div>
          <div><span class="big-num" id="stat-events">0</span>
            <span class="big-sub">events</span></div>
        </div>
      </div>
    </div>
  </div>
  </div>
"""

_VIEW_CATALOG = r"""
  <div class="view" id="view-catalog" role="tabpanel"
    aria-labelledby="tab-catalog" tabindex="0" hidden>
    <div class="view-header">
      <span class="view-title">Server Catalog</span>
      <span class="tile-title" id="catalog-count" aria-live="polite">0 servers</span>
    </div>
    <div class="view-scroll">
      <div class="catalog-toolbar">
        <input class="form-input" id="catalog-search" type="search"
          placeholder="Search servers (e.g. search, github)..." autocomplete="off"
          aria-label="Search servers" aria-describedby="catalog-count">
      </div>
      <div class="server-grid" id="catalog-grid">
        <div class="view-empty">Loading catalog...</div>
      </div>
    </div>
  </div>
"""

_VIEW_EVALS = r"""
  <div class="view" id="view-evals" role="tabpanel"
    aria-labelledby="tab-evals" tabindex="0" hidden>
    <div class="view-header">
      <span class="view-title">Tool Performance</span>
    </div>
    <div class="eval-summary" id="eval-summary"></div>
    <div class="view-scroll">
      <table class="eval-table">
        <thead><tr>
          <th>Tool</th><th>Calls</th><th>Success</th><th>Avg Latency</th>
        </tr></thead>
        <tbody id="eval-tbody"></tbody>
      </table>
    </div>
  </div>
"""

_VIEW_DEPLOY = r"""
  <div class="view" id="view-deploy" role="tabpanel"
    aria-labelledby="tab-deploy" tabindex="0" hidden>
    <div class="view-header">
      <span class="view-title">Deployment Configs</span>
    </div>
    <div class="view-scroll">
      <div class="code-tabs" id="deploy-tabs"></div>
      <div class="code-preview">
        <div class="code-desc" id="deploy-desc"></div>
        <div class="code-wrap">
          <button class="code-copy" onclick="copyDeployCode(this)"
            aria-label="Copy deployment code">Copy</button>
          <pre class="code-block" id="deploy-code">Select a format above.</pre>
        </div>
      </div>
    </div>
  </div>
"""

_VIEW_SETTINGS = r"""
  <div class="view" id="view-settings" role="tabpanel"
    aria-labelledby="tab-settings" tabindex="0" hidden>
    <div class="view-header">
      <span class="view-title">Settings</span>
    </div>
    <div class="view-scroll">
      <div class="settings-form">
        <div class="form-field">
          <label class="form-label" for="set-auth-mode">Auth Mode</label>
          <select class="form-select" id="set-auth-mode">
            <option value="none">none</option>
            <option value="apikey">apikey</option>
            <option value="oauth">oauth</option>
          </select>
        </div>
        <div class="form-field">
          <label class="form-label" for="set-profile">Default Profile</label>
          <input class="form-input" id="set-profile" type="text" />
        </div>
        <div class="form-field">
          <label class="form-label" for="set-cors">CORS Origins</label>
          <input class="form-input" id="set-cors" type="text" />
          <div class="form-help">Comma-separated origins allowed to call the dashboard API.</div>
        </div>
        <div class="form-field">
          <label class="form-label" for="set-rate-limit">Rate Limit / min</label>
          <input class="form-input" id="set-rate-limit" type="number"
            min="0" />
          <div class="form-help">Public deployments should keep this above zero.</div>
        </div>
        <div class="form-field">
          <label class="form-label" for="set-storage">Storage Backend</label>
          <select class="form-select" id="set-storage">
            <option value="sqlite">sqlite</option>
            <option value="jsonl">jsonl</option>
          </select>
        </div>
        <button class="btn-save" onclick="saveSettings()">Save Settings</button>
      </div>
    </div>
  </div>
"""

_HTML_SHELL_BOTTOM = r"""
  <div class="command-bar">
    <span class="cmd-prompt">&gt;</span>
    <label for="cmd-input" class="sr-only">Command</label>
    <input id="cmd-input"
      placeholder="Command"
      autocomplete="off" />
  </div>
</div>

<div class="detail-panel" id="detail-panel">
  <div class="detail-header">
    <span class="detail-name" id="detail-name">-</span>
    <div class="detail-close" onclick="closeDetail()" role="button"
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
    <div class="detail-label">Launch Command</div>
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
    <button class="btn-action primary" id="btn-connect" type="button"
      onclick="connectSelected()" style="width:100%">Connect…</button>
  </div>
  <div class="detail-actions">
    <button class="btn-action primary" id="btn-enable" onclick="detailToggle(true)">Enable</button>
    <button class="btn-action danger" id="btn-disable"
      onclick="detailToggle(false)">Disable</button>
  </div>
</div>

<div class="modal-overlay" id="cred-modal" role="dialog" aria-modal="true"
  aria-labelledby="cred-title">
  <div class="modal-card">
    <div class="modal-head">
      <span class="modal-title" id="cred-title">Connect</span>
      <div class="detail-close" onclick="closeCredentialsModal()" role="button"
        tabindex="0" aria-label="Close"
        onkeydown="btnKey(event,closeCredentialsModal)">&times;</div>
    </div>
    <p class="modal-sub" id="cred-sub">Paste a token to connect this server.</p>
    <div id="cred-fields"></div>
    <div class="modal-actions">
      <a class="btn-action" id="cred-provider" href="#" target="_blank"
        rel="noopener" style="display:none">Get a token &#8599;</a>
      <button class="btn-action primary" id="cred-save" type="button"
        onclick="saveCredentials()">Save &amp; connect</button>
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
    + _HTML_SHELL_BOTTOM
)


_JS = r"""
const API = '';
const MONO_FONT = "ui-monospace,'SF Mono','Cascadia Code','JetBrains Mono','Consolas',monospace";
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
let canvas, ctx;
let nodes = [];
let hoveredNode = null;
let selectedNode = null;

// Semantic transport colors — jade (stdio), ice (sse/http), amber (native).
const transportColors = {
  stdio: '#3ecf8e', sse: '#6fb7e0', http: '#6fb7e0',
  native: '#ffb224', local: '#ffb224'
};

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

async function wsUrlWithAuth() {
  const token = sessionStorage.getItem(AUTH_STORAGE);
  if (!token) return WS_URL;
  try {
    const data = await apiPost('/api/ws-ticket', {});
    if (data.ticket) {
      const sepTicket = WS_URL.includes('?') ? '&' : '?';
      return WS_URL + sepTicket + 'ticket=' + encodeURIComponent(data.ticket);
    }
  } catch (e) {
    // Local/dev mode can still use the bare WS URL; auth failures surface below.
  }
  return WS_URL;
}

function setWsStatus(status) {
  const dot = document.getElementById('ws-dot');
  const label = document.getElementById('ws-status');
  if (!dot || !label) return;
  dot.classList.remove('off', 'warn', 'on');
  if (status === 'online') {
    dot.classList.add('on');
    label.textContent = 'ws online';
  } else if (status === 'connecting') {
    dot.classList.add('warn');
    label.textContent = 'ws connecting';
  } else {
    dot.classList.add('off');
    label.textContent = 'ws offline';
  }
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
  const clientId = 'kater-dashboard';
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
  const q = new URLSearchParams({
    response_type: 'code',
    client_id: 'kater-dashboard',
    redirect_uri: redirect,
    code_challenge: challenge,
    code_challenge_method: 'S256',
    scope: 'tools',
  });
  location.href = '/authorize?' + q.toString();
}

async function handleAuthBootstrap() {
  const params = new URLSearchParams(location.search);
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

// ── Boot ───────────────────────────────
// One readiness probe, no typewriter theater: the dashboard appears as
// soon as the gateway answers (401 still routes to the auth gate).
async function bootSequence() {
  const el = document.getElementById('boot-text');
  el.textContent = 'Connecting to gateway\u2026';
  try { await api('/api/status'); } catch (e) {
    if (e instanceof ApiError && e.status === 401) throw e;
  }
  const boot = document.getElementById('boot');
  boot.classList.add('done');
  setTimeout(() => { boot.style.display = 'none'; }, 200);
}

// ── Init ───────────────────────────────
async function init() {
  if (appReady) return;
  try { await handleAuthBootstrap(); } catch (e) {
    console.error('auth bootstrap:', e);
    toast((e instanceof ApiError ? e.message : 'Login failed'), 'error');
  }
  try { await bootSequence(); } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      showAuthGate();
      return;
    }
    console.error('boot failed:', e);
  }
  // Canvas MUST exist before loadCatalog() calls buildNodes(), otherwise node
  // positions are computed against a fallback 600x400 box and never realign.
  initCanvas();
  try { await loadProfiles(); } catch (e) { console.error('profiles:', e); }
  try { await loadCatalog(); } catch (e) { console.error('catalog:', e); }
  try { await loadStatus(); } catch (e) { console.error('status:', e); }
  try { await loadTunnelStatus(); } catch (e) { console.error('tunnel:', e); }
  initDelegation();
  initCommandBar();
  initCatalogSearch();
  initKeyboard();
  initWebSocket();
  startAnimationLoop();
  setInterval(loadStatusSafe, 5000);
  appReady = true;
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
    const isActive = p === activeProfile;
    pill.className = 'pill' + (isActive ? ' active' : '');
    pill.textContent = p;
    pill.dataset.profile = p;
    pill.setAttribute('tabindex', '0');
    pill.setAttribute('role', 'button');
    pill.setAttribute('aria-pressed', String(isActive));
    el.appendChild(pill);
  }
}

function switchProfile(p) {
  if (profiles.indexOf(p) === -1) { toast('unknown profile: ' + p, 'error'); return; }
  activeProfile = p;
  document.querySelectorAll('.pill').forEach(el => {
    const isActive = el.dataset.profile === p;
    el.classList.toggle('active', isActive);
    el.setAttribute('aria-pressed', String(isActive));
  });
  loadCatalog();
  if (currentView === 'catalog') loadCatalogView();
  toast('profile: ' + p);
}

async function loadCatalog() {
  const data = await api(catalogApiPath());
  servers = filterServers(data.servers || []);
  buildNodes();
  document.getElementById('node-count').textContent = servers.length + ' nodes';
}

async function loadStatus() {
  const data = await api('/api/status');
  document.getElementById('version-tag').textContent = 'v' + (data.version || '');
  document.getElementById('auth-mode').textContent = data.auth_mode || 'none';
  document.getElementById('stat-tools').textContent = (data.servers && data.servers.total) || 0;
  document.getElementById('stat-enabled').textContent = (data.servers && data.servers.enabled) || 0;
  document.getElementById('stat-success').textContent =
    ((data.telemetry && data.telemetry.success_rate) || 0) + '%';
  document.getElementById('stat-backends').textContent =
    (data.telemetry && data.telemetry.tool_calls) || 0;
  document.getElementById('stat-events').textContent =
    (data.telemetry && data.telemetry.total_events) || 0;
  document.getElementById('auth-dot').style.background =
    data.auth_mode === 'none' ? '#3ecf8e' : '#ffb224';
}

// ── Constellation Canvas ───────────────
function initCanvas() {
  canvas = document.getElementById('constellation-canvas');
  ctx = canvas.getContext('2d');
  resizeCanvas();
  window.addEventListener('resize', resizeCanvas);
  canvas.addEventListener('mousemove', onCanvasMove);
  canvas.addEventListener('click', onCanvasClick);
}

function resizeCanvas() {
  if (!canvas || !ctx) return;
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);
  // Re-layout nodes against the new geometry so a resize keeps the
  // constellation centered instead of leaving nodes in stale coordinates.
  if (servers.length) buildNodes();
  else drawConstellation();
}

function buildNodes() {
  const rect = canvas ? canvas.getBoundingClientRect() : { width: 600, height: 400 };
  const cx = rect.width / 2;
  const cy = rect.height / 2;
  const maxR = Math.min(cx, cy) * 0.75;

  nodes = servers.map(s => {
    const pos = hashPos(s.name);
    return Object.assign({}, s, {
      x: cx + Math.cos(pos.angle) * maxR * pos.radius,
      y: cy + Math.sin(pos.angle) * maxR * pos.radius,
      r: 16,
    });
  });
  drawConstellation();
}

function hashPos(name) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = ((h << 5) - h + name.charCodeAt(i)) | 0;
  const angle = ((h % 360) + 360) % 360 * Math.PI / 180;
  const radius = 0.32 + Math.abs(h % 100) / 350;
  return { angle, radius };
}

function onCanvasMove(e) {
  const rect = canvas.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;
  const prev = hoveredNode;
  hoveredNode = null;
  for (const n of nodes) {
    const dx = x - n.x, dy = y - n.y;
    if (dx * dx + dy * dy < (n.r + 8) * (n.r + 8)) {
      hoveredNode = n;
      break;
    }
  }
  canvas.style.cursor = hoveredNode ? 'pointer' : 'default';
  if (hoveredNode !== prev) drawConstellation();
}

async function onCanvasClick(e) {
  if (!hoveredNode) {
    if (selectedNode) closeDetail();
    return;
  }
  let node = hoveredNode;
  // Catalog nodes carry no `mcp` field; fetch the full server doc so the
  // detail panel can show a real Launch Command instead of '-'.
  if (!node.mcp) {
    try { node = await api('/api/mcp/servers/' + encodeURIComponent(node.name)); }
    catch (err) { /* fall back to catalog data */ }
  }
  openDetail(node);
}

// Calm, static topology render. Redrawn on demand (data change, resize,
// hover) instead of a continuous rAF loop: no particles, no pulsing —
// state is communicated by color and line style only.
function drawConstellation() {
  if (!ctx || !canvas) return;
  const rect = canvas.getBoundingClientRect();
  const w = rect.width, h = rect.height;
  const cx = w / 2, cy = h / 2;

  ctx.clearRect(0, 0, w, h);

  for (const n of nodes) {
    const color = transportColors[n.transport] || '#5d626c';
    const isActive = n.enabled && n.env_configured;
    const isHovered = n === hoveredNode;

    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(n.x, n.y);
    if (isActive) {
      ctx.strokeStyle = color + '55';
      ctx.lineWidth = isHovered ? 2 : 1.5;
    } else {
      ctx.strokeStyle = 'rgba(255,255,255,0.08)';
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 4]);
    }
    ctx.stroke();
    ctx.setLineDash([]);
  }

  for (const n of nodes) {
    const color = transportColors[n.transport] || '#5d626c';
    const isActive = n.enabled && n.env_configured;
    const isHovered = n === hoveredNode;
    const r = isHovered ? n.r + 2 : n.r;

    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    if (isActive) {
      ctx.fillStyle = color + '1e';
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = isHovered ? 2 : 1.5;
    } else {
      ctx.fillStyle = '#17181c';
      ctx.fill();
      ctx.strokeStyle = isHovered ? 'rgba(255,255,255,0.3)' : 'rgba(255,255,255,0.12)';
      ctx.lineWidth = 1.5;
    }
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(n.x, n.y, 3.5, 0, Math.PI * 2);
    ctx.fillStyle = isActive ? color : '#5d626c';
    ctx.fill();

    ctx.font = '11px ' + MONO_FONT;
    ctx.textAlign = 'center';
    ctx.fillStyle = isHovered ? '#f7f8fa' : isActive ? '#e8e9ec' : '#5d626c';
    ctx.fillText(n.name, n.x, n.y + r + 14);
  }

  // Gateway hub: a single steady mark, no glow or pulse.
  ctx.beginPath();
  ctx.arc(cx, cy, 15, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(255,178,36,0.14)';
  ctx.fill();
  ctx.strokeStyle = '#ffb224';
  ctx.lineWidth = 1.5;
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(cx, cy, 5, 0, Math.PI * 2);
  ctx.fillStyle = '#ffb224';
  ctx.fill();

  ctx.font = 'bold 11px ' + MONO_FONT;
  ctx.textAlign = 'center';
  ctx.fillStyle = '#ffb224';
  ctx.fillText('KATER', cx, cy + 34);
}

function startAnimationLoop() {
  // Kept as the init seam; rendering is now event-driven, so this is
  // just the first paint.
  drawConstellation();
}

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
      val.style.color = configured ? '#3ecf8e' : '#f2695c';
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

  document.getElementById('detail-panel').classList.add('open');
}

function closeDetail() {
  document.getElementById('detail-panel').classList.remove('open');
  selectedNode = null;
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
      const inputId = 'cred-' + v.replace(/[^a-z0-9_-]/gi, '-');
      const label = document.createElement('label');
      label.className = 'form-label';
      label.setAttribute('for', inputId);
      label.textContent = v;
      const input = document.createElement('input');
      input.id = inputId;
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

async function saveCredentials() {
  if (!credServer) return;
  const inputs = document.querySelectorAll('#cred-fields input[data-env]');
  const env = {};
  let any = false;
  inputs.forEach((i) => {
    const val = i.value.trim();
    if (val) { env[i.dataset.env] = val; any = true; }
  });
  if (!any) { toast('Enter at least one value to save.', 'error'); return; }
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
  }
}

async function detailToggle(enable) {
  if (!selectedNode) return;
  const name = selectedNode.name;
  const action = enable ? 'enable' : 'disable';
  try {
    await apiPost('/api/mcp/servers/' + encodeURIComponent(name) + '/' + action, {});
    toast(enableHint(name, enable), enable ? 'success' : '');
  } catch (e) {
    toast(name + ': ' + (e.message || 'failed'), 'error');
  }
  // Reload, then re-resolve selectedNode from the FRESH server list so we
  // don't keep rendering a stale, optimistically-mutated object.
  try { await loadCatalog(); } catch (e) { /* handled */ }
  const fresh = servers.find(s => s.name === name);
  if (fresh) openDetail(fresh);
  // Enabling something that still needs a token? Bring up the connect popup.
  if (enable && fresh && fresh.env_configured === false) promptCredentials(name);
}

function clearSearch() {
  const input = document.getElementById('catalog-search');
  if (input) {
    input.value = '';
    catalogQuery = '';
    loadCatalog();
    if (currentView === 'catalog') loadCatalogView();
  }
}

function initCatalogSearch() {
  const input = document.getElementById('catalog-search');
  if (!input || input.dataset.bound) return;
  input.dataset.bound = '1';
  input.addEventListener('input', () => {
    if (catalogSearchTimer) clearTimeout(catalogSearchTimer);
    catalogSearchTimer = setTimeout(async () => {
      catalogSearchTimer = null;
      catalogQuery = input.value.trim();
      try {
        await loadCatalog();
        if (currentView === 'catalog') await loadCatalogView();
      } catch (e) { /* ignore search errors while typing */ }
    }, 200);
  });
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

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (document.getElementById('cred-modal').classList.contains('show')) {
      closeCredentialsModal();
    } else {
      closeDetail();
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

// ── WebSocket ──────────────────────────
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

async function initWebSocket() {
  closeWebSocket();
  setWsStatus('connecting');
  let url = WS_URL;
  try { url = await wsUrlWithAuth(); } catch (e) { url = WS_URL; }
  try {
    ws = new WebSocket(url);
  } catch (e) {
    setWsStatus('offline');
    scheduleReconnect();
    return;
  }
  ws.onopen = () => {
    wsRetry = 0;
    setWsStatus('online');
    // subscribe_all so we receive every broadcast without a `type` filter
    // (the previous {cmd:'subscribe'} was missing the required type field).
    try { ws.send(JSON.stringify({ cmd: 'subscribe_all' })); } catch (e) {}
  };
  ws.onmessage = (e) => {
    try { handleWSMessage(JSON.parse(e.data)); } catch (err) {}
  };
  ws.onclose = (e) => {
    ws = null;
    setWsStatus('offline');
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

  const stream = document.getElementById('telemetry-stream');
  const row = document.createElement('div');
  row.className = 'tlm-row';
  const now = new Date();
  const ts = pad2(now.getHours()) + ':' + pad2(now.getMinutes()) + ':' + pad2(now.getSeconds());
  const ok = event.success !== false;

  const t = document.createElement('span'); t.className = 'tlm-time'; t.textContent = ts;
  const ic = document.createElement('span');
  ic.className = 'tlm-icon ' + (ok ? 'ok' : 'err');
  ic.textContent = ok ? '\u2713' : '\u2717';
  const nm = document.createElement('span');
  nm.className = 'tlm-name';
  nm.textContent = event.name || event.type || '';
  const ms = document.createElement('span');
  ms.className = 'tlm-ms';
  ms.textContent = Math.round(event.duration_ms || 0) + 'ms';

  row.appendChild(t); row.appendChild(ic); row.appendChild(nm); row.appendChild(ms);
  stream.insertBefore(row, stream.firstChild);

  while (stream.children.length > 50) stream.lastChild.remove();

  setTimeout(() => row.classList.add('faded'), 4000);
}

// ── Tunnels ────────────────────────────
function tunnelBtn(provider) {
  return document.getElementById(provider === 'cloudflare' ? 'btn-cf' : 'btn-ts');
}

function setTunnelButton(provider, running) {
  const btn = tunnelBtn(provider);
  if (!btn) return;
  btn.classList.toggle('active', !!running);
  btn.textContent = running ? 'ON' : 'START';
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
  btn.textContent = '...';
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

function switchView(name, options = {}) {
  currentView = name;
  document.querySelectorAll('.view').forEach(v => {
    const isActive = v.id === 'view-' + name;
    v.classList.toggle('active', isActive);
    v.hidden = !isActive;
  });
  document.querySelectorAll('.nav-tabs .tab').forEach(t => {
    const isActive = t.dataset.view === name;
    t.classList.toggle('active', isActive);
    t.setAttribute('aria-selected', String(isActive));
    t.setAttribute('tabindex', isActive ? '0' : '-1');
    if (isActive && options.focusTab) t.focus();
  });
  loadViewData(name);
}

function initTabNavigation() {
  const tablist = document.querySelector('.nav-tabs[role="tablist"]');
  if (!tablist) return;

  tablist.addEventListener('keydown', (e) => {
    const tabs = Array.from(tablist.querySelectorAll('[role="tab"]'));
    const currentIndex = tabs.indexOf(document.activeElement);
    if (currentIndex === -1) return;

    let nextIndex = currentIndex;
    if (e.key === 'ArrowRight') {
      nextIndex = (currentIndex + 1) % tabs.length;
    } else if (e.key === 'ArrowLeft') {
      nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    } else if (e.key === 'Home') {
      nextIndex = 0;
    } else if (e.key === 'End') {
      nextIndex = tabs.length - 1;
    } else {
      return;
    }

    e.preventDefault();
    switchView(tabs[nextIndex].dataset.view, { focusTab: true });
  });
}

async function loadViewData(name) {
  try {
    if (name === 'catalog') await loadCatalogView();
    else if (name === 'evals') await loadEvalsView();
    else if (name === 'deploy') await loadDeployView();
    else if (name === 'settings') await loadSettingsView();
  } catch (e) {
    console.error('view load error:', e);
  }
}

async function loadCatalogView() {
  const search = document.getElementById('catalog-search');
  if (search && search.value.trim() !== catalogQuery) {
    catalogQuery = search.value.trim();
  }
  const data = await api(catalogApiPath());
  const grid = document.getElementById('catalog-grid');
  const items = filterServers(data.servers || []);
  document.getElementById('catalog-count').textContent = items.length + ' servers';
  grid.innerHTML = '';
  if (!items.length) {
    const empty = document.createElement('div');
    empty.className = 'view-empty';
    empty.style.gridColumn = '1 / -1';
    if (catalogQuery) {
      empty.textContent = 'No servers match "' + catalogQuery + '".';
      const clearBtn = document.createElement('button');
      clearBtn.className = 'view-empty-link';
      clearBtn.textContent = 'Clear search';
      clearBtn.onclick = clearSearch;
      empty.appendChild(clearBtn);
    } else {
      empty.textContent = 'No servers in this profile. Switch profiles in the top bar.';
    }
    grid.appendChild(empty);
    return;
  }
  for (const s of items) {
    const card = document.createElement('div');
    card.className = 'server-card';
    card.dataset.name = s.name;

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
    toggle.setAttribute('tabindex', '0');
    toggle.title = pending ? 'On, but needs credentials to connect' : '';
    toggle.dataset.name = s.name;
    head.appendChild(nameEl);
    head.appendChild(toggle);
    card.appendChild(head);

    const badges = document.createElement('div');
    badges.className = 'badges';
    badges.style.marginBottom = '6px';
    badges.appendChild(makeBadge(s.transport, s.transport));
    badges.appendChild(makeBadge(s.risk, s.risk));
    badges.appendChild(makeBadge(
      s.env_configured ? 'low' : 'high',
      s.env_configured ? 'configured' : 'missing env'
    ));
    card.appendChild(badges);

    const desc = document.createElement('div');
    desc.className = 'server-card-desc';
    desc.textContent = s.description || '';
    card.appendChild(desc);

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
    const s = servers.find(x => x.name === name);
    const pending = data.enabled && s && s.env_configured === false;
    el.classList.remove('on', 'pending');
    if (data.enabled) el.classList.add(pending ? 'pending' : 'on');
    el.setAttribute('aria-checked', String(!!data.enabled));
    el.title = pending ? 'On, but needs credentials to connect' : '';
    toast(enableHint(name, !!data.enabled), data.enabled ? 'success' : '');
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
    big.className = 'big-num';
    big.textContent = val;
    stat.appendChild(big);
    stat.appendChild(document.createTextNode(' ' + label));
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
    const color = rate >= 90 ? '#3ecf8e' : rate >= 50 ? '#ffb224' : '#f2695c';
    const avg = Math.round(s.avg_duration_ms || 0);
    const tr = document.createElement('tr');
    tr.appendChild(td(name));
    tr.appendChild(td(String(s.total)));
    const c = td('');
    const bar = document.createElement('span');
    bar.className = 'success-bar';
    const fill = document.createElement('span');
    fill.className = 'success-bar-fill';
    fill.style.width = rate + '%';
    fill.style.background = color;
    bar.appendChild(fill);
    c.appendChild(bar);
    c.appendChild(document.createTextNode(rate + '%'));
    tr.appendChild(c);
    tr.appendChild(td(avg + 'ms'));
    tbody.appendChild(tr);
  }
}

let deployFormats = [];

async function loadDeployView() {
  const data = await api('/api/deploy');
  deployFormats = data.formats || [];
  const tabs = document.getElementById('deploy-tabs');
  tabs.innerHTML = '';
  for (const f of deployFormats) {
    const btn = document.createElement('button');
    btn.className = 'code-tab';
    btn.dataset.fmt = f.name;
    btn.textContent = f.name;
    tabs.appendChild(btn);
  }
  if (deployFormats[0]) await selectDeployFormat(deployFormats[0].name);
}

async function selectDeployFormat(fmt) {
  document.querySelectorAll('.code-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.fmt === fmt);
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
  btn.dataset.copying = '1';
  const text = document.getElementById('deploy-code').textContent || '';
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(
      () => {
        const old = btn.textContent;
        btn.textContent = 'Copied!';
        toast('copied to clipboard', 'success');
        setTimeout(() => {
          btn.textContent = old;
          delete btn.dataset.copying;
        }, 2000);
      },
      () => {
        delete btn.dataset.copying;
        toast('clipboard access denied', 'error');
      }
    );
  } else {
    delete btn.dataset.copying;
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

async function saveSettings() {
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
  }
}

function initKeyboard() {
  initTabNavigation();
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      document.getElementById('cmd-input').focus();
      return;
    }
    const tag = e.target.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (e.key >= '1' && e.key <= '5') {
      const views = ['dashboard', 'catalog', 'evals', 'deploy', 'settings'];
      const v = views[parseInt(e.key) - 1];
      if (v) switchView(v, { focusTab: true });
    }
  });
}

// ── Start ──────────────────────────────
window.addEventListener('DOMContentLoaded', init);
"""


def render_dashboard(ws_port: int = 9092) -> str:
    # Inject runtime config so the client talks to the configured WebSocket
    # port instead of a hardcoded one (single source of truth = ListenConfig).
    config = f"<script>window.KATER_CONFIG={{wsPort:{int(ws_port)}}};</script>\n"
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
