from __future__ import annotations

_CSS = r"""
:root {
  /* Industrial Brutalist / Swiss Industrial Print — white-first, ink-on-paper.
     Amber is a RESTRAINED signal accent: warnings, runs/pending, terminal only. */
  --paper: #F4F3EF;
  --paper-2: #EAE8E2;
  --ink: #111111;
  --ink-dim: #5B5F66;
  --line: #1A1A1A;
  --line-soft: rgba(0, 0, 0, 0.14);
  --accent: #8A4E00;
  --accent-bg: #FBF1DE;
  --ok: #2F5D32;
  --err: #9F2F2D;
  --mono: 'JetBrains Mono', 'SF Mono', ui-monospace, 'Cascadia Code', monospace;
  --sans: 'Inter', 'Archivo', ui-sans-serif, system-ui, sans-serif;
  --radius: 0;
  --motion-instant: 100ms;
  --motion-fast: 180ms;
  --motion-base: 260ms;
  --motion-slow: 420ms;
  --motion-ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --motion-ease-in: cubic-bezier(0.4, 0, 1, 1);
  --motion-ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  color-scheme: light;
  --s1: 4px; --s2: 8px; --s3: 12px; --s4: 16px; --s5: 24px; --s6: 32px;
  --z-boot: 100; --z-auth: 120; --z-modal: 130; --z-detail: 50; --z-toast: 200; --z-skip: 300;
}

* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { height: 100%; }
body {
  font-family: var(--sans);
  background: var(--paper);
  color: var(--ink);
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

::selection { background: var(--accent-bg); color: var(--accent); }

/* Quality floor: every interactive element shows a visible hard focus ring. */
a:focus-visible, button:focus-visible, input:focus-visible,
select:focus-visible, [role="switch"]:focus-visible, [tabindex]:focus-visible {
  outline: 2px solid var(--line);
  outline-offset: 2px;
  border-radius: var(--radius);
}

/* Visually hidden but accessible to screen readers. */
.sr-only {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
}
.skip-link:focus {
  position: fixed; left: 12px; top: 8px; z-index: var(--z-skip);
  width: auto; height: auto; margin: 0; padding: 8px 16px;
  clip: auto; overflow: visible; white-space: nowrap;
  background: var(--ink); color: var(--paper); border-radius: var(--radius);
  font-family: var(--mono); font-size: 13px; text-transform: uppercase;
  letter-spacing: 1px; text-decoration: none;
}

/* ── Reduced motion: the only motion rule in this file (Agent E owns the rest). ── */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
    animation-delay: 0ms !important;
  }
  /* Kill our explicit loops / entrance keyframes outright. */
  .toggle-switch.pending::after,
  .confirm-overlay, .confirm-card {
    animation: none !important;
  }
  .confirm-card { transform: none !important; opacity: 1 !important; }
  .confirm-overlay { opacity: 1 !important; }
  .kater-rowin, .view-in, .view-out { opacity: 1 !important; transform: none !important; }
}

/* Static paper surface — no gradient, no texture, no grid. */
#bg-gradient { position: fixed; inset: 0; z-index: 0; background: var(--paper); }

/* ── Boot ────────────────────────── */
#boot {
  position: fixed; inset: 0; z-index: var(--z-boot);
  background: var(--paper);
  display: flex; align-items: center; justify-content: center;
  font-family: var(--mono); font-size: 13px; color: var(--ink-dim);
}
#boot.done { opacity: 0; pointer-events: none;
  transition: opacity var(--motion-base) var(--motion-ease-in); }
#boot .boot-text { white-space: pre; line-height: 1.8; }
#boot .boot-text .ok { color: var(--ok); }
#boot .boot-text .accent { color: var(--accent); }

/* ── Layout ────────────────────────────── */
#app {
  position: relative; z-index: 1;
  height: 100vh;
  display: flex; flex-direction: column;
}

/* ── Topbar ────────────────────────────── */
.topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 20px; min-height: 56px;
  border-bottom: 2px solid var(--line);
  background: var(--paper);
  gap: 16px;
}
.topbar-left { display: flex; align-items: center; gap: 16px; }
.brand {
  font-family: var(--mono); font-weight: 700; font-size: 15px;
  letter-spacing: 2px; color: var(--ink);
  display: flex; align-items: center; gap: 10px;
}
.brand-dot {
  width: 9px; height: 9px; border-radius: var(--radius);
  background: var(--accent);
}
.version-tag {
  font-family: var(--mono); font-size: 11px; color: var(--ink-dim);
  padding: 2px 8px; border-radius: var(--radius);
  border: 1px solid var(--line);
}
.profile-pills { display: flex; gap: 0; flex-wrap: wrap; }
.pill {
  font-family: var(--mono); font-size: 11px; text-transform: uppercase;
  letter-spacing: 1px;
  padding: 4px 10px; border-radius: var(--radius);
  border: 1px solid var(--line); border-right-width: 0;
  color: var(--ink-dim); background: var(--paper);
  cursor: pointer; user-select: none;
  transition: background var(--motion-fast) var(--motion-ease-in-out);
}
.pill:last-child { border-right-width: 1px; }
.pill:hover { color: var(--ink); }
.pill.active {
  background: var(--ink); color: var(--paper); border-color: var(--ink);
}
.pill--on { background: var(--ink); color: var(--paper); border-color: var(--ink); }
.topbar-right { display: flex; align-items: center; justify-content: flex-end; gap: 8px; }
.status-chip, .auth-badge {
  font-family: var(--mono); font-size: 11px; color: var(--ink-dim);
  display: flex; align-items: center; gap: 7px;
  min-height: 32px; padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--paper);
}
.auth-dot, .status-dot {
  width: 6px; height: 6px; border-radius: var(--radius); background: var(--ok);
}
.status-dot.off { background: var(--ink-dim); }
.status-dot.warn { background: var(--accent); }
.status-dot.on { background: var(--ok); }

/* ── Primitive: .panel ─────────────────── */
.panel {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: none;
}

/* ── Primitive: .grid-hard (razor-thin rule grid) ── */
.grid-hard {
  display: grid;
  gap: 1px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}
.grid-hard > * { background: var(--paper); border-radius: var(--radius); }

/* ── Primitive: .tag (square status chip) ── */
.tag {
  display: inline-flex; align-items: center;
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  letter-spacing: 0.5px; text-transform: uppercase;
  padding: 2px 8px; border-radius: var(--radius);
  border: 1px solid var(--line);
  color: var(--ink); background: var(--paper);
}
.tag--ok { color: var(--ok); border-color: var(--ok); background: var(--paper); }
.tag--err { color: var(--err); border-color: var(--err); background: var(--paper); }
.tag--accent { color: var(--accent); border-color: var(--accent); background: var(--accent-bg); }
.tag--dim { color: var(--ink-dim); border-color: var(--line-soft); background: var(--paper-2); }
.tag--muted { background: var(--paper-2); border-color: var(--line-soft); color: var(--ink-dim); }

/* ── Primitive: .kv / definition grid ─── */
.kv { display: grid; grid-template-columns: max-content 1fr; gap: 0;
  border: 1px solid var(--line); border-radius: var(--radius); }
.kv dt {
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  letter-spacing: 1px; text-transform: uppercase; color: var(--ink-dim);
  padding: 6px 12px; border-right: 1px solid var(--line); border-bottom: 1px solid var(--line-soft);
}
.kv dd {
  font-family: var(--mono); font-size: 12px; color: var(--ink);
  padding: 6px 12px; border-bottom: 1px solid var(--line-soft); word-break: break-all;
}

/* ── Primitive: .btn (solid ink) ──────── */
.btn {
  font-family: var(--mono); font-size: 12px; font-weight: 600;
  letter-spacing: 0.5px; text-transform: uppercase;
  padding: 8px 16px; border-radius: var(--radius); cursor: pointer;
  border: 1px solid var(--ink); background: var(--ink); color: var(--paper);
  box-shadow: none; transition: background var(--motion-fast) var(--motion-ease-in-out);
  user-select: none;
}
.btn:hover { background: var(--paper); color: var(--ink); }
.btn:active { transform: translateY(1px); }
.btn--accent { background: var(--accent); border-color: var(--accent); color: var(--paper); }
.btn--accent:hover { background: var(--paper); color: var(--accent); }
.btn--ghost { background: var(--paper); color: var(--ink); }
.btn--ghost:hover { background: var(--ink); color: var(--paper); }
.btn-ok { background: var(--ok); border-color: var(--ok); color: var(--paper); }
.btn-warn { background: var(--accent); border-color: var(--accent); color: var(--paper); }

/* ── Primitive: .feed (live event stream) ── */
.feed {
  font-family: var(--mono); font-size: 11px; line-height: 1.6;
  padding: 8px 12px; overflow-y: auto;
  border-top: 2px solid var(--line);
  background: var(--paper); color: var(--ink);
}
.feed::-webkit-scrollbar { width: 8px; }
.feed::-webkit-scrollbar-thumb { background: var(--line-soft); border-radius: var(--radius); }

/* New telemetry row entrance — opacity + translateY only. */
.feed-row {
  opacity: 1;
  will-change: transform, opacity;
}
.feed-row.kater-rowin {
  opacity: 0; transform: translateY(6px);
  animation: kater-rowin var(--motion-fast) var(--motion-ease-out) forwards;
}
@keyframes kater-rowin {
  to { opacity: 1; transform: translateY(0); }
}
.feed-row { padding: 3px 0; border-bottom: 1px solid var(--line-soft); white-space: pre; }
.feed--err { color: var(--err); }
.feed--accent { color: var(--accent); }
.feed--ok { color: var(--ok); }
/* One restrained status emphasis on a colored row. Never particles. */
.feed-row.kater-pulse { animation: kater-statuspulse var(--motion-base) var(--motion-ease-in-out); }
@keyframes kater-statuspulse {
  0% { opacity: 1; }
  25% { opacity: 0.55; }
  100% { opacity: 1; }
}
/* JSON chevron — rotate via transform only, instant fallback. */
.json-chevron {
  display: inline-block; transition: transform var(--motion-instant) var(--motion-ease-in-out);
  transform: rotate(0deg);
}
.json-chevron.open { transform: rotate(90deg); }

/* ── Primitive: .confirm (danger surface) ── */
.confirm {
  background: var(--paper);
  border: 2px solid var(--err);
  border-radius: var(--radius);
  padding: 16px;
  color: var(--ink);
}

/* ── Primitive: .table-hard (printed register) ── */
.table-hard {
  width: 100%; border-collapse: collapse; border-radius: var(--radius);
  font-family: var(--mono); font-size: 12px; color: var(--ink);
}
.table-hard th {
  text-align: left; padding: 8px 12px;
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  letter-spacing: 1px; text-transform: uppercase;
  color: var(--paper); background: var(--ink);
  border: 1px solid var(--line);
}
.table-hard td {
  padding: 6px 12px; border: 1px solid var(--line-soft);
  font-family: var(--mono); color: var(--ink);
}
.table-hard tbody tr:nth-child(even) td { background: var(--paper-2); }
.table-hard tbody tr:hover td { background: var(--accent-bg); }

/* ── Typographic helpers ──────────────── */
.mono { font-family: var(--mono); }
.uppercase {
  text-transform: uppercase; letter-spacing: 1.5px;
  font-family: var(--mono); font-weight: 600; font-size: 10px; color: var(--ink-dim);
}
.metric {
  font-family: var(--mono); font-weight: 700; font-size: 28px;
  line-height: 1; color: var(--ink); letter-spacing: -0.5px;
}
.metrics {
  display: grid; gap: 12px 24px; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
}
.metric-value {
  font: 700 28px/1 var(--mono); letter-spacing: -0.5px; color: var(--ink);
  font-variant-numeric: tabular-nums;
}

/* ── Bento Grid (legacy markup — restyled brutalist) ── */
.bento {
  flex: 1; display: grid;
  grid-template-columns: 1fr 340px;
  grid-template-rows: 1fr auto;
  gap: 1px; padding: 1px;
  background: var(--line);
  overflow: hidden;
  border-bottom: 2px solid var(--line);
}
.tile {
  background: var(--paper);
  border: 0;
  border-radius: var(--radius);
  display: flex; flex-direction: column;
  overflow: hidden;
}
.tile-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px; min-height: 36px;
  border-bottom: 1px solid var(--line);
  background: var(--paper-2);
}
.tile-title {
  font-family: var(--mono); font-size: 11px; font-weight: 600;
  letter-spacing: 1px; text-transform: uppercase; color: var(--ink-dim);
}
.panel-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px; min-height: 36px; border-bottom: 1px solid var(--line);
  background: var(--paper-2);
}
.panel-title {
  font: 600 11px var(--mono); letter-spacing: 1px; text-transform: uppercase;
  color: var(--ink-dim);
}

/* ── Constellation Tile ────────────────── */
.constellation-tile { grid-column: 1; grid-row: 1; }
#constellation-canvas { flex: 1; width: 100%; cursor: pointer; background: var(--paper); }

/* ── Telemetry Tile ────────────────────── */
.telemetry-tile { grid-column: 2; grid-row: 1; }
.telemetry-stream {
  flex: 1; overflow-y: auto;
  font-family: var(--mono); font-size: 11px;
  padding: 8px 12px;
  border-top: 2px solid var(--line);
  scrollbar-width: thin;
  scrollbar-color: var(--line-soft) transparent;
}
.telemetry-stream::-webkit-scrollbar { width: 8px; }
.telemetry-stream::-webkit-scrollbar-thumb {
  background: var(--line-soft); border-radius: var(--radius); }
.tlm-row {
  display: flex; align-items: center; gap: 8px;
  padding: 3px 0; white-space: nowrap;
  border-bottom: 1px solid var(--line-soft);
}
.tlm-time { color: var(--ink-dim); flex-shrink: 0; }
.tlm-icon { flex-shrink: 0; width: 14px; text-align: center; }
.tlm-icon.ok { color: var(--ok); }
.tlm-icon.err { color: var(--err); }
.tlm-name { color: var(--ink); overflow: hidden; text-overflow: ellipsis; }
.tlm-ms { color: var(--ink-dim); margin-left: auto; flex-shrink: 0; }

/* ── Stats / Tunnel / Auth Tiles ───────── */
.stats-row {
  grid-column: 1 / -1; grid-row: 2;
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px;
  background: var(--line); border-top: 1px solid var(--line);
}
.mini-tile {
  background: var(--paper);
  padding: 14px 16px;
}
.mini-label {
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  letter-spacing: 1px; text-transform: uppercase; color: var(--ink-dim);
  margin-bottom: 6px;
}
.mini-content { display: flex; align-items: baseline; gap: 16px; }
.big-num {
  font-family: var(--mono); font-size: 28px; font-weight: 700;
  color: var(--ink); line-height: 1; letter-spacing: -0.5px;
  font-variant-numeric: tabular-nums;
}
.big-sub { font-family: var(--mono); font-size: 12px; color: var(--ink-dim); }
.btn-tunnel {
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  letter-spacing: 0.5px; text-transform: uppercase;
  padding: 4px 10px; border-radius: var(--radius); cursor: pointer;
  border: 1px solid var(--line); color: var(--ink);
  background: var(--paper); user-select: none;
  transition: background var(--motion-fast) var(--motion-ease-in-out);
}
.btn-tunnel:hover { background: var(--paper-2); }
.btn-tunnel.active { background: var(--ok); border-color: var(--ok); color: var(--paper); }
.tunnel-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 4px 0;
}
.tunnel-name { font-family: var(--mono); font-size: 12px; color: var(--ink); }

/* ── Command Bar ───────────────────────── */
.command-bar {
  height: 40px; min-height: 40px;
  display: flex; align-items: center;
  padding: 0 16px; gap: 8px;
  background: var(--ink);
  border-top: 2px solid var(--line);
}
.cmd-prompt { font-family: var(--mono); font-weight: 700; color: var(--accent); }
#cmd-input {
  flex: 1; background: transparent; border: none; outline: none;
  font-family: var(--mono); font-size: 13px; color: var(--paper);
}
#cmd-input::placeholder { color: var(--ink-dim); }
.cmd-hint {
  font-family: var(--mono); font-size: 10px; color: var(--paper);
  padding: 2px 6px; border-radius: var(--radius); border: 1px solid rgba(255,255,255,0.4);
}

/* ── Detail Panel ──────────────────────── */
.detail-panel {
  position: fixed; top: 90px; right: 0; bottom: 40px;
  width: 320px; z-index: var(--z-detail);
  background: var(--paper);
  border-left: 2px solid var(--line);
  transform: translateX(100%);
  transition: transform var(--motion-base) var(--motion-ease-out);
  display: flex; flex-direction: column;
  overflow-y: auto;
}
.detail-panel.open { transform: translateX(0); }
.detail-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px; border-bottom: 2px solid var(--line);
  background: var(--paper-2);
}
.detail-name {
  font-family: var(--mono); font-size: 16px; font-weight: 700;
  color: var(--ink);
}
.detail-close {
  cursor: pointer; color: var(--ink-dim); font-size: 18px;
  width: 28px; height: 28px; border-radius: var(--radius);
  border: 1px solid var(--line);
  display: flex; align-items: center; justify-content: center;
  transition: background var(--motion-fast) var(--motion-ease-in-out);
}
.detail-close:hover { color: var(--err); background: var(--accent-bg); }
.detail-section {
  padding: 14px 16px; border-bottom: 1px solid var(--line-soft);
}
.detail-label {
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  letter-spacing: 1px; text-transform: uppercase; color: var(--ink-dim);
  margin-bottom: 8px;
}
.detail-value {
  font-family: var(--mono); font-size: 12px; color: var(--ink);
  word-break: break-all;
}
.detail-link {
  font-family: var(--mono); font-size: 12px; color: var(--accent);
  text-decoration: none; word-break: break-all;
}
.detail-link:hover { text-decoration: underline; }
.detail-status {
  display: inline-flex; align-items: center; gap: 8px;
  font-family: var(--mono); font-size: 12px; color: var(--ink);
}
.detail-status::before {
  content: ''; width: 8px; height: 8px; border-radius: var(--radius);
  background: var(--ink-dim); flex-shrink: 0;
}
.detail-status.ready { color: var(--ok); }
.detail-status.ready::before { background: var(--ok); }
.detail-status.needs { color: var(--accent); }
.detail-status.needs::before { background: var(--accent); }
.detail-status.off { color: var(--ink-dim); }
.badges { display: flex; gap: 6px; flex-wrap: wrap; }
.badge {
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  padding: 2px 8px; border-radius: var(--radius); text-transform: uppercase;
  border: 1px solid var(--line); color: var(--ink);
}
.badge.stdio { color: var(--ok); border-color: var(--ok); }
.badge.sse, .badge.http { color: var(--ink); border-color: var(--line); }
.badge.native { color: var(--accent); border-color: var(--accent); background: var(--accent-bg); }
.badge.high { color: var(--err); border-color: var(--err); }
.badge.medium { color: var(--accent); border-color: var(--accent); background: var(--accent-bg); }
.badge.low { color: var(--ok); border-color: var(--ok); }
.detail-actions {
  padding: 16px; display: flex; gap: 8px;
}
.btn-action {
  flex: 1; font-family: var(--mono); font-size: 12px; font-weight: 600;
  padding: 8px; border-radius: var(--radius); cursor: pointer;
  border: 1px solid var(--ink); background: var(--ink); color: var(--paper);
  text-transform: uppercase; letter-spacing: 0.5px;
  transition: background var(--motion-fast) var(--motion-ease-in-out);
}
.btn-action:hover { background: var(--paper); color: var(--ink); }
.btn-action:active { transform: translateY(1px); }
.btn-action.primary { background: var(--ink); border-color: var(--ink); color: var(--paper); }
.btn-action.primary:hover { background: var(--paper); color: var(--ink); }
.btn-action.danger { background: var(--err); border-color: var(--err); color: var(--paper); }
.btn-action.danger:hover { background: var(--paper); color: var(--err); }

/* ── Toast ─────────────────────────────── */
.toast-container {
  position: fixed; bottom: 52px; left: 50%;
  transform: translateX(-50%); z-index: var(--z-toast);
  display: flex; flex-direction: column; gap: 8px; align-items: center;
}
.toast {
  font-family: var(--mono); font-size: 12px;
  padding: 8px 16px; border-radius: var(--radius);
  background: var(--paper); border: 1px solid var(--line); color: var(--ink);
}
.toast.success { border-color: var(--ok); border-left-width: 4px; }
.toast.error { border-color: var(--err); border-left-width: 4px; }

/* ── Nav Tabs ─────────────────────────── */
.nav-tabs {
  display: flex; gap: 0; padding: 0; align-items: stretch;
  background: var(--paper);
  border-bottom: 2px solid var(--line);
  min-height: 38px;
  overflow-x: auto;
}
.tab {
  font-family: var(--mono); font-size: 11px; font-weight: 600;
  letter-spacing: 1px; text-transform: uppercase; color: var(--ink-dim);
  min-height: 44px; padding: 0 16px; cursor: pointer; border: none; background: transparent;
  display: flex; align-items: center; position: relative;
  transition: color var(--motion-fast) var(--motion-ease-in-out); white-space: nowrap;
  border-right: 1px solid var(--line-soft);
}
.tab:hover { color: var(--ink); }
.tab.active { color: var(--ink); background: var(--paper-2); }
.tab.active::after {
  content: ''; position: absolute; bottom: -2px; left: 0; right: 0;
  height: 2px; background: var(--accent);
}
.tab-num { display: none; }
/* ── Views ────────────────────────────── */
.view { display: none; flex: 1; overflow: hidden; }
.view.active { display: flex; flex-direction: column; }
.view-scroll {
  flex: 1; overflow-y: auto;
  scrollbar-width: thin; scrollbar-color: var(--line-soft) transparent;
}
.view-scroll::-webkit-scrollbar { width: 8px; }
.view-scroll::-webkit-scrollbar-thumb {
  background: var(--line-soft); border-radius: var(--radius);
}
.view-header {
  padding: 12px 16px; border-bottom: 1px solid var(--line);
  background: var(--paper-2);
  display: flex; align-items: center; justify-content: space-between;
  min-height: 38px;
}
.view-title {
  font-family: var(--mono); font-size: 13px; font-weight: 700;
  color: var(--ink); text-transform: uppercase; letter-spacing: 1px;
  text-wrap: balance;
}
.view-empty {
  padding: 48px 20px; text-align: center;
  font-family: var(--mono); font-size: 12px; color: var(--ink-dim);
}
.catalog-toolbar {
  padding: 10px 12px 0;
  position: sticky; top: 0; z-index: 2;
  background: var(--paper-2); border-bottom: 1px solid var(--line);
}
#catalog-search { width: 100%; max-width: 420px; }

/* ── Server Grid (Catalog) ────────────── */
.server-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1px; padding: 1px;
  background: var(--line);
}
.server-card {
  position: relative;
  background: var(--paper); border: 0;
  border-radius: var(--radius); padding: 14px; cursor: pointer;
  transition: background var(--motion-fast) var(--motion-ease-in-out);
}
.server-card:hover { background: var(--paper-2); }
.server-card-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 8px; gap: 8px;
  padding-bottom: 8px; border-bottom: 1px solid var(--line);
}
.server-card-name {
  font-family: var(--mono); font-size: 13px; font-weight: 700;
  color: var(--ink);
  overflow: hidden; text-overflow: ellipsis;
}
.server-card-desc {
  font-size: 12px; color: var(--ink-dim); line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; overflow: hidden;
}
.toggle-switch {
  width: 44px; height: 24px; border-radius: var(--radius);
  background: var(--paper-2); position: relative; cursor: pointer;
  border: 1px solid var(--line);
  transition: background var(--motion-fast) var(--motion-ease-in-out); flex-shrink: 0;
}
.toggle-switch::after {
  content: ''; position: absolute; top: 2px; left: 2px;
  width: 18px; height: 18px; border-radius: var(--radius);
  background: var(--ink-dim);
  transform: translateX(0);
  transition: transform var(--motion-fast) var(--motion-ease-in-out),
              background var(--motion-fast) var(--motion-ease-in-out);
  will-change: transform;
}
.toggle-switch.on { background: var(--ok); border-color: var(--ok); }
.toggle-switch.on::after { transform: translateX(20px); background: var(--paper); }
.toggle-switch.pending { background: var(--accent); border-color: var(--accent); }
.toggle-switch.pending::after { transform: translateX(20px); background: var(--paper); }
/* Single quiet pending indicator — opacity only, no scale/particles. */
.toggle-switch.pending::after {
  animation: kater-pending 1.2s var(--motion-ease-in-out) infinite;
}
@keyframes kater-pending {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.45; }
}

/* ── Eval Table ───────────────────────── */
.eval-table {
  width: 100%; border-collapse: collapse; font-size: 12px;
  border: 1px solid var(--line); border-radius: var(--radius);
}
.eval-table th {
  text-align: left; padding: 8px 12px;
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  letter-spacing: 1px; text-transform: uppercase; color: var(--paper);
  background: var(--ink); border: 1px solid var(--line);
  position: sticky; top: 0;
}
.eval-table td {
  padding: 6px 12px; border: 1px solid var(--line-soft);
  font-family: var(--mono); color: var(--ink);
}
.eval-table tbody tr:nth-child(even) td { background: var(--paper-2); }
.eval-table tbody tr:hover td { background: var(--accent-bg); }
.success-bar {
  display: inline-block; width: 60px; height: 6px;
  background: var(--paper-2); border: 1px solid var(--line);
  border-radius: var(--radius); overflow: hidden;
  vertical-align: middle; margin-right: 8px;
}
.success-bar-fill { height: 100%; border-radius: var(--radius);
  display: block; background: var(--ok); }
.eval-summary {
  display: flex; gap: 24px; padding: 14px 16px; flex-wrap: wrap;
  border-bottom: 1px solid var(--line);
  background: var(--paper-2);
}
.eval-stat {
  font-family: var(--mono); font-size: 12px; color: var(--ink-dim);
}
.eval-stat .big-num { font-size: 20px; }

/* ── Code Preview (Deploy) ────────────── */
.code-tabs {
  display: flex; gap: 0; padding: 12px 12px 0; flex-wrap: wrap;
  border-bottom: 1px solid var(--line);
}
.code-tab {
  font-family: var(--mono); font-size: 11px; font-weight: 600;
  padding: 6px 12px; border-radius: var(--radius); cursor: pointer;
  border: 1px solid var(--line); border-bottom-width: 0; background: var(--paper);
  color: var(--ink-dim); transition: background var(--motion-fast) var(--motion-ease-in-out);
}
.code-tab:hover { color: var(--ink); background: var(--paper-2); }
.code-tab.active {
  background: var(--ink); color: var(--paper); border-color: var(--ink);
}
.code-preview { padding: 0 12px 12px; }
.code-desc {
  font-family: var(--mono); font-size: 12px; color: var(--ink-dim);
  padding: 8px 0 0;
}
.code-wrap { position: relative; margin-top: 12px; }
.code-block {
  margin: 0; padding: 14px;
  background: var(--paper-2); border: 1px solid var(--line);
  border-radius: var(--radius);
  font-family: var(--mono); font-size: 12px; color: var(--ink);
  white-space: pre; overflow-x: auto; max-height: 55vh;
  scrollbar-width: thin; scrollbar-color: var(--line-soft) transparent;
}
.code-block::-webkit-scrollbar { height: 8px; width: 8px; }
.code-block::-webkit-scrollbar-thumb {
  background: var(--line-soft); border-radius: var(--radius);
}
.code-copy {
  position: absolute; top: 10px; right: 10px; z-index: 2;
  font-family: var(--mono); font-size: 10px; text-transform: uppercase;
  padding: 4px 10px; border-radius: var(--radius); cursor: pointer;
  border: 1px solid var(--line); background: var(--paper);
  color: var(--ink-dim); transition: background var(--motion-fast) var(--motion-ease-in-out);
}
.code-copy:hover { color: var(--ink); background: var(--paper-2); }
.code-copy:active { transform: translateY(1px); }
.code-copy.copied { color: var(--ok); border-color: var(--ok); }

/* Confirm dialog — state-transition emphasis in/out, sharp not playful. */
.confirm-overlay {
  position: fixed; inset: 0; z-index: var(--z-modal);
  display: flex; align-items: center; justify-content: center;
  background: rgba(17, 17, 17, 0.4);
  padding: 24px;
  opacity: 0; transition: opacity var(--motion-fast) var(--motion-ease-in-out);
}
.confirm-overlay:not(.hidden) { opacity: 1; }
.confirm-card {
  transform: translateY(8px);
  opacity: 0; will-change: transform, opacity;
  transition: transform var(--motion-fast) var(--motion-ease-out),
              opacity var(--motion-fast) var(--motion-ease-out);
  background: var(--paper); border: 2px solid var(--err); max-width: 440px; width: 100%;
}
.confirm-overlay:not(.hidden) .confirm-card { transform: translateY(0); opacity: 1; }
.confirm-head {
  padding: 10px 14px; border-bottom: 1px solid var(--line);
  font: 600 12px var(--mono); text-transform: uppercase; letter-spacing: 1px;
}
.confirm-body { padding: 14px; }
.confirm-actions {
  padding: 10px 14px; display: flex; gap: 8px; justify-content: flex-end;
  border-top: 1px solid var(--line);
}
.empty-note {
  padding: 16px; color: var(--ink-dim); font: 12px var(--mono);
  text-transform: uppercase; letter-spacing: 1px;
}
.empty-note.err { color: var(--err); }
.modal-overlay, .detail-panel, .view-scroll, .feed, .telemetry-stream {
  overscroll-behavior: contain;
}

/* ── Settings Form ────────────────────── */
.settings-form { padding: 16px; max-width: 560px; }
.form-field { margin-bottom: 18px; }
.form-label {
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  letter-spacing: 1px; text-transform: uppercase; color: var(--ink-dim);
  display: block; margin-bottom: 6px;
}
.form-help {
  color: var(--ink-dim); font-size: 12px; line-height: 1.45;
  margin-top: 6px;
}
.form-input, .form-select {
  width: 100%; min-height: 44px; padding: 9px 12px;
  background: var(--paper); border: 1px solid var(--line);
  border-radius: var(--radius);
  font-family: var(--mono); font-size: 13px; color: var(--ink);
  outline: none; transition: border-color var(--motion-fast) var(--motion-ease-in-out);
}
.form-input:focus, .form-select:focus { border-color: var(--accent); }
.btn-save {
  font-family: var(--mono); font-size: 12px; font-weight: 600;
  min-height: 44px; padding: 9px 20px; border-radius: var(--radius); cursor: pointer;
  border: 1px solid var(--ink); background: var(--ink); color: var(--paper);
  text-transform: uppercase; letter-spacing: 0.5px;
  transition: background var(--motion-fast) var(--motion-ease-in-out);
}
.btn-save:hover { background: var(--paper); color: var(--ink); }
.btn-save:active { transform: translateY(1px); }

/* ── Modal (credentials) ───────────────── */
.modal-overlay {
  position: fixed; inset: 0; z-index: var(--z-modal);
  display: none; align-items: center; justify-content: center;
  background: rgba(17, 17, 17, 0.55);
  padding: 20px;
}
.modal-overlay.show { display: flex; }
.modal-card {
  width: min(460px, 96vw);
  background: var(--paper);
  border: 2px solid var(--line);
  border-radius: var(--radius);
  padding: 22px;
}
.modal-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 6px;
  padding-bottom: 10px; border-bottom: 1px solid var(--line);
}
.modal-title {
  font-family: var(--mono); font-size: 15px; font-weight: 700;
  letter-spacing: 0.5px; color: var(--ink); text-transform: uppercase;
}
.modal-sub {
  color: var(--ink-dim); font-size: 13px; line-height: 1.5;
  margin-bottom: 18px;
}
.modal-actions {
  display: flex; gap: 10px; align-items: center; margin-top: 6px;
}
.modal-actions .btn-action { flex: 1; text-transform: none; letter-spacing: 0; }
.modal-actions .btn-action#cred-provider {
  flex: 0 0 auto; text-decoration: none; display: inline-flex;
  align-items: center; justify-content: center;
}

/* ── Auth gate ─────────────────────────── */
#auth-gate {
  position: fixed; inset: 0; z-index: var(--z-auth);
  display: none; align-items: center; justify-content: center;
  background: rgba(17, 17, 17, 0.55);
}
#auth-gate.show { display: flex; }
.auth-card {
  width: min(460px, 92vw);
  background: var(--paper);
  border: 2px solid var(--err);
  border-radius: var(--radius);
  padding: 28px;
}
.auth-card h2 {
  font-family: var(--mono); font-size: 18px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 1px;
  color: var(--ink); margin-bottom: 8px;
}
.auth-card p { color: var(--ink-dim); margin-bottom: 20px; font-size: 13px; }
.auth-card input {
  width: 100%; padding: 10px 12px; margin-bottom: 12px;
  background: var(--paper); border: 1px solid var(--line);
  border-radius: var(--radius); color: var(--ink);
  font-family: var(--mono); font-size: 13px;
}
.auth-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }

/* ── Responsive ────────────────────────── */
@media (max-width: 980px) {
  .topbar { align-items: flex-start; flex-direction: column; padding: 12px 14px; }
  .topbar-left, .topbar-right { width: 100%; flex-wrap: wrap; }
  .topbar-right { justify-content: flex-start; }
  .profile-pills { max-width: 100%; overflow-x: auto; padding-bottom: 2px; }
}
@media (max-width: 768px) {
  html, body { overflow: auto; }
  #app { height: auto; min-height: 100dvh; }
  .nav-tabs { padding: 0; }
  .tab { flex: 1 0 auto; justify-content: center; padding: 0 12px; }
  .bento { grid-template-columns: 1fr; grid-template-rows: 1fr 200px auto; }
  .constellation-tile { grid-column: 1; }
  .telemetry-tile { grid-column: 1; grid-row: 2; }
  .stats-row { grid-column: 1; grid-row: 3; grid-template-columns: 1fr; }
  .detail-panel { top: 0; bottom: 0; width: 100%; }
  .command-bar { min-height: 48px; }
  .cmd-hint { display: none; }
  .auth-actions { grid-template-columns: 1fr; }
}
"""


