from __future__ import annotations

_CSS = r"""
:root {
  /* Amber-console palette: neutral graphite + a single amber signal.
     Status colors (jade/coral/ice) carry meaning, never decoration. */
  --bg: #0a0b0e;
  --bg2: #0f1116;
  --surface: rgba(20, 22, 28, 0.72);
  --surface-solid: #14161c;
  --border: rgba(255, 255, 255, 0.07);
  --border-bright: rgba(255, 255, 255, 0.17);
  --text: #e7e9ee;
  --text-dim: #8b919e;
  --text-bright: #f6f7f9;
  --accent: #ffb224;
  --accent-soft: #f59e0b;
  --accent-glow: rgba(255, 178, 36, 0.16);
  --green: #3fb950;
  --green-glow: rgba(63, 185, 80, 0.14);
  --cyan: #5cc8e0;
  --cyan-glow: rgba(92, 200, 224, 0.12);
  --red: #f76d5e;
  /* Legacy alias: any stray purple usage stays on-brand amber. */
  --purple: #ffb224;
  --s1: 4px; --s2: 8px; --s3: 12px; --s4: 16px; --s5: 24px; --s6: 32px;
  --radius: 14px;
  --radius-sm: 9px;
  --font: ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  --mono: 'JetBrains Mono', 'SF Mono', ui-monospace, 'Cascadia Code', 'Consolas', monospace;
  --shadow: 0 10px 34px rgba(0, 0, 0, 0.5);
  --transition: 170ms cubic-bezier(0.4, 0, 0.2, 1);
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

::selection { background: var(--accent-glow); color: var(--text-bright); }

/* Quality floor: every interactive element shows a visible amber focus ring. */
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
  position: fixed; left: 12px; top: 8px; z-index: 999;
  width: auto; height: auto; margin: 0; padding: 8px 16px;
  clip: auto; overflow: visible; white-space: nowrap;
  background: var(--accent); color: #000; border-radius: 6px;
  font-family: var(--mono); font-size: 13px; text-decoration: none;
}

/* Respect reduced-motion: kill ambient animation and transitions. */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
  }
}

#bg-gradient {
  position: fixed; inset: 0; z-index: 0;
  background:
    radial-gradient(ellipse 900px 640px at 18% 20%, rgba(255,178,36,0.05), transparent 60%),
    radial-gradient(ellipse 700px 820px at 84% 78%, rgba(92,200,224,0.035), transparent 60%),
    var(--bg);
}
/* Faint engineering grid — the console sits on a measured surface. */
#bg-gradient::before {
  content: ''; position: absolute; inset: 0; opacity: 0.4;
  background-image:
    linear-gradient(rgba(255,255,255,0.018) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.018) 1px, transparent 1px);
  background-size: 38px 38px;
  -webkit-mask-image: radial-gradient(ellipse 80% 80% at 50% 40%, #000 30%, transparent 80%);
  mask-image: radial-gradient(ellipse 80% 80% at 50% 40%, #000 30%, transparent 80%);
}

/* ── Boot ──────────────────────────────── */
#boot {
  position: fixed; inset: 0; z-index: 100;
  background: var(--bg);
  display: flex; align-items: center; justify-content: center;
  font-family: var(--mono); font-size: 13px; color: var(--text-dim);
}
#boot.done { opacity: 0; pointer-events: none; transition: opacity 400ms; }
#boot .boot-text { white-space: pre; line-height: 1.8; }
#boot .boot-text .ok { color: var(--green); }
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
  padding: 0 20px; height: 52px; min-height: 52px;
  border-bottom: 1px solid var(--border);
  background: rgba(10, 14, 20, 0.8);
  backdrop-filter: blur(12px);
}
.topbar-left { display: flex; align-items: center; gap: 16px; }
.brand {
  font-family: var(--mono); font-weight: 700; font-size: 15px;
  letter-spacing: 2px; color: var(--text-bright);
  display: flex; align-items: center; gap: 10px;
}
.brand-dot {
  width: 9px; height: 9px; border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 0 0 var(--accent-glow), 0 0 14px var(--accent);
  animation: reactor 2.6s ease-in-out infinite;
}
@keyframes reactor {
  0%, 100% { box-shadow: 0 0 0 0 rgba(255,178,36,0.45), 0 0 14px var(--accent); }
  50% { box-shadow: 0 0 0 6px rgba(255,178,36,0), 0 0 18px var(--accent); }
}
.version-tag {
  font-family: var(--mono); font-size: 11px; color: var(--text-dim);
  padding: 2px 8px; border-radius: 999px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.02);
}
.profile-pills {
  display: flex; gap: 4px; flex-wrap: wrap;
}
.pill {
  font-family: var(--mono); font-size: 11px;
  padding: 4px 10px; border-radius: 20px;
  border: 1px solid var(--border); color: var(--text-dim);
  cursor: pointer; transition: var(--transition); user-select: none;
}
.pill:hover { color: var(--text); border-color: var(--border-bright); }
.pill.active {
  background: var(--accent); color: #000; border-color: var(--accent);
  box-shadow: 0 0 16px var(--accent-glow);
}
.topbar-right { display: flex; align-items: center; gap: 12px; }
.auth-badge {
  font-family: var(--mono); font-size: 11px; color: var(--text-dim);
  display: flex; align-items: center; gap: 6px;
}
.auth-dot {
  width: 6px; height: 6px; border-radius: 50%; background: var(--green);
}

/* ── Bento Grid ────────────────────────── */
.bento {
  flex: 1; display: grid;
  grid-template-columns: 1fr 340px;
  grid-template-rows: 1fr auto;
  gap: 12px; padding: 12px;
  overflow: hidden;
}
.tile {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  backdrop-filter: blur(12px);
  display: flex; flex-direction: column;
  overflow: hidden;
}
.tile-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px; min-height: 36px;
  border-bottom: 1px solid var(--border);
}
.tile-title {
  font-family: var(--mono); font-size: 11px; font-weight: 600;
  letter-spacing: 1px; text-transform: uppercase; color: var(--text-dim);
}

/* ── Constellation Tile ────────────────── */
.constellation-tile {
  grid-column: 1; grid-row: 1;
}
#constellation-canvas {
  flex: 1; width: 100%; cursor: pointer;
}

/* ── Telemetry Tile ────────────────────── */
.telemetry-tile {
  grid-column: 2; grid-row: 1;
}
.telemetry-stream {
  flex: 1; overflow-y: auto;
  font-family: var(--mono); font-size: 11px;
  padding: 8px 12px;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}
.telemetry-stream::-webkit-scrollbar { width: 4px; }
.telemetry-stream::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
.tlm-row {
  display: flex; align-items: center; gap: 8px;
  padding: 3px 0; opacity: 1; transition: opacity 600ms;
  white-space: nowrap;
}
.tlm-row.faded { opacity: 0.4; }
.tlm-time { color: var(--text-dim); flex-shrink: 0; }
.tlm-icon { flex-shrink: 0; width: 14px; text-align: center; }
.tlm-icon.ok { color: var(--green); }
.tlm-icon.err { color: var(--red); }
.tlm-name { color: var(--text); overflow: hidden; text-overflow: ellipsis; }
.tlm-ms { color: var(--text-dim); margin-left: auto; flex-shrink: 0; }

/* ── Stats / Tunnel / Auth Tiles ───────── */
.stats-row {
  grid-column: 1 / -1; grid-row: 2;
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;
}
.mini-tile {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  backdrop-filter: blur(12px);
  padding: 14px 16px;
}
.mini-label {
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  letter-spacing: 1px; text-transform: uppercase; color: var(--text-dim);
  margin-bottom: 6px;
}
.mini-content { display: flex; align-items: baseline; gap: 16px; }
.big-num {
  font-family: var(--mono); font-size: 28px; font-weight: 700;
  color: var(--text-bright); line-height: 1;
}
.big-sub {
  font-family: var(--mono); font-size: 12px; color: var(--text-dim);
}
.btn-tunnel {
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  letter-spacing: 0.5px; text-transform: uppercase;
  padding: 4px 10px; border-radius: 6px; cursor: pointer;
  border: 1px solid var(--accent); color: var(--accent);
  background: transparent; transition: var(--transition);
}
.btn-tunnel:hover { background: var(--accent); color: #000; }
.btn-tunnel.active { background: var(--green); border-color: var(--green); color: #000; }
.tunnel-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 4px 0;
}
.tunnel-name { font-family: var(--mono); font-size: 12px; color: var(--text); }

/* ── Command Bar ───────────────────────── */
.command-bar {
  height: 40px; min-height: 40px;
  display: flex; align-items: center;
  padding: 0 16px; gap: 8px;
  background: rgba(10, 14, 20, 0.9);
  border-top: 1px solid var(--border);
  backdrop-filter: blur(12px);
}
.cmd-prompt {
  font-family: var(--mono); font-weight: 700; color: var(--accent);
}
#cmd-input {
  flex: 1; background: transparent; border: none; outline: none;
  font-family: var(--mono); font-size: 13px; color: var(--text);
}
#cmd-input::placeholder { color: var(--text-dim); }
.cmd-hint {
  font-family: var(--mono); font-size: 10px; color: var(--text-dim);
  padding: 2px 6px; border-radius: 4px; border: 1px solid var(--border);
}

/* ── Detail Panel ──────────────────────── */
.detail-panel {
  position: fixed; top: 90px; right: 0; bottom: 40px;
  width: 320px; z-index: 50;
  background: var(--surface-solid);
  border-left: 1px solid var(--border-bright);
  box-shadow: -8px 0 32px rgba(0,0,0,0.3);
  transform: translateX(100%);
  transition: transform 300ms cubic-bezier(0.4, 0, 0.2, 1);
  display: flex; flex-direction: column;
  overflow-y: auto;
}
.detail-panel.open { transform: translateX(0); }
.detail-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px; border-bottom: 1px solid var(--border);
}
.detail-name {
  font-family: var(--mono); font-size: 16px; font-weight: 700;
  color: var(--text-bright);
}
.detail-close {
  cursor: pointer; color: var(--text-dim); font-size: 18px;
  width: 28px; height: 28px; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  transition: var(--transition);
}
.detail-close:hover { color: var(--red); background: rgba(247,109,94,0.12); }
.detail-section {
  padding: 14px 16px; border-bottom: 1px solid var(--border);
}
.detail-label {
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  letter-spacing: 1px; text-transform: uppercase; color: var(--text-dim);
  margin-bottom: 8px;
}
.detail-value {
  font-family: var(--mono); font-size: 12px; color: var(--text);
  word-break: break-all;
}
.detail-link {
  font-family: var(--mono); font-size: 12px; color: var(--accent);
  text-decoration: none; word-break: break-all;
}
.detail-link:hover { text-decoration: underline; }
.detail-status {
  display: inline-flex; align-items: center; gap: 8px;
  font-family: var(--mono); font-size: 12px; color: var(--text);
}
.detail-status::before {
  content: ''; width: 8px; height: 8px; border-radius: 50%;
  background: var(--text-dim); flex-shrink: 0;
}
.detail-status.ready { color: var(--green); }
.detail-status.ready::before { background: var(--green); box-shadow: 0 0 10px var(--green); }
.detail-status.needs { color: var(--accent); }
.detail-status.needs::before { background: var(--accent); box-shadow: 0 0 10px var(--accent); }
.detail-status.off { color: var(--text-dim); }
.badges { display: flex; gap: 6px; flex-wrap: wrap; }
.badge {
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  padding: 2px 8px; border-radius: 4px; text-transform: uppercase;
}
.badge.stdio { background: var(--green-glow); color: var(--green); }
.badge.sse, .badge.http { background: var(--cyan-glow); color: var(--cyan); }
.badge.native { background: var(--accent-glow); color: var(--accent); }
.badge.high { background: rgba(247,109,94,0.13); color: var(--red); }
.badge.medium { background: rgba(255,178,36,0.14); color: var(--accent); }
.badge.low { background: var(--green-glow); color: var(--green); }
.detail-actions {
  padding: 16px; display: flex; gap: 8px;
}
.btn-action {
  flex: 1; font-family: var(--mono); font-size: 12px; font-weight: 600;
  padding: 8px; border-radius: var(--radius-sm); cursor: pointer;
  border: 1px solid var(--border); background: transparent; color: var(--text);
  transition: var(--transition); text-transform: uppercase; letter-spacing: 0.5px;
}
.btn-action:hover { border-color: var(--border-bright); background: rgba(255,255,255,0.03); }
.btn-action.primary { background: var(--green); border-color: var(--green); color: #000; }
.btn-action.danger { background: var(--red); border-color: var(--red); color: #fff; }

/* ── Toast ─────────────────────────────── */
.toast-container {
  position: fixed; bottom: 52px; left: 50%;
  transform: translateX(-50%); z-index: 200;
  display: flex; flex-direction: column; gap: 8px; align-items: center;
}
.toast {
  font-family: var(--mono); font-size: 12px;
  padding: 8px 16px; border-radius: 8px;
  background: var(--surface-solid); border: 1px solid var(--border-bright);
  box-shadow: var(--shadow);
  animation: toast-in 200ms ease-out, toast-out 200ms ease-in 2.5s forwards;
}
.toast.success { border-color: var(--green); }
.toast.error { border-color: var(--red); }
@keyframes toast-in { from { opacity: 0; transform: translateY(8px); } }
@keyframes toast-out { to { opacity: 0; transform: translateY(8px); } }

/* ── Nav Tabs ─────────────────────────── */
.nav-tabs {
  display: flex; gap: 0; padding: 0 12px; align-items: stretch;
  background: rgba(10, 14, 20, 0.8);
  border-bottom: 1px solid var(--border);
  backdrop-filter: blur(12px); min-height: 38px;
  overflow-x: auto;
}
.tab {
  font-family: var(--mono); font-size: 11px; font-weight: 600;
  letter-spacing: 1px; text-transform: uppercase; color: var(--text-dim);
  padding: 0 14px; cursor: pointer; border: none; background: transparent;
  display: flex; align-items: center; position: relative;
  transition: var(--transition); white-space: nowrap;
}
.tab:hover { color: var(--text); }
.tab.active { color: var(--text-bright); }
.tab.active::after {
  content: ''; position: absolute; bottom: 0; left: 14px; right: 14px;
  height: 2px; background: var(--accent); border-radius: 2px 2px 0 0;
}
.tab .tab-num {
  font-size: 9px; color: var(--text-dim); margin-left: 6px;
  opacity: 0.6; font-weight: 400;
}

/* ── Views ────────────────────────────── */
.view { display: none; flex: 1; overflow: hidden; }
.view.active { display: flex; flex-direction: column; }
.view-scroll {
  flex: 1; overflow-y: auto;
  scrollbar-width: thin; scrollbar-color: var(--border) transparent;
}
.view-scroll::-webkit-scrollbar { width: 6px; }
.view-scroll::-webkit-scrollbar-thumb {
  background: var(--border); border-radius: 3px;
}
.view-header {
  padding: 12px 16px; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
  min-height: 38px;
}
.view-title {
  font-family: var(--mono); font-size: 13px; font-weight: 700;
  color: var(--text-bright);
}
.view-empty {
  padding: 48px 20px; text-align: center;
  font-family: var(--mono); font-size: 12px; color: var(--text-dim);
}
.catalog-toolbar {
  padding: 10px 12px 0;
  position: sticky; top: 0; z-index: 2;
  background: linear-gradient(var(--bg) 70%, transparent);
}
#catalog-search {
  width: 100%; max-width: 420px;
}

/* ── Server Grid (Catalog) ────────────── */
.server-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px; padding: 12px;
}
.server-card {
  position: relative;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 14px; cursor: pointer;
  transition: var(--transition); backdrop-filter: blur(12px);
  overflow: hidden;
}
.server-card::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 2px;
  background: var(--accent); opacity: 0;
  transition: opacity var(--transition);
}
.server-card:hover {
  border-color: var(--border-bright); transform: translateY(-2px);
  box-shadow: var(--shadow);
}
.server-card:hover::before { opacity: 0.9; }
.server-card-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 8px; gap: 8px;
}
.server-card-name {
  font-family: var(--mono); font-size: 13px; font-weight: 700;
  color: var(--text-bright);
  overflow: hidden; text-overflow: ellipsis;
}
.server-card-desc {
  font-size: 12px; color: var(--text-dim); line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; overflow: hidden;
}
.toggle-switch {
  width: 36px; height: 20px; border-radius: 10px;
  background: var(--border); position: relative; cursor: pointer;
  transition: var(--transition); flex-shrink: 0;
}
.toggle-switch::after {
  content: ''; position: absolute; top: 2px; left: 2px;
  width: 16px; height: 16px; border-radius: 50%;
  background: var(--text-dim); transition: var(--transition);
}
.toggle-switch.on { background: var(--green); }
.toggle-switch.on::after { left: 18px; background: #fff; }
/* Mid-stage: switched on, but missing credentials — not actually connected. */
.toggle-switch.pending { background: var(--accent-soft); }
.toggle-switch.pending::after {
  left: 18px; background: #000;
  animation: toggle-pulse 1.6s ease-in-out infinite;
}
@keyframes toggle-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

/* ── Eval Table ───────────────────────── */
.eval-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.eval-table th {
  text-align: left; padding: 10px 12px;
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  letter-spacing: 1px; text-transform: uppercase; color: var(--text-dim);
  border-bottom: 1px solid var(--border);
  position: sticky; top: 0; background: var(--surface-solid);
}
.eval-table td {
  padding: 10px 12px; border-bottom: 1px solid var(--border);
  font-family: var(--mono); color: var(--text);
}
.eval-table tr:hover td { background: rgba(255,255,255,0.02); }
.success-bar {
  display: inline-block; width: 60px; height: 6px;
  background: var(--border); border-radius: 3px; overflow: hidden;
  vertical-align: middle; margin-right: 8px;
}
.success-bar-fill { height: 100%; border-radius: 3px; display: block; }
.eval-summary {
  display: flex; gap: 24px; padding: 14px 16px; flex-wrap: wrap;
  border-bottom: 1px solid var(--border);
}
.eval-stat {
  font-family: var(--mono); font-size: 12px; color: var(--text-dim);
}
.eval-stat .big-num { font-size: 20px; }

/* ── Code Preview (Deploy) ────────────── */
.code-tabs {
  display: flex; gap: 4px; padding: 12px 12px 0; flex-wrap: wrap;
}
.code-tab {
  font-family: var(--mono); font-size: 11px; font-weight: 600;
  padding: 6px 12px; border-radius: 6px; cursor: pointer;
  border: 1px solid var(--border); background: transparent;
  color: var(--text-dim); transition: var(--transition);
}
.code-tab:hover { color: var(--text); border-color: var(--border-bright); }
.code-tab.active {
  background: var(--accent); color: #000; border-color: var(--accent);
}
.code-preview { padding: 0 12px 12px; }
.code-desc {
  font-family: var(--mono); font-size: 12px; color: var(--text-dim);
  padding: 8px 0 0;
}
.code-wrap { position: relative; margin-top: 12px; }
.code-block {
  margin: 0; padding: 14px;
  background: var(--bg2); border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-family: var(--mono); font-size: 12px; color: var(--text);
  white-space: pre; overflow-x: auto; max-height: 55vh;
  scrollbar-width: thin; scrollbar-color: var(--border) transparent;
}
.code-block::-webkit-scrollbar { height: 6px; width: 6px; }
.code-block::-webkit-scrollbar-thumb {
  background: var(--border); border-radius: 3px;
}
.code-copy {
  position: absolute; top: 10px; right: 10px; z-index: 2;
  font-family: var(--mono); font-size: 10px; text-transform: uppercase;
  padding: 4px 10px; border-radius: 4px; cursor: pointer;
  border: 1px solid var(--border); background: var(--surface-solid);
  color: var(--text-dim); transition: var(--transition);
}
.code-copy:hover { color: var(--text); border-color: var(--border-bright); }

/* ── Settings Form ────────────────────── */
.settings-form { padding: 16px; max-width: 560px; }
.form-field { margin-bottom: 18px; }
.form-label {
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  letter-spacing: 1px; text-transform: uppercase; color: var(--text-dim);
  display: block; margin-bottom: 6px;
}
.form-input, .form-select {
  width: 100%; padding: 8px 12px;
  background: var(--bg2); border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-family: var(--mono); font-size: 13px; color: var(--text);
  outline: none; transition: var(--transition);
}
.form-input:focus, .form-select:focus { border-color: var(--accent); }
.btn-save {
  font-family: var(--mono); font-size: 12px; font-weight: 600;
  padding: 8px 20px; border-radius: var(--radius-sm); cursor: pointer;
  border: 1px solid var(--accent); background: var(--accent); color: #000;
  text-transform: uppercase; letter-spacing: 0.5px;
  transition: var(--transition);
}
  .btn-save:hover { opacity: 0.85; }

/* ── Modal (credentials) ───────────────── */
.modal-overlay {
  position: fixed; inset: 0; z-index: 130;
  display: none; align-items: center; justify-content: center;
  background: rgba(8, 9, 12, 0.74);
  backdrop-filter: blur(8px);
  padding: 20px;
}
.modal-overlay.show { display: flex; animation: toast-in 160ms ease-out; }
.modal-card {
  width: min(460px, 96vw);
  background: var(--surface-solid);
  border: 1px solid var(--border-bright);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 22px;
}
.modal-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 6px;
}
.modal-title {
  font-family: var(--mono); font-size: 15px; font-weight: 700;
  letter-spacing: 0.5px; color: var(--text-bright);
}
.modal-sub {
  color: var(--text-dim); font-size: 13px; line-height: 1.5;
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
  position: fixed; inset: 0; z-index: 120;
  display: none; align-items: center; justify-content: center;
  background: rgba(10, 14, 20, 0.92);
  backdrop-filter: blur(8px);
}
#auth-gate.show { display: flex; }
.auth-card {
  width: min(420px, 92vw);
  background: var(--surface-solid);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 28px;
  box-shadow: var(--shadow);
}
.auth-card h2 {
  font-size: 18px; color: var(--text-bright); margin-bottom: 8px;
}
.auth-card p { color: var(--text-dim); margin-bottom: 20px; font-size: 13px; }
.auth-card input {
  width: 100%; padding: 10px 12px; margin-bottom: 12px;
  background: var(--bg2); border: 1px solid var(--border);
  border-radius: var(--radius-sm); color: var(--text);
  font-family: var(--mono); font-size: 13px;
}
.auth-actions { display: flex; gap: 10px; flex-wrap: wrap; }

/* ── Responsive ────────────────────────── */
@media (max-width: 768px) {
  .bento { grid-template-columns: 1fr; grid-template-rows: 1fr 200px auto; }
  .constellation-tile { grid-column: 1; }
  .telemetry-tile { grid-column: 1; grid-row: 2; }
  .stats-row { grid-column: 1; grid-row: 3; grid-template-columns: 1fr; }
  .profile-pills { display: none; }
  .detail-panel { width: 100%; }
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
      <span class="tile-title" id="catalog-count">0 servers</span>
    </div>
    <div class="view-scroll">
      <div class="catalog-toolbar">
        <input class="form-input" id="catalog-search" type="search"
          placeholder="Zoek servers (bijv. search, github)..." autocomplete="off"
          aria-label="Search servers">
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
          <button class="code-copy" onclick="copyDeployCode()"
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
          <label class="form-label">Auth Mode</label>
          <select class="form-select" id="set-auth-mode">
            <option value="none">none</option>
            <option value="apikey">apikey</option>
            <option value="oauth">oauth</option>
          </select>
        </div>
        <div class="form-field">
          <label class="form-label">Default Profile</label>
          <input class="form-input" id="set-profile" type="text" />
        </div>
        <div class="form-field">
          <label class="form-label">CORS Origins (comma-separated)</label>
          <input class="form-input" id="set-cors" type="text" />
        </div>
        <div class="form-field">
          <label class="form-label">Rate Limit / min (0 = off)</label>
          <input class="form-input" id="set-rate-limit" type="number"
            min="0" />
        </div>
        <div class="form-field">
          <label class="form-label">Storage Backend</label>
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
      placeholder="type a command... (toggle github, profile ops)"
      autocomplete="off" />
    <span class="cmd-hint">tab</span>
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
const MONO_FONT = "'JetBrains Mono','SF Mono',ui-monospace,'Cascadia Code','Consolas',monospace";
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
let particles = [];
let animFrame = null;

const transportColors = {
  stdio: '#3fb950', sse: '#5cc8e0', http: '#5cc8e0',
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

// ── Boot Sequence ──────────────────────
async function bootSequence() {
  const el = document.getElementById('boot-text');
  const lines = [
    { t: 'initializing kater...', d: 200 },
    { t: 'loading catalog...', d: 250 },
    { t: 'connecting backends...', d: 300 },
    { t: '', d: 100 },
  ];
  el.innerHTML = '';
  for (const line of lines) {
    const div = document.createElement('div');
    const prompt = document.createElement('span');
    prompt.textContent = '> ';
    div.appendChild(prompt);
    if (line.t) {
      const a = document.createElement('span');
      a.className = 'accent';
      a.textContent = line.t;
      div.appendChild(a);
    }
    el.appendChild(div);
    await sleep(line.d);
  }
  let version = '';
  try { version = (await api('/api/status')).version || ''; } catch (e) {
    if (e instanceof ApiError && e.status === 401) throw e;
  }
  const ready = document.createElement('div');
  ready.className = 'ok';
  ready.textContent = 'kater ready' + (version ? '. v' + version : '');
  el.appendChild(ready);
  await sleep(300);
  const boot = document.getElementById('boot');
  boot.classList.add('done');
  setTimeout(() => { boot.style.display = 'none'; }, 500);
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
    pill.className = 'pill' + (p === activeProfile ? ' active' : '');
    pill.textContent = p;
    pill.dataset.profile = p;
    pill.setAttribute('tabindex', '0');
    pill.setAttribute('role', 'button');
    el.appendChild(pill);
  }
}

function switchProfile(p) {
  if (profiles.indexOf(p) === -1) { toast('unknown profile: ' + p, 'error'); return; }
  activeProfile = p;
  document.querySelectorAll('.pill').forEach(el => {
    el.classList.toggle('active', el.dataset.profile === p);
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
    data.auth_mode === 'none' ? '#3fb950' : '#ffb224';
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
      pulse: 0,
    });
  });
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
  hoveredNode = null;
  for (const n of nodes) {
    const dx = x - n.x, dy = y - n.y;
    if (dx * dx + dy * dy < (n.r + 8) * (n.r + 8)) {
      hoveredNode = n;
      canvas.style.cursor = 'pointer';
      return;
    }
  }
  canvas.style.cursor = 'default';
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

function drawConstellation() {
  if (!ctx || !canvas) return;
  const rect = canvas.getBoundingClientRect();
  const w = rect.width, h = rect.height;
  const cx = w / 2, cy = h / 2;

  ctx.clearRect(0, 0, w, h);

  const time = Date.now() / 1000;
  const pulse = 0.5 + 0.5 * Math.sin(time * 1.5);

  const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, 60);
  grad.addColorStop(0, 'rgba(255,178,36,0.15)');
  grad.addColorStop(1, 'rgba(255,178,36,0)');
  ctx.fillStyle = grad;
  ctx.fillRect(cx - 60, cy - 60, 120, 120);

  for (const n of nodes) {
    const color = transportColors[n.transport] || '#565d6a';
    const isActive = n.enabled && n.env_configured;
    const isHovered = n === hoveredNode;

    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(n.x, n.y);

    if (isActive) {
      ctx.strokeStyle = color + '44';
      ctx.lineWidth = isHovered ? 2 : 1.5;
    } else {
      ctx.strokeStyle = 'rgba(255,255,255,0.08)';
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 4]);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    if (isActive && Math.random() < 0.02) {
      particles.push({
        x: n.x, y: n.y, tx: cx, ty: cy,
        color: color, life: 1.0, speed: 0.01 + Math.random() * 0.01,
      });
    }
  }

  particles = particles.filter(p => p.life > 0);
  for (const p of particles) {
    p.life -= 0.015;
    const t = 1 - p.life;
    p.x = p.x + (p.tx - p.x) * p.speed;
    p.y = p.y + (p.tx - p.y) * p.speed;
    ctx.beginPath();
    ctx.arc(p.x, p.y, 2, 0, Math.PI * 2);
    // Clamp alpha: life can dip below 0 before the filter catches it, which
    // would produce a negative hex ("-1") and an invalid fillStyle.
    const alpha = Math.max(0, Math.min(255, Math.floor(p.life * 200)));
    ctx.fillStyle = p.color + alpha.toString(16).padStart(2, '0');
    ctx.fill();
  }

  for (const n of nodes) {
    const color = transportColors[n.transport] || '#565d6a';
    const isActive = n.enabled && n.env_configured;
    const isHovered = n === hoveredNode;
    const r = isHovered ? n.r + 3 : n.r;

    if (isActive) {
      const g = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, r * 2);
      g.addColorStop(0, color + '22');
      g.addColorStop(1, color + '00');
      ctx.fillStyle = g;
      ctx.fillRect(n.x - r * 2, n.y - r * 2, r * 4, r * 4);
    }

    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    if (isActive) {
      ctx.fillStyle = color + '22';
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
    } else {
      ctx.fillStyle = 'rgba(20,22,28,0.85)';
      ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,0.12)';
      ctx.lineWidth = 1.5;
    }
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(n.x, n.y, 4, 0, Math.PI * 2);
    ctx.fillStyle = isActive ? color : '#565d6a';
    ctx.fill();

    ctx.font = '11px ' + MONO_FONT;
    ctx.textAlign = 'center';
    ctx.fillStyle = isHovered ? '#f6f7f9' : isActive ? '#e7e9ee' : '#565d6a';
    ctx.fillText(n.name, n.x, n.y + r + 14);
  }

  ctx.beginPath();
  ctx.arc(cx, cy, 22 + pulse * 3, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(255,178,36,0.08)';
  ctx.fill();

  ctx.beginPath();
  ctx.arc(cx, cy, 16, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(255,178,36,0.22)';
  ctx.fill();
  ctx.strokeStyle = '#ffb224';
  ctx.lineWidth = 2;
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(cx, cy, 6, 0, Math.PI * 2);
  ctx.fillStyle = '#ffb224';
  ctx.fill();

  ctx.font = 'bold 12px ' + MONO_FONT;
  ctx.textAlign = 'center';
  ctx.fillStyle = '#ffb224';
  ctx.fillText('KATER', cx, cy + 36);
}

function startAnimationLoop() {
  function loop() {
    drawConstellation();
    animFrame = requestAnimationFrame(loop);
  }
  loop();
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
      val.style.color = configured ? '#3fb950' : '#f76d5e';
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

function initWebSocket() {
  closeWebSocket();
  try {
    ws = new WebSocket(wsUrlWithAuth());
  } catch (e) {
    scheduleReconnect();
    return;
  }
  ws.onopen = () => {
    wsRetry = 0;
    // subscribe_all so we receive every broadcast without a `type` filter
    // (the previous {cmd:'subscribe'} was missing the required type field).
    try { ws.send(JSON.stringify({ cmd: 'subscribe_all' })); } catch (e) {}
  };
  ws.onmessage = (e) => {
    try { handleWSMessage(JSON.parse(e.data)); } catch (err) {}
  };
  ws.onclose = (e) => {
    ws = null;
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
    empty.textContent = catalogQuery
      ? 'No servers match "' + catalogQuery + '". Clear the search to see all.'
      : 'No servers in this profile. Switch profiles in the top bar.';
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
    const color = rate >= 90 ? '#3fb950' : rate >= 50 ? '#ffb224' : '#f76d5e';
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

function copyDeployCode() {
  const text = document.getElementById('deploy-code').textContent || '';
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(
      () => toast('copied to clipboard', 'success'),
      () => toast('clipboard access denied', 'error')
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
