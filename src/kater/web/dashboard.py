from __future__ import annotations

_CSS = r"""
:root {
  --bg: #0a0e14;
  --bg2: #0d1320;
  --surface: rgba(18, 24, 38, 0.72);
  --surface-solid: #121826;
  --border: rgba(48, 60, 82, 0.6);
  --border-bright: rgba(80, 100, 140, 0.4);
  --text: #e2e8f0;
  --text-dim: #64748b;
  --text-bright: #f1f5f9;
  --accent: #f59e0b;
  --accent-glow: rgba(245, 158, 11, 0.15);
  --green: #22c55e;
  --green-glow: rgba(34, 197, 94, 0.12);
  --cyan: #06b6d4;
  --cyan-glow: rgba(6, 182, 212, 0.12);
  --red: #ef4444;
  --purple: #a855f7;
  --radius: 12px;
  --radius-sm: 8px;
  --font: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  --mono: 'SF Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
  --shadow: 0 4px 24px rgba(0,0,0,0.4);
  --transition: 200ms cubic-bezier(0.4, 0, 0.2, 1);
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
}

#bg-gradient {
  position: fixed; inset: 0; z-index: 0;
  background:
    radial-gradient(ellipse 800px 600px at 20% 30%, rgba(245,158,11,0.04), transparent),
    radial-gradient(ellipse 600px 800px at 80% 70%, rgba(6,182,212,0.03), transparent),
    var(--bg);
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
  letter-spacing: 1px; color: var(--text-bright);
  display: flex; align-items: center; gap: 8px;
}
.brand-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--accent); box-shadow: 0 0 12px var(--accent);
}
.version-tag {
  font-family: var(--mono); font-size: 11px; color: var(--text-dim);
  padding: 2px 8px; border-radius: 4px; background: rgba(255,255,255,0.04);
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
.detail-close:hover { color: var(--red); background: rgba(239,68,68,0.1); }
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
.badges { display: flex; gap: 6px; flex-wrap: wrap; }
.badge {
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  padding: 2px 8px; border-radius: 4px; text-transform: uppercase;
}
.badge.stdio { background: var(--green-glow); color: var(--green); }
.badge.sse, .badge.http { background: var(--cyan-glow); color: var(--cyan); }
.badge.native { background: var(--accent-glow); color: var(--accent); }
.badge.high { background: rgba(239,68,68,0.12); color: var(--red); }
.badge.medium { background: rgba(245,158,11,0.12); color: var(--accent); }
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

/* ── Server Grid (Catalog) ────────────── */
.server-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px; padding: 12px;
}
.server-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 14px; cursor: pointer;
  transition: var(--transition); backdrop-filter: blur(12px);
}
.server-card:hover {
  border-color: var(--border-bright); transform: translateY(-1px);
}
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

<div id="app">
  <div class="topbar">
    <div class="topbar-left">
      <div class="brand">
        <div class="brand-dot"></div>
        KATER
        <span class="version-tag" id="version-tag">v0.0.0</span>
      </div>
      <div class="profile-pills" id="profile-pills"></div>
    </div>
    <div class="topbar-right">
      <div class="auth-badge">
        <div class="auth-dot" id="auth-dot"></div>
        <span id="auth-mode">none</span>
      </div>
    </div>
  </div>

  <div class="nav-tabs">
    <button class="tab active" data-view="dashboard"
      onclick="switchView('dashboard')">Dashboard
      <span class="tab-num">1</span></button>
    <button class="tab" data-view="catalog"
      onclick="switchView('catalog')">Catalog
      <span class="tab-num">2</span></button>
    <button class="tab" data-view="evals"
      onclick="switchView('evals')">Evals
      <span class="tab-num">3</span></button>
    <button class="tab" data-view="deploy"
      onclick="switchView('deploy')">Deploy
      <span class="tab-num">4</span></button>
    <button class="tab" data-view="settings"
      onclick="switchView('settings')">Settings
      <span class="tab-num">5</span></button>
  </div>
"""

_VIEW_DASHBOARD = r"""
  <div class="view active" id="view-dashboard">
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
  <div class="view" id="view-catalog">
    <div class="view-header">
      <span class="view-title">Server Catalog</span>
      <span class="tile-title" id="catalog-count">0 servers</span>
    </div>
    <div class="view-scroll">
      <div class="server-grid" id="catalog-grid">
        <div class="view-empty">Loading catalog...</div>
      </div>
    </div>
  </div>
"""