_HTML_SHELL_TOP = r"""
<div id="bg-gradient"></div>
<div id="boot"><div class="boot-text" id="boot-text"></div></div>

<a href="#app" class="sr-only skip-link">Skip to content</a>

<div id="auth-gate">
  <div class="auth-card">
    <h2>Sign in to Kater</h2>
    <p>This gateway requires authentication. Use OAuth or paste an API key.</p>
    <label for="auth-key-input" class="sr-only">API key</label>
    <input type="password" id="auth-key-input" placeholder="API key (optional)" autocomplete="off">
    <div class="auth-actions">
      <button class="btn-save btn" id="auth-oauth-btn" type="button">Sign in with OAuth</button>
      <button class="btn-save btn" id="auth-key-btn" type="button">Use API key</button>
    </div>
  </div>
</div>

<div id="app">
  <h1 class="sr-only">Kater Control</h1>
  <div class="topbar">
    <div class="topbar-left">
      <div class="brand">
        <span class="brand-mark" aria-hidden="true">&#9612;</span>
        KATER
        <span class="version-tag" id="version-tag">v0.0.0</span>
      </div>
      <div class="profile-pills" id="profile-pills" role="group" aria-label="Profiles"></div>
    </div>
    <div class="topbar-right">
      <div class="tag" id="ws-chip">
        <span class="status-dot off" id="ws-dot"></span>
        <span id="ws-status">ws offline</span>
      </div>
      <div class="tag" id="auth-chip">
        <span class="auth-dot" id="auth-dot"></span>
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
  <header class="view-header">
    <span class="view-title">CONTROL PLANE</span>
    <span class="tile-title" id="node-count">0 nodes</span>
  </header>
  <div class="view-scroll">
    <div class="grid-hard">

      <section class="panel" id="panel-metrics">
        <div class="panel-head">
          <span class="panel-title">KEY METRICS</span>
        </div>
        <dl class="metrics">
          <div class="metric">
            <dt>Tools enabled</dt>
            <dd class="metric-value"><data id="stat-enabled">0</data></dd>
          </div>
          <div class="metric">
            <dt>Total tools</dt>
            <dd class="metric-value"><data id="stat-tools">0</data></dd>
          </div>
          <div class="metric">
            <dt>Success rate</dt>
            <dd class="metric-value"><data id="stat-success">0%</data></dd>
          </div>
          <div class="metric">
            <dt>Backends</dt>
            <dd class="metric-value"><data id="stat-backends">0</data></dd>
          </div>
          <div class="metric">
            <dt>Events</dt>
            <dd class="metric-value"><data id="stat-events">0</data></dd>
          </div>
        </dl>
      </section>

      <section class="panel" id="panel-tunnels">
        <div class="panel-head">
          <span class="panel-title">TUNNELS</span>
        </div>
        <dl class="kv">
          <div class="kv-row">
            <dt>cloudflare</dt>
            <dd><button class="btn" id="btn-cf" type="button"
              data-name="cloudflare"
              onclick="toggleTunnel(this)">START</button></dd>
          </div>
          <div class="kv-row">
            <dt>tailscale</dt>
            <dd><button class="btn" id="btn-ts" type="button"
              data-name="tailscale"
              onclick="toggleTunnel(this)">START</button></dd>
          </div>
        </dl>
      </section>

      <section class="panel" id="panel-constellation">
        <div class="panel-head">
          <span class="panel-title">TOPOLOGY</span>
        </div>
        <canvas id="constellation-canvas"></canvas>
      </section>

      <section class="panel panel-wide" id="panel-telemetry">
        <div class="panel-head">
          <span class="panel-title">LIVE TELEMETRY</span>
          <span class="tag tag--accent" id="tlm-state">STREAM</span>
        </div>
        <div class="feed" id="telemetry-stream" role="log" aria-live="polite"></div>
      </section>

      <section class="panel" id="backend-health" aria-label="Backend health">
        <div class="panel-head">
          <span class="panel-title">BACKEND HEALTH</span>
        </div>
        <div class="feed" id="backend-health-body"></div>
      </section>

      <section class="panel panel-wide" id="recent-calls" aria-label="Recent calls">
        <div class="panel-head">
          <span class="panel-title">RECENT CALLS</span>
        </div>
        <div class="feed" id="recent-calls-body"></div>
      </section>

    </div>
  </div>
  </div>
"""