_VIEW_EVALS = r"""
  <div class="view" id="view-evals">
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
  <div class="view" id="view-deploy">
    <div class="view-header">
      <span class="view-title">Deployment Configs</span>
    </div>
    <div class="view-scroll">
      <div class="code-tabs" id="deploy-tabs"></div>
      <div class="code-preview">
        <div class="code-desc" id="deploy-desc"></div>
        <div class="code-wrap">
          <button class="code-copy" onclick="copyDeployCode()">Copy</button>
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
          <select class="form-select" id="set-storage" disabled>
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
    <input id="cmd-input"
      placeholder="type a command... (toggle github, profile ops)"
      autocomplete="off" />
    <span class="cmd-hint">tab</span>
  </div>
</div>

<div class="detail-panel" id="detail-panel">
  <div class="detail-header">
    <span class="detail-name" id="detail-name">-</span>
    <div class="detail-close" onclick="closeDetail()">&times;</div>
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
  <div class="detail-actions">
    <button class="btn-action primary" id="btn-enable" onclick="detailToggle(true)">ENABLE</button>
    <button class="btn-action danger" id="btn-disable"
      onclick="detailToggle(false)">DISABLE</button>
  </div>
</div>

<div class="toast-container" id="toast-container"></div>
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
const WS_URL = `ws://${location.hostname}:9092/ws`;
let ws = null;
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
  stdio: '#22c55e', sse: '#06b6d4', http: '#06b6d4',
  native: '#f59e0b', local: '#a855f7'
};

function hashPos(name, total) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = ((h << 5) - h + name.charCodeAt(i)) | 0;
  const angle = (h % 360 + 360) % 360 * Math.PI / 180;
  const radius = 0.32 + Math.abs(h % 100) / 350;
  return { angle, radius };
}

async function api(path, opts = {}) {
  const r = await fetch(API + path, opts);
  return r.json();
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
  t.className = `toast ${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), 3000);
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
  let html = '';
  for (const line of lines) {
    html += `> ${line.t}\n`;
    el.innerHTML = html.replace(/> (.*)/, '> <span class="accent">$1</span>');
    await sleep(line.d);
  }
  const data = await api('/api/status');
  html += `<span class="ok">kater ready. v${data.version}</span>\n`;
  el.innerHTML = html;
  await sleep(300);
  document.getElementById('boot').classList.add('done');
  setTimeout(() => document.getElementById('boot').style.display = 'none', 500);
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ── Init ───────────────────────────────
async function init() {
  await bootSequence();
  await loadProfiles();
  await loadCatalog();
  await loadStatus();
  initCanvas();
  initCommandBar();
  initKeyboard();
  initWebSocket();
  startAnimationLoop();
  setInterval(loadStatus, 5000);
}

async function loadProfiles() {
  const data = await api('/api/profiles');
  profiles = data.profiles;
  const el = document.getElementById('profile-pills');
  el.innerHTML = profiles.map(p =>
    `<div class="pill ${p === activeProfile ? 'active' : ''}"`
    + ` onclick="switchProfile('${p}')">${p}</div>`
  ).join('');
}

function switchProfile(p) {
  activeProfile = p;
  document.querySelectorAll('.pill').forEach(el => {
    el.classList.toggle('active', el.textContent === p);
  });
  loadCatalog();
  toast(`profile: ${p}`);
}

async function loadCatalog() {
  const data = await api('/api/catalog');
  servers = data.servers || [];
  buildNodes();
  document.getElementById('node-count').textContent = `${servers.length} nodes`;
}

async function loadStatus() {
  const data = await api('/api/status');
  document.getElementById('version-tag').textContent = `v${data.version}`;
  document.getElementById('auth-mode').textContent = data.auth_mode;
  document.getElementById('stat-tools').textContent = data.servers?.total || 0;
  document.getElementById('stat-enabled').textContent = data.servers?.enabled || 0;
  document.getElementById('stat-success').textContent = `${data.telemetry?.success_rate || 0}%`;
  document.getElementById('stat-backends').textContent = data.telemetry?.tool_calls || 0;
  document.getElementById('stat-events').textContent = data.telemetry?.total_events || 0;
  const authDot = document.getElementById('auth-dot');
  authDot.style.background = data.auth_mode === 'none' ? '#22c55e' : '#f59e0b';
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
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);
}

function buildNodes() {
  const rect = canvas?.getBoundingClientRect() || { width: 600, height: 400 };
  const cx = rect.width / 2;
  const cy = rect.height / 2;
  const maxR = Math.min(cx, cy) * 0.75;

  nodes = servers.map((s, i) => {
    const pos = hashPos(s.name, servers.length);
    return {
      ...s,
      x: cx + Math.cos(pos.angle) * maxR * pos.radius,
      y: cy + Math.sin(pos.angle) * maxR * pos.radius,
      r: 16,
      pulse: 0,
    };
  });
}

function onCanvasMove(e) {
  const rect = canvas.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;
  hoveredNode = null;
  for (const n of nodes) {
    const dx = x - n.x, dy = y - n.y;
    if (dx * dx + dy * dy < (n.r + 8) ** 2) {
      hoveredNode = n;
      canvas.style.cursor = 'pointer';
      return;
    }
  }
  canvas.style.cursor = 'default';
}

function onCanvasClick(e) {
  if (hoveredNode) {
    openDetail(hoveredNode);
  } else if (selectedNode) {
    closeDetail();
  }
}

function drawConstellation() {
  if (!ctx || !canvas) return;
  const rect = canvas.getBoundingClientRect();
  const w = rect.width, h = rect.height;
  const cx = w / 2, cy = h / 2;

  ctx.clearRect(0, 0, w, h);

  // center node (Kater)
  const time = Date.now() / 1000;
  const pulse = 0.5 + 0.5 * Math.sin(time * 1.5);

  // glow
  const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, 60);
  grad.addColorStop(0, 'rgba(245,158,11,0.15)');
  grad.addColorStop(1, 'rgba(245,158,11,0)');
  ctx.fillStyle = grad;
  ctx.fillRect(cx - 60, cy - 60, 120, 120);

  // connections
  for (const n of nodes) {
    const color = transportColors[n.transport] || '#64748b';
    const isActive = n.enabled && n.env_configured;
    const isHovered = n === hoveredNode;

    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(n.x, n.y);

    if (isActive) {
      ctx.strokeStyle = color + '44';
      ctx.lineWidth = isHovered ? 2 : 1.5;
    } else {
      ctx.strokeStyle = 'rgba(48,60,82,0.3)';
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 4]);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    // data particles
    if (isActive && Math.random() < 0.02) {
      particles.push({
        x: n.x, y: n.y, tx: cx, ty: cy,
        color: color, life: 1.0, speed: 0.01 + Math.random() * 0.01,
      });
    }
  }

  // update + draw particles
  particles = particles.filter(p => p.life > 0);
  for (const p of particles) {
    p.life -= 0.015;
    const t = 1 - p.life;
    p.x = p.x + (p.tx - p.x) * p.speed;
    p.y = p.y + (p.tx - p.y) * p.speed;
    ctx.beginPath();
    ctx.arc(p.x, p.y, 2, 0, Math.PI * 2);
    ctx.fillStyle = p.color + Math.floor(p.life * 200).toString(16).padStart(2, '0');
    ctx.fill();
  }

  // server nodes
  for (const n of nodes) {
    const color = transportColors[n.transport] || '#64748b';
    const isActive = n.enabled && n.env_configured;
    const isHovered = n === hoveredNode;
    const r = isHovered ? n.r + 3 : n.r;

    // glow for active
    if (isActive) {
      const g = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, r * 2);
      g.addColorStop(0, color + '22');
      g.addColorStop(1, color + '00');
      ctx.fillStyle = g;
      ctx.fillRect(n.x - r * 2, n.y - r * 2, r * 4, r * 4);
    }

    // circle
    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    if (isActive) {
      ctx.fillStyle = color + '22';
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
    } else {
      ctx.fillStyle = 'rgba(18,24,38,0.8)';
      ctx.fill();
      ctx.strokeStyle = '#303c4c';
      ctx.lineWidth = 1.5;
    }
    ctx.stroke();

    // inner dot
    ctx.beginPath();
    ctx.arc(n.x, n.y, 4, 0, Math.PI * 2);
    ctx.fillStyle = isActive ? color : '#475569';
    ctx.fill();

    // label
    ctx.font = '11px SF Mono, Consolas, monospace';
    ctx.textAlign = 'center';
    ctx.fillStyle = isHovered ? '#f1f5f9' : isActive ? '#e2e8f0' : '#475569';
    ctx.fillText(n.name, n.x, n.y + r + 14);
  }

  // Kater center
  ctx.beginPath();
  ctx.arc(cx, cy, 22 + pulse * 3, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(245,158,11,0.08)';
  ctx.fill();

  ctx.beginPath();
  ctx.arc(cx, cy, 16, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(245,158,11,0.2)';
  ctx.fill();
  ctx.strokeStyle = '#f59e0b';
  ctx.lineWidth = 2;
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(cx, cy, 6, 0, Math.PI * 2);
  ctx.fillStyle = '#f59e0b';
  ctx.fill();

  ctx.font = 'bold 12px SF Mono, Consolas, monospace';
  ctx.textAlign = 'center';
  ctx.fillStyle = '#f59e0b';
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
function openDetail(node) {
  selectedNode = node;
  const panel = document.getElementById('detail-panel');
  document.getElementById('detail-name').textContent = node.name;
  document.getElementById('detail-desc').textContent = node.description || '-';

  const badges = document.getElementById('detail-badges');
  badges.innerHTML = `
    <span class="badge ${node.transport}">${node.transport}</span>
    <span class="badge ${node.risk}">${node.risk}</span>
    ${node.env_configured
      ? '<span class="badge low">configured</span>'
      : '<span class="badge high">missing env</span>'}
  `;

  const envEl = document.getElementById('detail-env');
  if (node.env_required && node.env_required.length > 0) {
    envEl.innerHTML = node.env_required.map(e => {
      const set = node.env_configured;
      return `${e}: ${
        set
          ? '<span style="color:#22c55e">set</span>'
          : '<span style="color:#ef4444">MISSING</span>'
      }`;
    }).join('<br>');
  } else {
    envEl.textContent = '(none required)';
  }

  const cmdEl = document.getElementById('detail-cmd');
  if (node.mcp && node.mcp.command) {
    cmdEl.textContent = `${node.mcp.command} ${(node.mcp.args || []).join(' ')}`;
  } else if (node.mcp && node.mcp.url) {
    cmdEl.textContent = node.mcp.url;
  } else {
    cmdEl.textContent = '-';
  }

  document.getElementById('detail-profiles').textContent = (node.profiles || []).join(', ');

  const enableBtn = document.getElementById('btn-enable');
  const disableBtn = document.getElementById('btn-disable');
  if (node.enabled) {
    enableBtn.style.opacity = '0.4';
    disableBtn.style.opacity = '1';
  } else {
    enableBtn.style.opacity = '1';
    disableBtn.style.opacity = '0.4';
  }

  panel.classList.add('open');
}

function closeDetail() {
  document.getElementById('detail-panel').classList.remove('open');
  selectedNode = null;
}

async function detailToggle(enable) {
  if (!selectedNode) return;
  const action = enable ? 'enable' : 'disable';
  await apiPost(`/api/mcp/servers/${selectedNode.name}/${action}`, {});
  toast(`${selectedNode.name}: ${enable ? 'enabled' : 'disabled'}`, 'success');
  selectedNode.enabled = enable;
  await loadCatalog();
  openDetail(selectedNode);
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
        if (match) input.value = `${parts[0]} ${match.name}`;
      }
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDetail();
  });
}

async function runCommand(input) {
  if (!input) return;
  const parts = input.split(/\s+/);
  const cmd = parts[0];

  if ((cmd === 'toggle' || cmd === 'enable' || cmd === 'disable') && parts[1]) {
    const server = parts[1];
    const action = cmd === 'toggle' ? 'toggle' : cmd;
    await apiPost(`/api/mcp/servers/${server}/${action}`, {});
    toast(`${server}: ${action}d`, 'success');
    await loadCatalog();
  } else if (cmd === 'profile' && parts[1]) {
    switchProfile(parts[1]);
  } else if (cmd === 'status') {
    const data = await api('/api/status');
    toast(`${data.servers.enabled}/${data.servers.total} servers`
      + ` | ${data.telemetry.success_rate}% success`);
  } else if (cmd === 'refresh') {
    await loadCatalog();
    toast('catalog refreshed');
  } else {
    toast(`unknown: ${input}`, 'error');
  }
}

// ── WebSocket ──────────────────────────
function initWebSocket() {
  try {
    ws = new WebSocket(WS_URL);
    ws.onopen = () => {
      ws.send(JSON.stringify({ cmd: 'subscribe' }));
    };
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        handleWSMessage(data);
      } catch {}
    };
    ws.onclose = () => setTimeout(initWebSocket, 3000);
  } catch {}
}

function handleWSMessage(data) {
  if (data.type === 'server_enabled'
      || data.type === 'server_disabled'
      || data.type === 'server_toggled') {
    loadCatalog();
    toast(`${data.name}: ${data.type}`, 'success');
  }
  if (data.type === 'telemetry' || data.type === 'tool_call') {
    appendTelemetry(data);
  }
}

function appendTelemetry(event) {
  const stream = document.getElementById('telemetry-stream');
  const row = document.createElement('div');
  const now = new Date();
  const ts = String(now.getHours()).padStart(2,'0')
    + ':' + String(now.getMinutes()).padStart(2,'0')
    + ':' + String(now.getSeconds()).padStart(2,'0');
  const ok = event.success !== false;
  row.className = 'tlm-row';
  row.innerHTML = `
    <span class="tlm-time">${ts}</span>
    <span class="tlm-icon ${ok ? 'ok' : 'err'}">${ok ? '\u2713' : '\u2717'}</span>
    <span class="tlm-name">${event.name || event.type}</span>
    <span class="tlm-ms">${Math.round(event.duration_ms || 0)}ms</span>
  `;
  stream.insertBefore(row, stream.firstChild);

  while (stream.children.length > 50) {
    stream.lastChild.remove();
  }

  setTimeout(() => row.classList.add('faded'), 4000);
}

// ── Tunnels ────────────────────────────
async function toggleTunnel(provider) {
  toast(`tunnel ${provider}: starting...`);
  try {
    const data = await apiPost(`/api/tunnel/${provider}/start`, {});
    const btn = document.getElementById(provider === 'cloudflare' ? 'btn-cf' : 'btn-ts');
    if (data.url) {
      btn.textContent = 'ON';
      btn.classList.add('active');
      toast(`tunnel: ${data.url}`, 'success');
    } else if (data.error) {
      toast(`tunnel error: ${data.error}`, 'error');
    }
  } catch (e) {
    toast('tunnel: failed to start', 'error');
  }
}

// ── View Navigation ────────────────────
let currentView = 'dashboard';

function switchView(name) {
  currentView = name;
  document.querySelectorAll('.view').forEach(v => {
    v.classList.toggle('active', v.id === 'view-' + name);
  });
  document.querySelectorAll('.nav-tabs .tab').forEach(t => {
    t.classList.toggle('active', t.dataset.view === name);
  });
  loadViewData(name);
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
  const data = await api('/api/catalog');
  const grid = document.getElementById('catalog-grid');
  document.getElementById('catalog-count').textContent =
    (data.total || 0) + ' servers';
  const items = data.servers || [];
  if (!items.length) {
    grid.innerHTML = '<div class="view-empty">No servers found.</div>';
    return;
  }
  grid.innerHTML = items.map(s => `
    <div class="server-card" onclick="openServerDetail('${s.name}')">
      <div class="server-card-head">
        <span class="server-card-name">${s.name}</span>
        <div class="toggle-switch ${s.enabled ? 'on' : ''}"
          onclick="event.stopPropagation();
            toggleServerCard('${s.name}', this)"></div>
      </div>
      <div class="badges" style="margin-bottom:6px">
        <span class="badge ${s.transport}">${s.transport}</span>
        <span class="badge ${s.risk}">${s.risk}</span>
        ${s.env_configured
          ? '<span class="badge low">configured</span>'
          : '<span class="badge high">missing env</span>'}
      </div>
      <div class="server-card-desc">${s.description || ''}</div>
    </div>
  `).join('');
}

async function toggleServerCard(name, el) {
  const data = await apiPost(
    '/api/mcp/servers/' + name + '/toggle', {}
  );
  if (data.error) { toast(data.error, 'error'); return; }
  el.classList.toggle('on', data.enabled);
  toast(name + ': ' + (data.enabled ? 'enabled' : 'disabled'),
    'success');
}

async function openServerDetail(name) {
  const data = await api('/api/mcp/servers/' + name);
  if (data.error) { toast(data.error, 'error'); return; }
  openDetail(data);
}

async function loadEvalsView() {
  const data = await api('/api/evals');
  const summary = data.summary || {};
  const tc = data.tool_calls || {};
  document.getElementById('eval-summary').innerHTML = `
    <div class="eval-stat"><span class="big-num">${tc.total || 0}</span>
      calls</div>
    <div class="eval-stat"><span class="big-num">${tc.unique_tools || 0}</span>
      tools</div>
    <div class="eval-stat"><span class="big-num">${summary.overall_success_rate || 0}%</span>
      success</div>
    <div class="eval-stat"><span class="big-num">${summary.total_errors || 0}</span>
      errors</div>
  `;
  const perTool = tc.per_tool || {};
  const entries = Object.entries(perTool)
    .sort((a, b) => b[1].total - a[1].total);
  const tbody = document.getElementById('eval-tbody');
  if (!entries.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="view-empty">'
      + 'No eval data yet.</td></tr>';
    return;
  }
  tbody.innerHTML = entries.map(([name, s]) => {
    const rate = s.success_rate || 0;
    const color = rate >= 90 ? '#22c55e'
      : rate >= 50 ? '#f59e0b' : '#ef4444';
    const avg = Math.round(s.avg_duration_ms || 0);
    return `<tr>
      <td>${name}</td>
      <td>${s.total}</td>
      <td><span class="success-bar"><span class="success-bar-fill"
        style="width:${rate}%;background:${color}"></span></span>${rate}%</td>
      <td>${avg}ms</td>
    </tr>`;
  }).join('');
}

let deployFormats = [];

async function loadDeployView() {
  const data = await api('/api/deploy');
  deployFormats = data.formats || [];
  const tabs = document.getElementById('deploy-tabs');
  tabs.innerHTML = deployFormats.map(f =>
    `<button class="code-tab" data-fmt="${f.name}"
      onclick="selectDeployFormat('${f.name}')">${f.name}</button>`
  ).join('');
  if (deployFormats[0]) await selectDeployFormat(deployFormats[0].name);
}

async function selectDeployFormat(fmt) {
  document.querySelectorAll('.code-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.fmt === fmt);
  });
  const data = await api('/api/deploy/' + fmt);
  const code = document.getElementById('deploy-code');
  const desc = document.getElementById('deploy-desc');
  if (data.error) {
    code.textContent = '# ' + data.error;
    desc.textContent = '';
    return;
  }
  code.textContent = JSON.stringify(data, null, 2);
  desc.textContent = data.description
    || (deployFormats.find(f => f.name === fmt) || {}).description
    || '';
}

function copyDeployCode() {
  const text = document.getElementById('deploy-code').textContent || '';
  navigator.clipboard.writeText(text).then(
    () => toast('copied to clipboard', 'success'),
    () => toast('clipboard access denied', 'error')
  );
}

async function loadSettingsView() {
  const data = await api('/api/settings');
  const auth = data.auth || {};
  document.getElementById('set-auth-mode').value = auth.mode || 'none';
  document.getElementById('set-cors').value =
    (data.cors_origins || []).join(', ');
  document.getElementById('set-rate-limit').value =
    data.rate_limit_per_min || 0;
  document.getElementById('set-profile').value =
    data.default_profile || 'core';
  document.getElementById('set-storage').value =
    data.storage_backend || 'sqlite';
}

async function saveSettings() {
  const body = {
    auth: { mode: document.getElementById('set-auth-mode').value },
    cors_origins: document.getElementById('set-cors').value
      .split(',').map(s => s.trim()).filter(Boolean),
    rate_limit_per_min:
      parseInt(document.getElementById('set-rate-limit').value) || 0,
    default_profile: document.getElementById('set-profile').value,
  };
  try {
    await apiPost('/api/settings', body);
    toast('settings saved', 'success');
  } catch (e) {
    toast('failed to save settings', 'error');
  }
}

function initKeyboard() {
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
      if (v) switchView(v);
    }
  });
}

// ── Start ──────────────────────────────
window.addEventListener('DOMContentLoaded', init);
"""


def render_dashboard() -> str:
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
        f"<script>{_JS}</script>\n"
        "</body>\n</html>\n"
    )