_VIEW_CATALOG = r"""
  <div class="view" id="view-catalog" role="tabpanel"
    aria-labelledby="tab-catalog" tabindex="0" hidden>
    <header class="view-header">
      <span class="view-title">SERVER CATALOG</span>
      <span class="tile-title" id="catalog-count">0 servers</span>
    </header>
    <div class="view-scroll">
      <div class="catalog-toolbar">
        <label class="sr-only" for="catalog-search">Search servers</label>
        <input class="form-input" id="catalog-search" type="search"
          placeholder="Search servers (e.g. search, github)..." autocomplete="off"
          aria-label="Search servers">
      </div>
      <section class="panel panel-full">
        <div class="panel-head">
          <span class="panel-title">REGISTRY</span>
        </div>
        <div class="server-grid" id="catalog-grid">
          <div class="view-empty">Loading catalog...</div>
        </div>
      </section>
    </div>
  </div>
"""

_VIEW_EVALS = r"""
  <div class="view" id="view-evals" role="tabpanel"
    aria-labelledby="tab-evals" tabindex="0" hidden>
    <header class="view-header">
      <span class="view-title">TOOL PERFORMANCE</span>
    </header>
    <div class="view-scroll">
      <section class="panel">
        <div class="panel-head">
          <span class="panel-title">EVALUATION INDEX</span>
        </div>
        <div class="eval-summary" id="eval-summary"></div>
        <table class="eval-table table-hard">
          <thead><tr>
            <th>Tool</th><th>Calls</th><th>Success</th><th>Avg Latency</th>
          </tr></thead>
          <tbody id="eval-tbody"></tbody>
        </table>
      </section>
    </div>
  </div>
"""

_VIEW_DEPLOY = r"""
  <div class="view" id="view-deploy" role="tabpanel"
    aria-labelledby="tab-deploy" tabindex="0" hidden>
    <header class="view-header">
      <span class="view-title">DEPLOYMENT CONFIGS</span>
    </header>
    <div class="view-scroll">
      <section class="panel panel-doc">
        <div class="panel-head">
          <span class="panel-title">DEPLOY MANIFEST</span>
        </div>
        <div class="code-tabs" id="deploy-tabs"></div>
        <div class="code-preview">
          <output class="code-desc" id="deploy-desc"></output>
          <div class="code-wrap">
            <button class="code-copy btn" onclick="copyDeployCode(this)"
              aria-label="Copy deployment code">Copy</button>
            <pre class="code-block" id="deploy-code">Select a format above.</pre>
          </div>
        </div>
      </section>
    </div>
  </div>
"""

_VIEW_SETTINGS = r"""
  <div class="view" id="view-settings" role="tabpanel"
    aria-labelledby="tab-settings" tabindex="0" hidden>
    <header class="view-header">
      <span class="view-title">SETTINGS</span>
    </header>
    <div class="view-scroll">
      <section class="panel">
        <div class="panel-head">
          <span class="panel-title">GATEWAY CONFIG</span>
        </div>
        <form class="settings-form kv" onsubmit="return false;">
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
          <button class="btn-save btn" onclick="saveSettings()">Save Settings</button>
        </form>
      </section>
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
    <output id="telegraph" class="telegraph" aria-live="polite"></output>
  </div>
</div>

<aside class="detail-panel panel--hard" id="detail-panel" aria-label="Server details">
  <div class="detail-header">
    <span class="detail-name" id="detail-name">-</span>
    <button class="detail-close" type="button" onclick="closeDetail()"
      aria-label="Close details"
      onkeydown="btnKey(event,closeDetail)">&times;</button>
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
    <button class="btn-action btn" id="btn-connect" type="button"
      onclick="connectSelected()" style="width:100%">Connect…</button>
  </div>
  <div class="detail-actions">
    <button class="btn-action btn" id="confirm-server-enable" type="button"
      data-confirm="enable"
      data-confirm-title="Enable Server"
      data-confirm-body="Enable this server? It will be included in the active profile."
      onclick="detailToggle(true)">Enable</button>
    <button class="btn-action btn btn--danger" id="confirm-server-disable" type="button"
      data-confirm="disable"
      data-confirm-title="Disable Server"
      data-confirm-body="Disable this server? Its tools will be removed from the active profile."
      onclick="detailToggle(false)">Disable</button>
  </div>
</aside>

<div class="modal-overlay" id="credentials-modal" role="dialog" aria-modal="true"
  aria-labelledby="cred-title">
  <div class="modal-card panel--hard">
    <div class="modal-head">
      <span class="modal-title" id="cred-title">Connect</span>
      <button class="detail-close" type="button" onclick="closeCredentialsModal()"
        aria-label="Close"
        onkeydown="btnKey(event,closeCredentialsModal)">&times;</button>
    </div>
    <p class="modal-sub" id="cred-sub">Paste a token to connect this server.</p>
    <div id="cred-fields"></div>
    <div class="modal-actions">
      <a class="btn-action btn" id="cred-provider" href="#" target="_blank"
        rel="noopener" style="display:none">Get a token &#8599;</a>
      <button class="btn-action btn" id="confirm-cred-save" type="button"
        data-confirm="save-credentials"
        data-confirm-title="Save Credentials"
        data-confirm-body="Save these credentials and connect the server?"
        onclick="saveCredentials()">Save &amp; connect</button>
    </div>
  </div>
</div>

<div class="confirm-overlay" id="confirm" role="alertdialog" aria-modal="true"
  aria-labelledby="confirm-title" aria-describedby="confirm-body" hidden>
  <div class="confirm-card panel--hard">
    <div class="confirm-head">
      <span class="confirm-title" id="confirm-title">Confirm</span>
    </div>
    <p class="confirm-body" id="confirm-body"></p>
    <div class="confirm-actions">
      <button class="btn-action btn" id="confirm-cancel" type="button"
        onclick="closeConfirm()">Cancel</button>
      <button class="btn-action btn btn--danger" id="confirm-ok" type="button"
        onclick="runConfirmed()">Confirm</button>
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
'use strict';

/* ────────────────────────────────────────────────────────────────────────
 * Kater dashboard — operator cockpit wiring.
 * Brutalist white-first. No canvas, no glow, no SaaS decoration.
 * Motion is delegated to Agent E via Kater.motion.* hooks (WAAPI/CSS).
 * ──────────────────────────────────────────────────────────────────────── */

const API = '';

// Bearer token used for authenticated API + WS handshake.
const AUTH_STORAGE = 'kater_bearer';

// wsPort is injected by Python (window.KATER_CONFIG). Everything reads it.
const WS_PORT = (window.KATER_CONFIG && window.KATER_CONFIG.wsPort) || 9092;
const WS_SCHEME = location.protocol === 'https:' ? 'wss' : 'ws';

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

// Intervals/listeners we own, so we can tear them down on unload.
const timers = new Set();
const controllers = new Set();          // AbortControllers for in-flight fetches
const listeners = [];                   // [target, type, fn] for removeEventListener
const viewIds = ['dashboard', 'catalog', 'evals', 'deploy', 'settings'];

// Motion hooks (Agent E fills these in). Each is no-op-safe.
const Kater = window.Kater || {};
// Reduced-motion gate. The CSS @media block only kills CSS animation/transition;
// JS-driven WAAPI element.animate() is NOT covered by the media query, so we
// must check it explicitly in every motion hook.
function katerReduced() {
  return typeof matchMedia === 'function'
    && matchMedia('(prefers-reduced-motion: reduce)').matches;
}

// Fire a one-shot WAAPI animation (transform/opacity only) and clean up on finish.
// Returns the Animation, or null when reduced-motion is on / unsupported.
function katerAnimate(el, frames, opts) {
  if (!el || katerReduced() || typeof el.animate !== 'function') return null;
  const anim = el.animate(frames, opts);
  anim.addEventListener('finish', () => {
    try { anim.cancel(); } catch (e) {}
  });
  return anim;
}

/* Motion hooks — native CSS + WAAPI only. Disciplined, no slop.
   Keyboard-initiated switches and initial load pass silent:true so the
   visual motion is skipped (productivity tool: Emil weighting). */
Kater.motion = Kater.motion || {
  // 1. View switch crossfade + translateY (≤8px), fast ease-out. Skip on keyboard/silent.
  viewIn(panel, opts) {
    if (!panel || (opts && opts.silent)) return;
    katerAnimate(panel,
      [ { opacity: 0, transform: 'translateY(6px)' }, { opacity: 1, transform: 'translateY(0)' } ],
      { duration: 180, easing: 'cubic-bezier(0.16,1,0.3,1)', fill: 'none' });
  },
  viewOut(panel, opts) {
    if (!panel || (opts && opts.silent)) return;
    katerAnimate(panel,
      [ { opacity: 1, transform: 'translateY(0)' }, { opacity: 0, transform: 'translateY(-4px)' } ],
      { duration: 140, easing: 'cubic-bezier(0.4,0,1,1)', fill: 'none' });
  },
  // 2. New telemetry row: opacity 0→1 + translateY(6px)→0, no loop.
  feedUpdate(row) {
    if (!row) return;
    row.classList.add('kater-rowin');
    trackedTimeout(() => row.classList.remove('kater-rowin'), 220);
  },
  rowIn(row) {
    if (!row) return;
    katerAnimate(row,
      [ { opacity: 0, transform: 'translateY(6px)' }, { opacity: 1, transform: 'translateY(0)' } ],
      { duration: 180, easing: 'cubic-bezier(0.16,1,0.3,1)', fill: 'none' });
  },
  // 3. Restrained count-up on the 4 key .metric-value stats. Transform not used;
  //    we tween the numeral text via rAF, gated by reduced-motion.
  metricSet(el, val, prev) {
    if (!el || katerReduced()) return;
    const to = parseFloat(val);
    const from = parseFloat(prev);
    if (!isFinite(to) || !isFinite(from) || from === to) return;
    const node = el.querySelector('.metric-value') || el;
    const text = node;
    const isPct = /%/.test(el.textContent || '');
    const start = performance.now();
    const dur = 260;
    function step(now) {
      const t = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - t, 3); // ease-out cubic
      const cur = Math.round(from + (to - from) * eased);
      text.textContent = isPct ? cur + '%' : fmtNum(cur);
      if (t < 1) trackedRAF(step);
    }
    if (typeof trackedRAF === 'function') trackedRAF(step);
  },
  // 4. Confirm dialog emphasis in/out — handled by CSS (.confirm-overlay states).
  //    Sharp state-transition; nothing to animate here beyond CSS.
  tabActivate(tab) { /* visual emphasis owned by CSS .active; animated via viewIn */ },
  // 5. Dangerous-action confirm: CSS drives the overlay/card transition. Hook is
  //    a no-op here because the transition lives on the .confirm-overlay class.
  confirmAction(dlg) { /* CSS-driven; see .confirm-overlay rules */ },
  // 6. One restrained status emphasis on a feed row — never particles.
  statusPulse(el, kind) {
    if (!el) return;
    el.classList.add('kater-pulse');
    trackedTimeout(() => el.classList.remove('kater-pulse'), 300);
  },
};
window.Kater = Kater;

// ── Helpers ────────────────────────────
class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function cls(s) {
  return String(s == null ? '' : s).replace(/[^a-z0-9_-]/gi, '');
}

function pad2(n) { return String(n).padStart(2, '0'); }

function authHeaders() {
  const h = {};
  const tok = localStorage.getItem(AUTH_STORAGE);
  if (tok) h['Authorization'] = 'Bearer ' + tok;
  return h;
}

function trackedFetch(url, opts) {
  const c = new AbortController();
  controllers.add(c);
  opts = opts || {};
  opts.headers = Object.assign({}, authHeaders(), opts.headers || {});
  opts.signal = c.signal;
  return fetch(url, opts).finally(() => controllers.delete(c));
}

function trackedInterval(fn, ms) {
  const id = setInterval(fn, ms);
  timers.add(id);
  return id;
}
let rafFrames = new Set();
function trackedRAF(fn) {
  if (typeof requestAnimationFrame !== 'function') return 0;
  const id = requestAnimationFrame((ts) => { rafFrames.delete(id); fn(ts); });
  rafFrames.add(id);
  return id;
}
  const id = setTimeout(() => { timers.delete(id); fn(); }, ms);
  timers.add(id);
  return id;
}
function onEl(target, type, fn, opts) {
  target.addEventListener(type, fn, opts);
  listeners.push([target, type, fn]);
}

async function apiGet(path) {
  const r = await trackedFetch(API + path, { method: 'GET' });
  if (!r.ok) throw new ApiError(r.statusText, r.status, await safeJson(r));
  return r.json();
}
async function apiSend(path, body, method) {
  const r = await trackedFetch(API + path, {
    method: method || 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
  if (!r.ok) throw new ApiError(r.statusText, r.status, await safeJson(r));
  return r.json().catch(() => ({}));
}
async function safeJson(r) {
  try { return await r.json(); } catch (e) { return null; }
}

function $(id) { return document.getElementById(id); }
function qsa(sel, root) {
  return Array.prototype.slice.call((root || document).querySelectorAll(sel));
}

function fmtNum(n, unit) {
  if (n == null || n === '') return '-';
  const v = (typeof n === 'number') ? n : parseFloat(n);
  if (isNaN(v)) return esc(n);
  return unit === '%' ? (v.toFixed(1) + '%') : (Math.round(v).toLocaleString());
}
function fmtBool(b) {
  if (b === true) return 'Y';
  if (b === false) return 'N';
  return esc(b);
}
function fmtDuration(ms) {
  if (ms == null) return '-';
  const v = (typeof ms === 'number') ? ms : parseFloat(ms);
  if (isNaN(v)) return '-';
  return v.toFixed(0) + 'ms';
}
function fmtTime(t) {
  if (!t) return '-';
  const d = new Date(t.endsWith('Z') || t.includes('+') || /\d\d:\d\d:\d\d/.test(t) ? t : t + 'Z');
  if (isNaN(d.getTime())) return esc(t);
  return pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds());
}

// ── Status / transport mapping (amber only for warn/pending; green ok; red err) ──
function tagFor(kind, text) {
  const map = {
    ok: 'tag--ok', err: 'tag--err', accent: 'tag--accent',
    warn: 'tag--accent', pending: 'tag--accent', run: 'tag--accent',
    off: 'tag--muted', idle: 'tag--muted',
  };
  const c = map[kind] || 'tag--muted';
  return '<span class="tag ' + c + '">' + esc(text) + '</span>';
}
function healthKind(h) {
  if (h === true) return 'ok';
  if (h === false) return 'err';
  return 'muted';
}
function breakerKind(s) {
  if (s === 'open') return 'err';
  if (s === 'half-open') return 'accent';
  return 'ok';
}
function statusKind(status) {
  if (!status) return 'muted';
  const s = String(status).toLowerCase();
  if (s === 'running' || s === 'healthy' || s === 'ok' || s === 'enabled') return 'ok';
  if (s === 'error' || s === 'failed' || s === 'down' || s === 'disabled') return 'err';
  if (s === 'pending' || s === 'starting' || s === 'degraded') return 'accent';
  return 'muted';
}

// ── Boot / status text ─────────────────
function setBoot(text, done) {
  const el = $('boot');
  const t = $('boot-text');
  if (!el) return;
  if (t) t.textContent = text || '';
  el.classList.toggle('hidden', !!done);
  if (done) el.setAttribute('aria-hidden', 'true');
  else el.removeAttribute('aria-hidden');
}

function setWsStatus(state, detail) {
  const dot = $('ws-dot');
  const label = $('ws-status');
  const chip = $('ws-chip');
  if (dot) dot.className = 'status-dot ' + cls(state);
  if (label) {
    const txt = {
      online: 'ws online', offline: 'ws offline',
      connecting: 'ws connecting…', auth: 'ws authenticating…',
    }[state] || ('ws ' + state);
    label.textContent = detail ? (txt + ' · ' + detail) : txt;
  }
  if (chip) chip.dataset.state = state;
}

// ── Telegraph status line (command box) ───────────────────────────────────
function telegraph(msg, kind) {
  const el = $('telegraph');
  if (!el) return;
  el.textContent = msg || '';
  el.dataset.kind = kind || 'info';
  if (Kater.motion && Kater.motion.statusPulse) Kater.motion.statusPulse(el, kind);
}

// ── Tab navigation (ARIA contract) ────────────────────────────────────────
function initTabNavigation() {
  const tablist = document.querySelector('[role="tablist"]');
  if (!tablist) return;
  const tabs = qsa('[role="tab"]', tablist);
  function focusTab(tab) { if (tab) tab.focus(); }

  tabs.forEach((tab) => {
    onEl(tab, 'keydown', (e) => {
      const i = tabs.indexOf(tab);
      let next = null;
      switch (e.key) {
        case 'ArrowRight': next = tabs[(i + 1) % tabs.length]; break;
        case 'ArrowLeft': next = tabs[(i - 1 + tabs.length) % tabs.length]; break;
        case 'Home': next = tabs[0]; break;
        case 'End': next = tabs[tabs.length - 1]; break;
        case 'Enter':
        case ' ':
          e.preventDefault();
          // Keyboard-initiated switch: skip visual motion (productivity tool).
          switchView(tab.dataset.view, { focusTab: true, viaKeyboard: true, silent: true });
          return;
        default: return;
      }
      if (next) { e.preventDefault(); focusTab(next); }
    });
  });
}

function switchView(view, opts) {
  opts = opts || {};
  const tab = $('tab-' + view);
  const panel = $('view-' + view);
  if (!tab || !panel) return;

  qsa('[role="tab"]').forEach((t) => {
    const active = t === tab;
    t.setAttribute('aria-selected', active ? 'true' : 'false');
    t.tabIndex = active ? 0 : -1;
    t.classList.toggle('active', active);
  });
  qsa('[role="tabpanel"]').forEach((p) => {
    const show = p === panel;
    if (show) {
      p.hidden = false;
      if (Kater.motion && Kater.motion.viewIn) Kater.motion.viewIn(p, opts);
    } else {
      if (Kater.motion && Kater.motion.viewOut) Kater.motion.viewOut(p, opts);
      p.hidden = true;
    }
  });
  try { history.replaceState(null, '', '#' + view); } catch (e) {}
  if (opts.focusTab && tab) tab.focus();
  // Lazy data hydration for heavy views.
  if (view === 'catalog' && !catalogReloadTimer) loadCatalog();
  if (view === 'deploy') hydrateDeploy();
  if (view === 'settings') hydrateSettings();
  if (view === 'dashboard' && appReady) { loadStatus(); }
}

// ── Server list (catalog) ─────────────────────────────────────────────────
function renderCatalog() {
  const grid = $('catalog-grid');
  const count = $('catalog-count');
  if (!grid) return;

  const list = Array.isArray(servers) ? servers : [];
  const q = (catalogQuery || '').trim().toLowerCase();
  const filtered = q
    ? list.filter((s) => {
        const hay = [s.name, s.transport, s.description, (s.profiles || []).join(' '),
          (s.tags || []).join(' ')].join(' ').toLowerCase();
        return hay.indexOf(q) !== -1;
      })
    : list;

  if (count) count.textContent = filtered.length + ' / ' + list.length;

  if (filtered.length === 0) {
    grid.innerHTML = '<div class="empty-note">No matching servers.</div>';
    return;
  }

  const cards = filtered.map((s) => {
    const enabled = !!s.enabled;
    const state = enabled ? 'enabled' : 'disabled';
    const stKind = enabled ? 'tag--ok' : 'tag--muted';
    const ctlId = 'ctl-' + cls(s.name);
    const profs = esc((s.profiles || []).join(',') || 'core');
    const action = enabled ? 'disable' : 'enable';
    const btnCls = enabled ? 'btn-warn' : 'btn-ok';
    const btnTxt = enabled ? 'Disable' : 'Enable';
    const card = [
      '<article class="server-card" data-name="' + esc(s.name) + '" tabindex="0"',
      ' role="button" aria-label="Server ' + esc(s.name) + '"',
      ' onclick="detailToggle(\'' + esc(s.name) + '\')"',
      ' onkeydown="btnKey(event,function(){detailToggle(\'' + esc(s.name) + '\')})">',
      '<div class="server-card-top">',
      '<span class="server-name">' + esc(s.name) + '</span>',
      '<span class="tag ' + stKind + '">' + state + '</span>',
      '</div>',
      '<div class="server-transport">' + esc(s.transport || '?') + '</div>',
      '<div class="server-desc">' + esc(s.description || 'No description.') + '</div>',
      '<div class="server-card-foot">',
      '<span class="tag tag--muted">' + profs + '</span>',
      '<button class="btn ' + btnCls + '" id="' + ctlId + '" data-confirm="' + action + '"',
      ' data-name="' + esc(s.name) + '">' + btnTxt + '</button>',
      '</div>',
      '</article>',
    ].join('');
    return card;
  }).join('');

  grid.innerHTML = cards;
}

function loadCatalog() {
  apiGet('/api/catalog').then((data) => {
    const list = Array.isArray(data) ? data : (data.servers || data.items || []);
    servers = list;
    renderCatalog();
  }).catch(() => {
    const grid = $('catalog-grid');
    if (grid) grid.innerHTML = '<div class="empty-note err">Catalog unreachable.</div>';
  });
}

function filterCatalog() {
  renderCatalog();   // servers already cached; filtering is synchronous
}

// ── Dashboard metrics ─────────────────────────────────────────────────────
function setMetric(statEl, value, unit) {
  if (!statEl) return;
  const prev = statEl.dataset.val;
  const next = String(value);
  statEl.textContent = (unit === '%') ? (value + '%') : fmtNum(value);
  statEl.dataset.val = next;
  if (Kater.motion && Kater.motion.metricSet) {
    Kater.motion.metricSet(statEl, next, prev);
  }
}

function loadStatus() {
  apiGet('/api/status').then((data) => {
    const d = data || {};
    const tools = (d.tools || {}).total !== undefined ? d.tools.total : d.tools_enabled;
    const backends = (d.backends && d.backends.total !== undefined)
      ? d.backends.total : d.backends_count;
    const events = (d.events && d.events.total !== undefined) ? d.events.total : d.events_count;
    const success = d.success_rate != null ? d.success_rate
      : (d.success_pct != null ? d.success_pct : d.success);

    setMetric($('stat-tools'), tools);
    setMetric($('stat-backends'), backends);
    setMetric($('stat-events'), events);
    setMetric($('stat-success'), success, '%');

    qsa('.metric').forEach((m) => {
      const key = m.dataset.metric;
      if (!key || !d[key]) return;
      const val = m.querySelector('.metric-val') || m.querySelector('.stat-num');
      if (val) setMetric(val, d[key].total !== undefined ? d[key].total : d[key]);
    });

    const prod = $('profile-pills');
    if (prod && Array.isArray(d.profiles)) {
      profiles = d.profiles;
      activeProfile = d.active_profile || (profiles[0] && profiles[0].id) || 'core';
      renderProfiles();
    }
  }).catch(() => { /* keep last-known values */ });
}

function renderProfiles() {
  const wrap = $('profile-pills');
  if (!wrap) return;
  const list = Array.isArray(profiles) ? profiles : [];
  wrap.innerHTML = list.map((p) => {
    const id = (typeof p === 'string') ? p : p.id;
    const name = (typeof p === 'string') ? p : (p.name || id);
    const on = id === activeProfile;
    return '<button class="pill' + (on ? ' pill--on' : '') + '" type="button" '
      + 'data-profile="' + esc(id) + '" onclick="selectProfile(\'' + esc(id) + '\')">'
      + esc(name) + '</button>';
  }).join('');
}

function selectProfile(id) {
  activeProfile = id;
  renderProfiles();
  loadStatus();
  loadCatalog();
}

// ── Backend health table ──────────────────────────────────────────────────
function renderBackends(data) {
  const body = $('backend-health-body');
  if (!body) return;
  const list = Array.isArray(data) ? data : (data.backends || []);
  if (!list.length) {
    body.innerHTML = '<tr><td colspan="7" class="empty-note">No backends.</td></tr>';
    return;
  }
  body.innerHTML = list.map((b) => {
    const healthy = healthKind(b.healthy);
    const enabled = b.enabled !== false;
    return '<tr>'
      + '<td class="mono strong">' + esc(b.name) + '</td>'
      + '<td>' + tagFor(healthy, fmtBool(b.healthy)) + '</td>'
      + '<td>' + tagFor(enabled ? 'ok' : 'muted', fmtBool(enabled)) + '</td>'
      + '<td class="num">' + fmtNum(b.tool_count) + '</td>'
      + '<td class="num">' + fmtNum(b.latency_ms) + 'ms</td>'
      + '<td>' + tagFor(breakerKind(b.breaker_state), esc(b.breaker_state || 'closed')) + '</td>'
      + '<td>' + tagFor(enabled ? 'ok' : 'muted', fmtBool(enabled)) + '</td>'
      + '</tr>';
  }).join('');
}

function loadBackends() {
  apiGet('/api/backends').then(renderBackends).catch(() => {
    const body = $('backend-health-body');
    if (body) {
      body.innerHTML = '<tr><td colspan="7" class="empty-note err">'
        + 'Backends unreachable.</td></tr>';
    }
  });
}

// ── Recent calls table ────────────────────────────────────────────────────
function renderCalls(data) {
  const body = $('recent-calls-body');
  if (!body) return;
  const list = Array.isArray(data) ? data : (data.events || data.items || []);
  if (!list.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty-note">No recent calls.</td></tr>';
    return;
  }
  body.innerHTML = list.map((e) => {
    const ok = e.success === true || e.success === 1 || e.status === 'ok';
    return '<tr>'
      + '<td class="mono">' + fmtTime(e.timestamp || e.ts) + '</td>'
      + '<td class="mono strong">' + esc(e.name) + '</td>'
      + '<td class="num">' + fmtDuration(e.duration_ms) + '</td>'
      + '<td>' + tagFor(ok ? 'ok' : 'err', ok ? 'OK' : 'ERR') + '</td>'
      + '<td class="mono">' + esc(e.profile || '-') + '</td>'
      + '</tr>';
  }).join('');
}

function loadCalls() {
  apiGet('/api/events?limit=50').then(renderCalls).catch(() => {
    const body = $('recent-calls-body');
    if (body) {
      body.innerHTML = '<tr><td colspan="5" class="empty-note err">'
        + 'Events unreachable.</td></tr>';
    }
  });
}

// ── Telemetry feed (live WS events) ───────────────────────────────────────
function pushTelemetry(ev) {
  const wrap = $('telemetry-stream');
  const feed = wrap ? wrap.querySelector('.feed') : null;
  if (!feed) return;

  const key = (ev.source || '') + ':' + (ev.kind || '') + ':' + (ev.msg || '') ;
  const now = Date.now();
  const last = recentTelemetry.get(key);
  if (last && (now - last) < TELEMETRY_DEDUPE_MS) return;
  recentTelemetry.set(key, now);
  if (recentTelemetry.size > 200) {
    const firstKey = recentTelemetry.keys().next().value;
    recentTelemetry.delete(firstKey);
  }

  const row = document.createElement('div');
  row.className = 'feed-row';
  const kind = ev.kind || 'log';
  if (kind === 'err' || kind === 'error' || kind === 'fail') row.classList.add('feed--err');
  else if (kind === 'warn' || kind === 'pending' || kind === 'run') {
    row.classList.add('feed--accent');
  }
  else if (kind === 'ok' || kind === 'success') row.classList.add('feed--ok');

  const samp = document.createElement('samp');
  samp.textContent = '[' + fmtTime(new Date().toISOString()) + '] '
    + (ev.source ? esc(ev.source) + ' ' : '')
    + (kind ? '(' + esc(kind) + ') ' : '')
    + esc(ev.msg || '');
  row.appendChild(samp);

  feed.insertBefore(row, feed.firstChild);
  while (feed.childElementCount > 200) feed.removeChild(feed.lastChild);
  if (Kater.motion && Kater.motion.feedUpdate) Kater.motion.feedUpdate(row);
}

// ── OAuth + WebSocket ─────────────────────────────────────────────────────
// First-party OAuth — no runtime/missing-client registration.
// client_id: 'kater-dashboard' (test-guarded — do not change).
const OAUTH = { client_id: 'kater-dashboard', grant: 'authorization_code' };

function connectSelected() {
  const authGate = $('auth-gate');
  if (authGate) { authGate.classList.add('hidden'); authGate.setAttribute('aria-hidden', 'true'); }
  initWebSocket();
  loadAll();
}

function beginOAuth() {
  setWsStatus('auth');
  const redirect = location.origin + (location.pathname || '/');
  const url = '/oauth/authorize'
    + '?response_type=code&client_id=' + encodeURIComponent(OAUTH.client_id)
    + '&redirect_uri=' + encodeURIComponent(redirect)
    + '&state=' + encodeURIComponent(String(Date.now()));
  location.href = url;
}

async function wsUrlWithAuth() {
  const r = await trackedFetch('/api/ws-ticket', { method: 'POST' });
  if (!r.ok) throw new ApiError('ticket failed', r.status);
  const data = await r.json();
  const ticket = data.ticket;
  if (!ticket) throw new ApiError('no ticket', 401);
  const host = location.hostname;
  return WS_SCHEME + '://' + host + ':' + WS_PORT + '/ws?ticket=' + encodeURIComponent(ticket);
}

function closeWebSocket() {
  if (wsTimer) { clearTimeout(wsTimer); wsTimer = null; }
  if (!ws) return;
  const old = ws;
  ws = null;
  old.onopen = null; old.onmessage = null; old.onerror = null; old.onclose = null;
  try { old.close(1000); } catch (e) {}
}

async function initWebSocket() {
  closeWebSocket();
  setWsStatus('connecting');
  let url;
  try { url = await wsUrlWithAuth(); }
  catch (e) {
    // Fall back to token-less handshake; server decides.
    url = WS_SCHEME + '://' + location.hostname + ':' + WS_PORT + '/ws';
  }
  try { ws = new WebSocket(url); }
  catch (e) { setWsStatus('offline'); scheduleReconnect(); return; }

  ws.onopen = () => {
    wsRetry = 0;
    setWsStatus('online');
    try { ws.send(JSON.stringify({ cmd: 'subscribe_all' })); } catch (e) {}
  };
  ws.onmessage = (e) => {
    try { handleWSMessage(JSON.parse(e.data)); } catch (err) {}
  };
  ws.onclose = (e) => {
    ws = null;
    setWsStatus('offline');
    if (e.code !== 1000) scheduleReconnect();
  };
  ws.onerror = () => { try { ws.close(); } catch (e) {} };
}

function scheduleReconnect() {
  if (wsTimer) return;
  const delay = Math.min(30000, 1000 * Math.pow(2, wsRetry++) + Math.random() * 500);
  wsTimer = setTimeout(() => { wsTimer = null; initWebSocket(); }, delay);
}

function handleWSMessage(data) {
  if (!data || typeof data !== 'object') return;
  if (data.type === 'telemetry' || data.type === 'log' || data.kind
      || data.type === 'server_enabled' || data.type === 'server_disabled'
      || data.type === 'event' || data.type === 'metric') {
    if (data.type === 'telemetry' || data.type === 'log' || data.kind) {
      pushTelemetry({
        source: data.source || data.server || data.component,
        kind: data.kind || data.level,
        msg: data.msg || data.message || data.detail
              || (data.type === 'server_enabled' ? 'server enabled'
                 : data.type === 'server_disabled' ? 'server disabled' : ''),
      });
    }
    if (data.type === 'server_enabled' || data.type === 'server_disabled') {
      loadCatalog();
      loadBackends();
      loadStatus();
    }
    if (data.type === 'event' || data.type === 'metric') {
      loadCalls();
      loadStatus();
    }
    return;
  }
  // Backwards-compat: any message with msg/kind
  if (data.msg || data.kind) pushTelemetry(data);
}

// ── Detail drawer ─────────────────────────────────────────────────────────
function detailToggle(name) {
  const server = servers.find((s) => s.name === name);
  if (!server) { loadCatalog().then(() => detailToggle(name)); return; }
  $('detail-name').textContent = server.name;
  $('detail-status').textContent = server.enabled ? 'ENABLED' : 'DISABLED';
  $('detail-badges').innerHTML = [
    tagFor(statusKind(server.status || (server.enabled ? 'running' : 'down')),
           esc(server.status || (server.enabled ? 'running' : 'down'))),
    '<span class="tag tag--muted">' + esc(server.transport) + '</span>'
  ].join(' ');
  $('detail-desc').textContent = server.description || '-';
  $('detail-env').textContent = envKeys(server).join(', ') || '(none)';
  $('detail-cmd').textContent = server.command || server.launch || '-';
  $('detail-profiles').textContent = (server.profiles || []).join(', ') || 'core';

  const hp = $('detail-homepage'), hpRow = $('detail-homepage-row');
  if (server.homepage && hp && hpRow) {
    hp.href = server.homepage; hp.textContent = server.homepage; hpRow.style.display = '';
  } else if (hpRow) { hpRow.style.display = 'none'; }

  const cRow = $('detail-connect-row');
  if (cRow) cRow.style.display = server.connection ? '' : 'none';
  const cVal = $('detail-connect');
  if (cVal) cVal.textContent = server.connection || '-';

  const panel = $('detail-panel');
  panel.classList.remove('hidden');
  panel.setAttribute('aria-hidden', 'false');
  panel.setAttribute('aria-expanded', 'true');
}
function envKeys(s) {
  const e = s.env || s.environment;
  if (!e) return [];
  if (Array.isArray(e)) return e;
  if (typeof e === 'object') return Object.keys(e);
  return String(e).split(',').map((x) => x.trim());
}
function closeDetail() {
  const panel = $('detail-panel');
  if (!panel) return;
  panel.classList.add('hidden');
  panel.setAttribute('aria-hidden', 'true');
  panel.setAttribute('aria-expanded', 'false');
}

function btnKey(e, fn) {
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fn(); }
}

// ── Confirm dialog (dangerous-action interception) ────────────────────────
let confirmCtx = null;
function confirmAction(action, name) {
  confirmCtx = {
    action: action,
    name: name,
    ok: $('confirm-ok'),
    cancel: $('confirm-cancel'),
  };
  const dlg = $('confirm');
  if (!dlg) return;
  const titles = {
    enable: 'ENABLE SERVER', disable: 'DISABLE SERVER',
    'save-credentials': 'SAVE CREDENTIALS',
  };
  const bodies = {
    enable: 'Enabling "' + (name || '') + '" opens a live tool connection. Confirm?',
    disable: 'Disabling "' + (name || '') + '" cuts an active tool connection. Confirm?',
    'save-credentials': 'Saving credentials writes secrets to storage. Confirm?',
  };
  const t = $('confirm-title'), b = $('confirm-body');
  if (t) t.textContent = titles[action] || 'CONFIRM';
  if (b) b.textContent = bodies[action] || '';
  dlg.classList.remove('hidden');
  dlg.setAttribute('aria-hidden', 'false');
  // Sharp emphasis in/out handled by CSS (.confirm-overlay state transition).
  if (Kater.motion && Kater.motion.confirmAction) Kater.motion.confirmAction(dlg);
  if (confirmCtx.ok) confirmCtx.ok.focus();
}
function closeConfirm() {
  const dlg = $('confirm');
  if (!dlg) return;
  dlg.classList.add('hidden');
  dlg.setAttribute('aria-hidden', 'true');
  confirmCtx = null;
}
function runConfirmed() {
  if (!confirmCtx) return;
  const { action, name } = confirmCtx;
  closeConfirm();
  if (action === 'enable') detailToggleEnable(name, true);
  else if (action === 'disable') detailToggleEnable(name, false);
  else if (action === 'save-credentials') saveCredentialsCore();
}
// toggleTunnel keeps its stop-confirm behavior (do not auto-fire confirm).
function toggleTunnel(btn) {
  if (btn) { event.stopPropagation(); }
  const name = (btn && btn.dataset && btn.dataset.name) || '';
  apiSend('/api/tunnel/toggle', { server: name }).then(() => {
    loadCatalog(); loadBackends();
  }).catch((e) => telegraph('tunnel toggle failed: ' + e.message, 'err'));
}
// Backing logic for enable/disable (used by confirm flow).
function detailToggleEnable(name, enabled) {
  apiSend('/api/servers/' + encodeURIComponent(name) + '/set', { enabled: enabled })
    .then(() => { loadCatalog(); loadBackends(); loadStatus(); closeDetail(); })
    .catch((e) => telegraph(
      'server ' + (enabled ? 'enable' : 'disable') + ' failed: ' + e.message,
      'err'));
}
// Confirm-trigger bindings (delegated from markup data-confirm buttons).
function initConfirmTriggers() {
  qsa('[data-confirm]').forEach((btn) => {
    onEl(btn, 'click', (e) => {
      // toggleTunnel / code-copy buttons manage their own confirmation.
      if (btn.dataset.confirm === 'tunnel') return;
      e.preventDefault();
      e.stopPropagation();
      confirmAction(btn.dataset.confirm, btn.dataset.name || '');
    });
  });
  onEl(document, 'keydown', (e) => {
    const dlg = $('confirm');
    if (!dlg || dlg.classList.contains('hidden')) return;
    if (e.key === 'Escape') closeConfirm();
    if (e.key === 'Enter' && document.activeElement === $('confirm-ok')) runConfirmed();
  });
}

// ── Server enable/disable (called from catalog confirm) ──────────────────
// #confirm-server-enable / #confirm-server-disable wire to confirmAction.
function confirmEnable(name) { confirmAction('enable', name); }
function confirmDisable(name) { confirmAction('disable', name); }

// ── Credentials modal ─────────────────────────────────────────────────────
function openCredentials() {
  const m = $('credentials-modal');
  if (m) { m.classList.remove('hidden'); m.setAttribute('aria-hidden', 'false'); }
}
function closeCredentialsModal() {
  const m = $('credentials-modal');
  if (m) { m.classList.add('hidden'); m.setAttribute('aria-hidden', 'true'); }
}
function saveCredentials() { confirmAction('save-credentials', ''); }
function saveCredentialsCore() {
  const server = ($('cred-server') && $('cred-server').value) || '';
  const env = ($('cred-env') && $('cred-env').value) || '';
  apiSend('/api/credentials/save', { server: server, env: env })
    .then(() => { telegraph('credentials saved', 'ok'); closeCredentialsModal(); })
    .catch((e) => telegraph('save failed: ' + e.message, 'err'));
}

// ── Deploy view ───────────────────────────────────────────────────────────
let deployTabs = ['claude', 'cursor', 'windsurf', 'generic'];
let deployCode = {};
function initDeployTabs() {
  qsa('.code-tab').forEach((tab) => {
    onEl(tab, 'click', () => {
      const v = tab.dataset.tab;
      qsa('.code-tab').forEach((t) => t.classList.toggle('active', t === tab));
      qsa('.code-block').forEach((b) => { b.hidden = (b.dataset.tab !== v); });
    });
  });
}
function hydrateDeploy() {
  apiGet('/api/deploy/config').then((data) => {
    deployCode = data || {};
    Object.keys(data || {}).forEach((k) => {
      const pre = document.querySelector('.code-block[data-tab="' + cls(k) + '"]');
      if (pre) {
        const txt = typeof data[k] === 'string' ? data[k] : JSON.stringify(data[k], null, 2);
        pre.textContent = txt;
      }
    });
  }).catch((e) => telegraph('deploy config failed: ' + e.message, 'err'));
}
function copyDeployCode(tab) {
  const sel = '.code-block[data-tab="' + cls(tab) + '"]';
  const pre = document.querySelector(sel) || document.querySelector('.code-block');
  if (!pre) return;
  const text = pre.textContent || '';
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => {
      const btn = $('deploy-copy');
      if (btn) {
        btn.classList.add('copied');
        if (Kater.motion && Kater.motion.statusPulse) Kater.motion.statusPulse(btn, 'ok');
        trackedTimeout(() => btn.classList.remove('copied'), 1200);
      }
    }).catch(() => telegraph('clipboard blocked by browser', 'err'));
  } else {
    telegraph('clipboard unavailable', 'err');
  }
}

// ── Settings view ─────────────────────────────────────────────────────────
function hydrateSettings() {
  apiGet('/api/settings').then((data) => {
    const d = data || {};
    setVal('set-auth-mode', d.auth_mode || d.authMode);
    setVal('set-profile', d.default_profile || d.defaultProfile);
    const cors = (d.cors_origins || d.cors || []);
    setVal('set-cors', Array.isArray(cors) ? cors.join(',') : cors);
    setVal('set-rate-limit', d.rate_limit || d.rateLimit);
    setVal('set-storage', d.storage || d.storage_backend);
  }).catch((e) => telegraph('settings load failed: ' + e.message, 'err'));
}
function setVal(id, v) { const el = $(id); if (el && v != null) el.value = v; }
function saveSettings() {
  const payload = {
    auth_mode: val('set-auth-mode'),
    default_profile: val('set-profile'),
    cors_origins: (val('set-cors') || '').split(',').map((x) => x.trim()).filter(Boolean),
    rate_limit: parseInt(val('set-rate-limit') || '0', 10),
    storage: val('set-storage'),
  };
  apiSend('/api/settings', payload, 'PUT')
    .then(() => telegraph('settings saved', 'ok'))
    .catch((e) => telegraph('settings save failed: ' + e.message, 'err'));
}
function val(id) { const el = $(id); return el ? el.value : ''; }

// ── Command box ───────────────────────────────────────────────────────────
function sendCommand() {
  const input = $('cmd-input');
  if (!input) return;
  const cmd = input.value.trim();
  if (!cmd) return;
  telegraph('> ' + cmd, 'accent');
  apiSend('/api/command', { command: cmd })
    .then((r) => telegraph('ok: ' + (r && r.result ? r.result : 'done'), 'ok'))
    .catch((e) => telegraph('err: ' + e.message, 'err'));
  input.value = '';
}
function initCommandBox() {
  const input = $('cmd-input');
  if (!input) return;
  onEl(input, 'keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); sendCommand(); } });
}

// ── Polling ───────────────────────────────────────────────────────────────
function startPolling() {
  loadStatus();
  loadBackends();
  loadCalls();
  loadCatalog();
  trackedInterval(loadStatus, 5000);
  trackedInterval(loadBackends, 4000);
  trackedInterval(loadCalls, 4000);
  trackedInterval(loadCatalog, 10000);
}

function loadAll() {
  startPolling();
}

// ── Teardown ──────────────────────────────────────────────────────────────
function teardown() {
  timers.forEach((id) => { clearInterval(id); clearTimeout(id); });
  timers.clear();
  listeners.forEach(([t, type, fn]) => { try { t.removeEventListener(type, fn); } catch (e) {} });
  listeners.length = 0;
  controllers.forEach((c) => { try { c.abort(); } catch (e) {} });
  controllers.clear();
  closeWebSocket();
}

// ── Init ──────────────────────────────────────────────────────────────────
function init() {
  initTabNavigation();
  initConfirmTriggers();
  initDeployTabs();
  initCommandBox();

  const hash = (location.hash || '').replace('#', '');
  // Initial load: no entrance motion.
  if (hash && viewIds.indexOf(hash) !== -1) switchView(hash, { focusTab: true, silent: true });
  else switchView('dashboard', { silent: true });

  const oauthBtn = $('auth-oauth-btn');
  if (oauthBtn) onEl(oauthBtn, 'click', beginOAuth);
  const keyBtn = $('auth-key-btn');
  if (keyBtn) onEl(keyBtn, 'click', () => {
    const v = ($('auth-key-input') && $('auth-key-input').value) || '';
    if (v) localStorage.setItem(AUTH_STORAGE, v);
    connectSelected();
  });

  const search = $('catalog-search');
  if (search) onEl(search, 'input', () => {
    if (catalogSearchTimer) clearTimeout(catalogSearchTimer);
    catalogSearchTimer = setTimeout(() => { catalogQuery = search.value; filterCatalog(); }, 120);
  });

  setBoot('ESTABLISHING UPLINK…');
  trackedTimeout(() => setBoot('', true), 450);

  connectSelected();
  appReady = true;

  window.addEventListener('beforeunload', teardown);
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
        '<meta name="color-scheme" content="light">\n'
        '<meta name="theme-color" content="#F4F3EF">\n'
        f"<style>{_CSS}</style>\n"
        "</head>\n<body>\n"
        f"{_HTML}\n"
        f"{config}"
        f"<script>{_JS}</script>\n"
        "</body>\n</html>\n"
    )
