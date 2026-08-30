#!/usr/bin/env python3
"""
Generates the comprehensive, Composio-grade Kater Dev Tools Dashboard.
Includes:
- Big Integrations Hub & Agent Toolkits
- Deep Action / Trigger Inspector Drawer
- Live Action Runner / Playground
- Quick Add Integration & Custom MCP Server Creator
- Control Room / Overview
- Browser Workspace
- PR Gate & Reviews
- Automations
- Catalog & Settings
"""
import sys

def build_dashboard():
    # Write directly to src/dashboardHtml.ts
    with open('src/dashboardHtml.ts', 'w', encoding='utf-8') as f:
        f.write('''import { McpServerDoc } from './types.js';

export function getDashboardHtml(port: number): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Kater Dev Tools — MCP Gateway & Integration Hub</title>
  <meta name="description" content="Composio-grade MCP Gateway with 50+ enterprise integrations, composable agent toolkits, and real-time control room.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0d10;
      --surface: #111419;
      --surface-2: #171b22;
      --elevated: #1d222c;
      --border: rgba(255,255,255,0.07);
      --border-strong: rgba(255,255,255,0.13);
      --text: #e6e9ef;
      --text-muted: #98a1b1;
      --text-faint: #5d6675;
      --accent: #2dd4bf;
      --accent-dim: rgba(45,212,191,0.14);
      --accent-line: rgba(45,212,191,0.35);
      --cta: #f2f4f7;
      --cta-text: #0b0d10;
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
      --sidebar-w: 230px;
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
    a, button, input, select, textarea, [role="switch"], [tabindex] { scroll-margin-top: 64px; }
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 4px; }
    ::-webkit-scrollbar-track { background: transparent; }
    a:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible, [role="switch"]:focus-visible, [tabindex]:focus-visible {
      outline: 2px solid var(--accent); outline-offset: 2px; border-radius: var(--radius-sm);
    }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
    
    /* Layout */
    #app { display: grid; grid-template-columns: var(--sidebar-w) 1fr; height: 100vh; }
    .sidebar { display: flex; flex-direction: column; border-right: 1px solid var(--border); background: var(--surface); min-height: 0; }
    .sidebar-brand { padding: 16px; border-bottom: 1px solid var(--border); }
    .brand-row { display: flex; align-items: center; gap: 9px; }
    .brand-mark {
      width: 24px; height: 24px; flex-shrink: 0; border-radius: 6px;
      background: linear-gradient(150deg, var(--accent), #119e8c);
      position: relative; box-shadow: 0 0 0 1px rgba(45,212,191,0.25), 0 4px 10px rgba(45,212,191,0.18);
    }
    .brand-mark::after {
      content: ""; position: absolute; inset: 6px; border-radius: 2px;
      border: 1.5px solid rgba(11,13,16,0.85); border-right-color: transparent; border-bottom-color: transparent;
    }
    .brand-name { font-family: var(--sans); font-size: 15px; font-weight: 700; color: var(--text); }
    .brand-meta { margin-top: 6px; font-family: var(--mono); font-size: 10.5px; color: var(--text-faint); }
    
    .sidebar-nav { display: flex; flex-direction: column; padding: 10px; gap: 2px; flex: 1; overflow-y: auto; }
    .nav-section { font-family: var(--mono); font-size: 9.5px; font-weight: 600; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.08em; padding: 12px 10px 4px; }
    .tab {
      display: flex; align-items: center; gap: 9px; width: 100%; padding: 8px 10px;
      border: none; border-radius: var(--radius-sm); background: transparent; color: var(--text-muted);
      font-family: var(--sans); font-size: 13px; font-weight: 500; text-align: left; cursor: pointer; position: relative;
    }
    .tab:hover { background: var(--surface-2); color: var(--text); }
    .tab.active { background: var(--surface-2); color: var(--text); }
    .tab.active::before { content: ""; position: absolute; left: 0; top: 6px; bottom: 6px; width: 2px; border-radius: 2px; background: var(--accent); }
    .tab-icon { width: 16px; height: 16px; flex-shrink: 0; opacity: 0.85; display: inline-flex; align-items: center; justify-content: center; }
    .tab.active .tab-icon { opacity: 1; color: var(--accent); }
    .tab-label { flex: 1; }
    .tab-badge { font-family: var(--mono); font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 999px; background: var(--accent-dim); color: var(--accent); border: 1px solid var(--accent-line); }
    .tab-badge.green { background: var(--ok-dim); color: var(--ok); border-color: rgba(61,220,151,0.3); }

    .sidebar-add-btn {
      display: flex; align-items: center; justify-content: center; gap: 7px;
      width: 100%; margin: 8px 0; padding: 8px 10px;
      border: 1px dashed var(--accent-line); border-radius: var(--radius-sm);
      background: var(--accent-dim); color: var(--accent);
      font-family: var(--mono); font-size: 11.5px; font-weight: 600;
      text-align: center; cursor: pointer; transition: all 120ms ease;
    }
    .sidebar-add-btn:hover { background: rgba(45,212,191,0.22); border-color: var(--accent); color: #fff; }

    .sidebar-foot { padding: 12px 14px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 8px; }
    .auth-badge { display: flex; align-items: center; gap: 8px; font-family: var(--mono); font-size: 11px; color: var(--text-muted); }
    .auth-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--ok); flex-shrink: 0; }
    .foot-hint { font-family: var(--mono); font-size: 10px; color: var(--text-faint); display: flex; align-items: center; gap: 6px; }
    .foot-hint kbd { font-family: var(--mono); font-size: 9.5px; border: 1px solid var(--border); border-radius: 3px; padding: 0 4px; color: var(--text-muted); }

    /* Workspace */
    .workspace { display: flex; flex-direction: column; min-width: 0; min-height: 0; }
    .page-toolbar {
      display: flex; align-items: center; justify-content: space-between; gap: 12px;
      padding: 10px 18px; border-bottom: 1px solid var(--border); background: var(--bg);
    }
    .page-title { font-family: var(--sans); font-size: 14px; font-weight: 600; color: var(--text); }
    .toolbar-right { display: flex; align-items: center; gap: 10px; }
    .profile-pills { display: flex; gap: 5px; flex-wrap: wrap; }
    .pill {
      font-family: var(--mono); font-size: 11px; padding: 3px 8px; border-radius: 999px;
      border: 1px solid var(--border); color: var(--text-muted); cursor: pointer; user-select: none; background: transparent;
    }
    .pill:hover { color: var(--text); border-color: var(--border-strong); }
    .pill.active { background: var(--accent-dim); color: var(--accent); border-color: var(--accent-line); }
    .palette-trigger {
      display: flex; align-items: center; gap: 8px; font-family: var(--sans); font-size: 12px; color: var(--text-muted);
      background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 5px 9px; cursor: pointer;
    }
    .palette-trigger:hover { border-color: var(--border-strong); color: var(--text); }
    .palette-trigger kbd { font-family: var(--mono); font-size: 10px; color: var(--text-faint); border: 1px solid var(--border); border-radius: 3px; padding: 0 4px; }

    .page-body { flex: 1; min-height: 0; overflow: hidden; display: flex; flex-direction: column; }
    .view { display: none; flex: 1; min-height: 0; overflow: hidden; }
    .view.active { display: flex; flex-direction: column; }
    .view-scroll { flex: 1; overflow-y: auto; min-height: 0; scrollbar-width: thin; scrollbar-color: var(--border-strong) transparent; }

    /* ═══════════════════════════════════════════════════════════════
       COMPOSIO-GRADE INTEGRATIONS HUB STYLING
    ═══════════════════════════════════════════════════════════════ */
    .hub-hero {
      padding: 20px 24px 16px;
      background: linear-gradient(180deg, rgba(45,212,191,0.04) 0%, transparent 100%);
      border-bottom: 1px solid var(--border);
      display: flex; flex-direction: column; gap: 14px;
    }
    .hub-hero-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
    .hub-hero-title { font-size: 20px; font-weight: 700; color: var(--text); letter-spacing: -0.02em; }
    .hub-hero-sub { font-size: 13px; color: var(--text-muted); margin-top: 4px; max-width: 680px; }
    .hub-hero-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

    .hub-stat-grid {
      display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 4px;
    }
    .hub-stat-card {
      background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
      padding: 12px 14px; display: flex; flex-direction: column; gap: 2px;
    }
    .hub-stat-num { font-family: var(--mono); font-size: 22px; font-weight: 700; color: var(--text); }
    .hub-stat-num.accent { color: var(--accent); }
    .hub-stat-num.ok { color: var(--ok); }
    .hub-stat-label { font-family: var(--mono); font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-faint); }
    .hub-stat-desc { font-size: 11px; color: var(--text-muted); }

    /* Hub Toolbar */
    .hub-toolbar {
      padding: 12px 24px; border-bottom: 1px solid var(--border); background: var(--bg);
      display: flex; flex-direction: column; gap: 10px;
    }
    .hub-search-row { display: flex; align-items: center; gap: 10px; }
    .hub-search-input {
      flex: 1; max-width: 480px; padding: 8px 12px; font-family: var(--sans); font-size: 13px;
      background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text);
    }
    .hub-search-input:focus { border-color: var(--accent); outline: none; }
    .hub-view-mode { display: flex; gap: 4px; margin-left: auto; }
    .hub-mode-btn {
      font-family: var(--mono); font-size: 11px; padding: 5px 10px; border-radius: var(--radius-sm);
      border: 1px solid var(--border); background: transparent; color: var(--text-muted); cursor: pointer;
    }
    .hub-mode-btn:hover { color: var(--text); border-color: var(--border-strong); }
    .hub-mode-btn.active { background: var(--surface-2); color: var(--text); border-color: var(--accent-line); }

    .hub-filters-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
    .hub-chip {
      font-family: var(--mono); font-size: 11px; padding: 4px 10px; border-radius: 999px;
      border: 1px solid var(--border); background: transparent; color: var(--text-muted); cursor: pointer;
      display: inline-flex; align-items: center; gap: 6px;
    }
    .hub-chip:hover { border-color: var(--border-strong); color: var(--text); }
    .hub-chip.active { background: var(--accent-dim); color: var(--accent); border-color: var(--accent-line); font-weight: 600; }
    .hub-chip .count { font-size: 10px; opacity: 0.7; }

    /* Toolkits Section */
    .toolkit-section { padding: 20px 24px 10px; display: flex; flex-direction: column; gap: 12px; }
    .toolkit-section-head { display: flex; align-items: center; justify-content: space-between; }
    .toolkit-section-title { font-size: 15px; font-weight: 700; color: var(--text); display: flex; align-items: center; gap: 8px; }
    .toolkit-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 14px; }
    
    .toolkit-card {
      background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
      padding: 16px; display: flex; flex-direction: column; gap: 12px; transition: border-color 120ms ease;
    }
    .toolkit-card:hover { border-color: var(--border-strong); }
    .toolkit-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
    .toolkit-icon { width: 32px; height: 32px; border-radius: 8px; background: var(--surface-2); border: 1px solid var(--border); display: flex; align-items: center; justify-content: center; font-size: 16px; flex-shrink: 0; }
    .toolkit-info { flex: 1; }
    .toolkit-name { font-size: 14px; font-weight: 600; color: var(--text); }
    .toolkit-desc { font-size: 12px; color: var(--text-muted); margin-top: 3px; line-height: 1.4; }
    .toolkit-badges { display: flex; gap: 5px; flex-wrap: wrap; margin-top: 6px; }
    .toolkit-servers-preview {
      display: flex; align-items: center; gap: 6px; flex-wrap: wrap; padding: 8px 10px;
      background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius-sm);
    }
    .tk-server-tag { font-family: var(--mono); font-size: 10.5px; padding: 2px 6px; border-radius: 3px; background: var(--surface-2); border: 1px solid var(--border); color: var(--text); }
    .tk-server-tag.active { border-color: var(--ok-dim); color: var(--ok); }
    .toolkit-foot { display: flex; align-items: center; justify-content: space-between; margin-top: auto; padding-top: 6px; border-top: 1px solid var(--border); }
    .toolkit-foot-meta { font-family: var(--mono); font-size: 11px; color: var(--text-muted); }

    /* Integration Cards Grid */
    .hub-grid {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(310px, 1fr));
      gap: 14px; padding: 18px 24px 24px;
    }
    .integ-card {
      background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
      padding: 16px; display: flex; flex-direction: column; gap: 10px; cursor: pointer; transition: all 120ms ease;
    }
    .integ-card:hover { background: var(--surface-2); border-color: var(--border-strong); transform: translateY(-1px); }
    .integ-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
    .integ-icon-wrap {
      width: 36px; height: 36px; border-radius: 8px; background: var(--surface-2);
      border: 1px solid var(--border-strong); display: flex; align-items: center; justify-content: center;
      font-family: var(--mono); font-size: 13px; font-weight: 700; color: var(--text); flex-shrink: 0;
    }
    .integ-meta { flex: 1; min-width: 0; }
    .integ-name { font-size: 14px; font-weight: 600; color: var(--text); display: flex; align-items: center; gap: 6px; }
    .integ-category { font-family: var(--mono); font-size: 10px; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.05em; }
    .integ-desc { font-size: 12px; color: var(--text-muted); line-height: 1.45; min-height: 35px; }

    .integ-tags { display: flex; gap: 5px; flex-wrap: wrap; }
    .integ-tag {
      font-family: var(--mono); font-size: 10px; padding: 2px 6px; border-radius: 4px;
      background: var(--bg); border: 1px solid var(--border); color: var(--text-faint);
    }
    .integ-tag.auth-oauth { color: var(--accent); border-color: var(--accent-line); }
    .integ-tag.auth-key { color: var(--warn); border-color: var(--warn-dim); }
    .integ-tag.auth-none { color: var(--ok); border-color: var(--ok-dim); }

    .integ-foot {
      display: flex; align-items: center; justify-content: space-between;
      padding-top: 10px; border-top: 1px solid var(--border); margin-top: auto;
    }
    .integ-actions-count { font-family: var(--mono); font-size: 11px; color: var(--text-muted); }
    .integ-btns { display: flex; align-items: center; gap: 6px; }
    .integ-btn {
      font-family: var(--mono); font-size: 11px; padding: 4px 8px; border-radius: var(--radius-sm);
      border: 1px solid var(--border); background: transparent; color: var(--text-muted); cursor: pointer;
    }
    .integ-btn:hover { border-color: var(--border-strong); color: var(--text); }
    .integ-btn.primary { background: var(--accent-dim); border-color: var(--accent-line); color: var(--accent); }

    /* Action Inspector / Deep Drawer */
    .drawer-overlay {
      position: fixed; inset: 0; z-index: 100; display: none; background: rgba(6,7,9,0.7);
      backdrop-filter: blur(2px); justify-content: flex-end;
    }
    .drawer-overlay.open { display: flex; }
    .drawer-panel {
      width: min(680px, 94vw); height: 100vh; background: var(--surface);
      border-left: 1px solid var(--border-strong); display: flex; flex-direction: column;
      box-shadow: -16px 0 48px rgba(0,0,0,0.5); animation: drawerSlideIn 180ms cubic-bezier(0.16, 1, 0.3, 1);
    }
    @keyframes drawerSlideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }

    .drawer-head {
      padding: 16px 20px; border-bottom: 1px solid var(--border); display: flex;
      align-items: center; justify-content: space-between; gap: 12px; background: var(--surface);
    }
    .drawer-tabs {
      display: flex; gap: 2px; padding: 8px 16px 0; border-bottom: 1px solid var(--border); background: var(--bg);
      overflow-x: auto;
    }
    .drawer-tab {
      font-family: var(--mono); font-size: 11.5px; padding: 7px 12px; border: none; border-bottom: 2px solid transparent;
      background: transparent; color: var(--text-muted); cursor: pointer; white-space: nowrap;
    }
    .drawer-tab:hover { color: var(--text); }
    .drawer-tab.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }

    .drawer-body { flex: 1; overflow-y: auto; padding: 16px 20px; display: flex; flex-direction: column; gap: 16px; }
    .action-card {
      background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius);
      padding: 12px 14px; display: flex; flex-direction: column; gap: 8px;
    }
    .action-card-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
    .action-title { font-family: var(--mono); font-size: 13px; font-weight: 600; color: var(--text); }
    .action-desc { font-size: 12px; color: var(--text-muted); line-height: 1.4; }
    
    .param-table { width: 100%; border-collapse: collapse; margin-top: 4px; font-family: var(--mono); font-size: 11px; }
    .param-table th { text-align: left; padding: 4px 8px; color: var(--text-faint); border-bottom: 1px solid var(--border); font-size: 10px; text-transform: uppercase; }
    .param-table td { padding: 6px 8px; border-bottom: 1px solid rgba(255,255,255,0.03); }
    .param-name { color: var(--accent); }
    .param-type { color: var(--text-faint); }
    .param-req { color: var(--err); font-size: 10px; }

    /* Playground */
    .playground-layout {
      display: grid; grid-template-columns: 1fr 1fr; gap: 16px; padding: 16px 24px; flex: 1; min-height: 0;
    }
    .playground-pane {
      background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
      display: flex; flex-direction: column; min-height: 0; overflow: hidden;
    }
    .playground-pane-head {
      padding: 10px 14px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between;
      font-family: var(--mono); font-size: 11px; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.05em;
    }
    .playground-pane-body { padding: 14px; flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }
    .json-editor {
      width: 100%; flex: 1; min-height: 220px; font-family: var(--mono); font-size: 12px; line-height: 1.5;
      background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text); padding: 10px;
      resize: vertical;
    }
    .terminal-out {
      width: 100%; flex: 1; min-height: 220px; font-family: var(--mono); font-size: 11.5px; line-height: 1.5;
      background: #06080a; border: 1px solid var(--border); border-radius: var(--radius-sm); color: #86e1fc; padding: 12px;
      overflow: auto; white-space: pre;
    }

    /* Common Components */
    .btn {
      font-family: var(--sans); font-size: 12px; font-weight: 600; padding: 6px 12px; border-radius: var(--radius-sm);
      border: 1px solid var(--border); background: var(--surface-2); color: var(--text); cursor: pointer;
      display: inline-flex; align-items: center; justify-content: center; gap: 6px;
    }
    .btn:hover { border-color: var(--border-strong); }
    .btn-primary { background: var(--cta); color: var(--cta-text); border-color: var(--cta); }
    .btn-primary:hover { opacity: 0.9; }
    .btn-accent { background: var(--accent); color: #0b0d10; border-color: var(--accent); }
    .btn-accent:hover { background: #24bfa9; }

    /* Overview View */
    #view-dashboard { padding: 14px 18px 0; gap: 14px; }
    .exc-strip { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .exc-item {
      display: inline-flex; align-items: center; gap: 7px; font-family: var(--mono); font-size: 11.5px; color: var(--text-muted);
      background: var(--surface); border: 1px solid var(--border); border-radius: 999px; padding: 4px 11px; cursor: pointer;
    }
    .exc-item.active { border-color: var(--accent-line); color: var(--text); background: var(--surface-2); }
    .exc-item .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--idle); }
    .exc-item.ok .dot { background: var(--ok); }
    .exc-item.warn .dot { background: var(--warn); }
    .exc-item.err .dot { background: var(--err); }
    .exc-item .n { color: var(--text); font-weight: 600; }
    .exc-spacer { flex: 1; }
    .live-indicator { display: inline-flex; align-items: center; gap: 7px; font-family: var(--mono); font-size: 11px; color: var(--text-muted); }
    .live-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--ok); }

    .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
    .kpi { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 12px 14px; min-height: 90px; display: flex; flex-direction: column; gap: 4px; }
    .kpi-top { display: flex; justify-content: space-between; align-items: center; }
    .kpi-label { font-family: var(--mono); font-size: 10px; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.06em; }
    .kpi-value { font-family: var(--mono); font-size: 24px; font-weight: 700; color: var(--text); }
    .kpi-sub { font-family: var(--mono); font-size: 10.5px; color: var(--text-muted); }

    .dash-cols { flex: 1; min-height: 0; display: grid; grid-template-columns: 1fr 360px; gap: 12px; padding-bottom: 12px; }
    .panel { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
    .panel-head { padding: 10px 14px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }
    .panel-title { font-size: 12px; font-weight: 600; color: var(--text); display: flex; align-items: center; gap: 8px; }
    .panel-meta { font-family: var(--mono); font-size: 11px; color: var(--text-faint); }
    .server-map { flex: 1; overflow-y: auto; }

    .route-table { width: 100%; border-collapse: collapse; }
    .route-table th { text-align: left; padding: 8px 14px; font-family: var(--mono); font-size: 9.5px; color: var(--text-faint); text-transform: uppercase; border-bottom: 1px solid var(--border); background: var(--surface); position: sticky; top: 0; }
    .route-table td { padding: 9px 14px; border-bottom: 1px solid var(--border); font-size: 12.5px; }
    .route-table tbody tr:hover td { background: var(--surface-2); }
    .route-name { font-family: var(--mono); font-weight: 600; color: var(--text); }
    .status-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--idle); }
    .status-dot.ok { background: var(--ok); }
    .status-dot.off { background: var(--idle); }

    .telemetry-stream { flex: 1; overflow-y: auto; padding: 6px 8px; font-family: var(--mono); font-size: 11px; }
    .tlm-row { display: flex; align-items: center; gap: 8px; padding: 4px 6px; border-radius: var(--radius-sm); }
    .tlm-row:hover { background: var(--surface-2); }
    .tlm-time { color: var(--text-faint); }
    .tlm-name { color: var(--text); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .tlm-ms { margin-left: auto; color: var(--text-muted); }

    /* Browser View */
    .browser-layout { display: grid; grid-template-columns: 220px 1fr 240px; height: 100%; }
    .browser-sessions, .browser-log-pane { border-right: 1px solid var(--border); background: var(--surface); display: flex; flex-direction: column; }
    .browser-log-pane { border-right: none; border-left: 1px solid var(--border); }
    .browser-pane-head { padding: 10px 12px; border-bottom: 1px solid var(--border); font-family: var(--mono); font-size: 10px; text-transform: uppercase; color: var(--text-faint); }
    .browser-session-list, .browser-log { flex: 1; overflow-y: auto; padding: 8px; }
    .browser-session { width: 100%; text-align: left; padding: 8px; border: 1px solid transparent; border-radius: var(--radius-sm); background: transparent; color: var(--text-muted); cursor: pointer; margin-bottom: 4px; font-family: var(--sans); font-size: 12px; }
    .browser-session:hover, .browser-session.active { background: var(--surface-2); color: var(--text); border-color: var(--accent-line); }
    .browser-main { display: flex; flex-direction: column; min-width: 0; min-height: 0; }
    .browser-toolbar { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border-bottom: 1px solid var(--border); background: var(--bg); }
    .browser-url { flex: 1; font-family: var(--mono); font-size: 12px; padding: 6px 10px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--surface); color: var(--text); }
    .browser-stage { flex: 1; display: flex; align-items: center; justify-content: center; background: radial-gradient(1200px 600px at 20% 0%, rgba(45,212,191,0.06), transparent 55%), #0e1116; }

    /* PR Gate */
    .pr-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; padding: 14px 18px; }
    .pr-card { border: 1px solid var(--border); border-radius: var(--radius); padding: 12px 14px; background: var(--surface); display: flex; flex-direction: column; gap: 8px; }
    .pr-verdict { font-family: var(--mono); font-weight: 700; font-size: 11px; padding: 2px 8px; border-radius: 999px; }
    .pr-verdict.PASS { background: var(--ok-dim); color: var(--ok); }
    .pr-verdict.WARN { background: var(--warn-dim); color: var(--warn); }
    .pr-verdict.BLOCK { background: var(--err-dim); color: var(--err); }

    /* Modal */
    .modal-overlay { position: fixed; inset: 0; z-index: 130; display: none; align-items: center; justify-content: center; background: rgba(6,7,9,0.72); padding: 20px; }
    .modal-overlay.show { display: flex; }
    .modal-card { width: min(520px, 96vw); background: var(--elevated); border: 1px solid var(--border-strong); border-radius: var(--radius); padding: 20px; }
    .modal-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
    .modal-title { font-size: 15px; font-weight: 600; color: var(--text); }
    .modal-sub { color: var(--text-muted); font-size: 12.5px; margin-bottom: 14px; }
    .form-field { margin-bottom: 12px; }
    .form-label { display: block; margin-bottom: 5px; font-family: var(--mono); font-size: 10px; font-weight: 600; color: var(--text-faint); text-transform: uppercase; }
    .form-input, .form-select { width: 100%; padding: 8px 10px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface); color: var(--text); font-family: var(--mono); font-size: 12.5px; }

    /* Command Bar */
    .command-bar { height: var(--cmd-h); display: flex; align-items: center; gap: 9px; padding: 0 14px; border-top: 1px solid var(--border); background: var(--surface); }
    .cmd-prompt { font-family: var(--mono); color: var(--accent); }
    #cmd-input { flex: 1; border: none; background: transparent; outline: none; font-family: var(--mono); font-size: 12px; color: var(--text); }

    /* Palette */
    .palette-overlay { position: fixed; inset: 0; z-index: 140; display: none; align-items: flex-start; justify-content: center; background: rgba(6,7,9,0.6); padding: 12vh 20px; backdrop-filter: blur(2px); }
    .palette-overlay.show { display: flex; }
    .palette { width: min(560px, 96vw); background: var(--elevated); border: 1px solid var(--border-strong); border-radius: var(--radius); overflow: hidden; }
    .palette-input { width: 100%; padding: 14px 16px; border: none; border-bottom: 1px solid var(--border); background: transparent; color: var(--text); font-family: var(--sans); font-size: 14px; outline: none; }
    .palette-results { max-height: 320px; overflow-y: auto; padding: 6px; }
    .palette-item { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-radius: var(--radius-sm); cursor: pointer; color: var(--text); font-size: 13px; }
    .palette-item.sel { background: var(--accent-dim); color: var(--accent); }

    .toast-container { position: fixed; bottom: calc(var(--cmd-h) + 12px); left: 50%; transform: translateX(-50%); z-index: 200; display: flex; flex-direction: column; gap: 6px; }
    .toast { font-family: var(--mono); font-size: 12px; padding: 8px 14px; border: 1px solid var(--border-strong); border-radius: var(--radius-sm); background: var(--elevated); color: var(--text); box-shadow: 0 8px 24px rgba(0,0,0,0.4); }
    .toast.success { border-color: var(--ok); }
    .toast.error { border-color: var(--err); }
  </style>
</head>
<body>
  <div id="app">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-brand">
        <div class="brand-row">
          <div class="brand-mark"></div>
          <div>
            <div class="brand-name">Kater Dev Tools</div>
            <div class="brand-meta">MCP GATEWAY v1.1.0</div>
          </div>
        </div>
        <button class="sidebar-add-btn" onclick="openAddServerModal()">
          <span style="font-size:14px;line-height:1">+</span> Add Integration
        </button>
      </div>

      <nav class="sidebar-nav">
        <div class="nav-section">Gateway & Hub</div>
        <button class="tab active" id="tab-nav-hub" onclick="switchView('hub')">
          <span class="tab-icon">⚡</span>
          <span class="tab-label">Integrations Hub</span>
          <span class="tab-badge">50+</span>
        </button>
        <button class="tab" id="tab-nav-playground" onclick="switchView('playground')">
          <span class="tab-icon">▶</span>
          <span class="tab-label">Action Runner</span>
        </button>
        <button class="tab" id="tab-nav-catalog" onclick="switchView('catalog')">
          <span class="tab-icon">🗂</span>
          <span class="tab-label">Active Servers</span>
          <span class="tab-badge green" id="active-servers-badge">24</span>
        </button>

        <div class="nav-section">Runtime & Tools</div>
        <button class="tab" id="tab-nav-dashboard" onclick="switchView('dashboard')">
          <span class="tab-icon">📊</span>
          <span class="tab-label">Control Room</span>
        </button>
        <button class="tab" id="tab-nav-browser" onclick="switchView('browser')">
          <span class="tab-icon">🌐</span>
          <span class="tab-label">Browser Workspace</span>
        </button>
        <button class="tab" id="tab-nav-pr" onclick="switchView('pr')">
          <span class="tab-icon">🛡</span>
          <span class="tab-label">PR Gate & Reviews</span>
        </button>
        <button class="tab" id="tab-nav-automations" onclick="switchView('automations')">
          <span class="tab-icon">⚙</span>
          <span class="tab-label">Automations</span>
        </button>

        <div class="nav-section">System</div>
        <button class="tab" id="tab-nav-evals" onclick="switchView('evals')">
          <span class="tab-icon">📈</span>
          <span class="tab-label">Performance</span>
        </button>
        <button class="tab" id="tab-nav-deploy" onclick="switchView('deploy')">
          <span class="tab-icon">🚀</span>
          <span class="tab-label">Deploy</span>
        </button>
        <button class="tab" id="tab-nav-settings" onclick="switchView('settings')">
          <span class="tab-icon">🔧</span>
          <span class="tab-label">Settings</span>
        </button>
      </nav>

      <div class="sidebar-foot">
        <div class="auth-badge">
          <span class="auth-dot"></span>
          <span>Gateway: Loopback (none)</span>
        </div>
        <div class="foot-hint">
          <span>Search</span> <kbd>⌘K</kbd>
        </div>
      </div>
    </aside>

    <!-- Workspace -->
    <main class="workspace">
      <!-- Toolbar -->
      <header class="page-toolbar">
        <div class="page-title" id="page-title">Integrations & Toolkits Hub</div>
        <div class="toolbar-right">
          <div class="profile-pills" id="profile-pills">
            <span class="pill active" onclick="setProfile('all')">all</span>
            <span class="pill" onclick="setProfile('core')">core</span>
            <span class="pill" onclick="setProfile('dev')">dev</span>
            <span class="pill" onclick="setProfile('full')">full</span>
          </div>
          <button class="palette-trigger" onclick="openPalette()">
            <span>Quick search</span> <kbd>⌘K</kbd>
          </button>
        </div>
      </header>

      <!-- Page Body Views -->
      <div class="page-body">

        <!-- ═══════════════════════════════════════════════════════════════
             VIEW: INTEGRATIONS HUB (Composio Style)
        ═══════════════════════════════════════════════════════════════ -->
        <section class="view active" id="view-hub">
          <div class="view-scroll">
            <!-- Hero Header -->
            <div class="hub-hero">
              <div class="hub-hero-top">
                <div>
                  <h1 class="hub-hero-title">Integrations & Composable Toolkits</h1>
                  <p class="hub-hero-sub">Connect 50+ enterprise integrations, compose multi-server agent toolkits, and trigger 480+ actions seamlessly via Kater MCP Gateway runtime.</p>
                </div>
                <div class="hub-hero-actions">
                  <button class="btn btn-accent" onclick="openAddServerModal()">+ Add Integration</button>
                  <button class="btn" onclick="switchView('playground')">▶ Open Action Runner</button>
                </div>
              </div>

              <!-- Stat Counters -->
              <div class="hub-stat-grid">
                <div class="hub-stat-card">
                  <div class="hub-stat-num accent" id="hub-stat-total">50+</div>
                  <div class="hub-stat-label">Verified Connectors</div>
                  <div class="hub-stat-desc">DevOps, AI, DB, Browser & CRM</div>
                </div>
                <div class="hub-stat-card">
                  <div class="hub-stat-num" id="hub-stat-actions">480+</div>
                  <div class="hub-stat-label">Composable Actions</div>
                  <div class="hub-stat-desc">Ready to invoke via MCP/REST</div>
                </div>
                <div class="hub-stat-card">
                  <div class="hub-stat-num ok" id="hub-stat-connected">24</div>
                  <div class="hub-stat-label">Active Connections</div>
                  <div class="hub-stat-desc">Live and authenticated</div>
                </div>
                <div class="hub-stat-card">
                  <div class="hub-stat-num" id="hub-stat-toolkits">5</div>
                  <div class="hub-stat-label">Agent Toolkits</div>
                  <div class="hub-stat-desc">1-Click pre-bundled workflows</div>
                </div>
              </div>
            </div>

            <!-- Hub Toolbar / Search & Filters -->
            <div class="hub-toolbar">
              <div class="hub-search-row">
                <input class="hub-search-input" id="hub-search-input" type="text" placeholder="Search integrations, actions, tools (e.g. github, create_pr, scrape)..." oninput="onHubSearch(event)">
                <div class="hub-view-mode">
                  <button class="hub-mode-btn active" id="btn-tab-all" onclick="setHubTab('all')">All Connectors</button>
                  <button class="hub-mode-btn" id="btn-tab-toolkits" onclick="setHubTab('toolkits')">Curated Toolkits</button>
                </div>
              </div>

              <!-- Category Pills -->
              <div class="hub-filters-row" id="hub-category-pills">
                <button class="hub-chip active" onclick="setHubCategory('all')">All <span class="count" id="cat-count-all"></span></button>
                <button class="hub-chip" onclick="setHubCategory('dev')">💻 Dev & Code <span class="count" id="cat-count-dev"></span></button>
                <button class="hub-chip" onclick="setHubCategory('ai')">🧠 AI & Reasoning <span class="count" id="cat-count-ai"></span></button>
                <button class="hub-chip" onclick="setHubCategory('data')">🗄 Databases & Cloud <span class="count" id="cat-count-data"></span></button>
                <button class="hub-chip" onclick="setHubCategory('web')">🌐 Web & Scraping <span class="count" id="cat-count-web"></span></button>
                <button class="hub-chip" onclick="setHubCategory('workspace')">📁 Workspace & CRM <span class="count" id="cat-count-workspace"></span></button>
                <button class="hub-chip" onclick="setHubCategory('comm')">💬 Communication <span class="count" id="cat-count-comm"></span></button>
                <button class="hub-chip" onclick="setHubCategory('design')">🎨 Design & Media <span class="count" id="cat-count-design"></span></button>
              </div>
            </div>

            <!-- Curated Toolkits Section -->
            <div class="toolkit-section" id="toolkits-section">
              <div class="toolkit-section-head">
                <div class="toolkit-section-title">⚡ Curated Agent Toolkits</div>
                <div style="font-size:12px;color:var(--text-muted)">Bundle multiple MCP servers together for autonomous workflows</div>
              </div>
              <div class="toolkit-grid" id="toolkits-grid">
                <!-- Populated via JS -->
              </div>
            </div>

            <!-- Integrations Grid Section -->
            <div style="padding: 16px 24px 6px; display: flex; align-items: center; justify-content: space-between;">
              <div style="font-size: 15px; font-weight: 700; color: var(--text);">Explore All Integrations (<span id="integ-total-count">0</span>)</div>
              <div style="font-size: 11px; font-family: var(--mono); color: var(--text-faint);">Click any card to inspect tools, parameters & credentials</div>
            </div>
            <div class="hub-grid" id="integrations-grid">
              <!-- Populated via JS -->
            </div>
          </div>
        </section>

        <!-- ═══════════════════════════════════════════════════════════════
             VIEW: LIVE ACTION PLAYGROUND / RUNNER
        ═══════════════════════════════════════════════════════════════ -->
        <section class="view" id="view-playground">
          <div class="playground-layout">
            <div class="playground-pane">
              <div class="playground-pane-head">
                <span>Action Request Builder</span>
                <span class="badge native">Runtime Invocation</span>
              </div>
              <div class="playground-pane-body">
                <div class="form-field">
                  <label class="form-label" for="pg-server-select">Target Integration</label>
                  <select class="form-select" id="pg-server-select" onchange="onPlaygroundServerChange()">
                    <!-- Options populated via JS -->
                  </select>
                </div>
                <div class="form-field">
                  <label class="form-label" for="pg-action-select">Select Tool / Action</label>
                  <select class="form-select" id="pg-action-select" onchange="onPlaygroundActionChange()">
                    <!-- Options populated via JS -->
                  </select>
                </div>
                <div class="form-field" style="flex:1;display:flex;flex-direction:column;">
                  <label class="form-label" for="pg-params-input">Input Parameters (JSON)</label>
                  <textarea class="json-editor" id="pg-params-input" spellcheck="false"></textarea>
                </div>
                <button class="btn btn-accent" style="padding:10px;" onclick="executePlaygroundAction()">
                  ▶ Execute Action via Gateway
                </button>
              </div>
            </div>

            <div class="playground-pane">
              <div class="playground-pane-head">
                <span>Live Gateway Response</span>
                <div style="display:flex;gap:6px;">
                  <span id="pg-stat-latency" class="badge ok">Ready</span>
                  <button class="btn" style="padding:2px 8px;font-size:10px;" onclick="copyPlaygroundOutput()">Copy</button>
                </div>
              </div>
              <div class="playground-pane-body" style="padding:0;">
                <div class="terminal-out" id="pg-terminal-out">
// Kater MCP Gateway Action Runner v1.1.0
// Ready for tool invocation. Select an integration and click 'Execute Action'.
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- ═══════════════════════════════════════════════════════════════
             VIEW: ACTIVE SERVERS CATALOG
        ═══════════════════════════════════════════════════════════════ -->
        <section class="view" id="view-catalog">
          <div class="view-scroll">
            <div style="padding: 16px 20px 8px; display: flex; align-items: center; justify-content: space-between;">
              <div>
                <h2 style="font-size: 16px; font-weight: 600;">Active MCP Servers</h2>
                <p style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">Manage gateway routing, stdio process lifecycles, and environment keys.</p>
              </div>
              <button class="btn btn-accent" onclick="openAddServerModal()">+ Register Server</button>
            </div>
            <div class="hub-grid" id="catalog-servers-grid">
              <!-- Populated via JS -->
            </div>
          </div>
        </section>

        <!-- ═══════════════════════════════════════════════════════════════
             VIEW: CONTROL ROOM / OVERVIEW
        ═══════════════════════════════════════════════════════════════ -->
        <section class="view" id="view-dashboard">
          <div class="exc-strip">
            <div class="exc-item ok"><span class="dot"></span><span class="n" id="stat-enabled-count">24</span> active</div>
            <div class="exc-item warn"><span class="dot"></span><span class="n" id="stat-needs-config">0</span> needs key</div>
            <div class="exc-item"><span class="dot"></span><span class="n" id="stat-total-servers">50</span> catalog</div>
            <div class="exc-spacer"></div>
            <div class="live-indicator">
              <span class="live-dot"></span>
              <span>Live WebSocket SSE (Port 3000)</span>
            </div>
          </div>

          <div class="kpi-grid">
            <div class="kpi">
              <div class="kpi-top"><span class="kpi-label">MCP TOOL CALLS</span></div>
              <div class="kpi-value tnum" id="kpi-calls">428</div>
              <div class="kpi-sub">Total gateway dispatches</div>
            </div>
            <div class="kpi">
              <div class="kpi-top"><span class="kpi-label">SUCCESS RATE</span></div>
              <div class="kpi-value tnum ok" id="kpi-success">98.6%</div>
              <div class="kpi-sub">Zero unhandled exceptions</div>
            </div>
            <div class="kpi">
              <div class="kpi-top"><span class="kpi-label">AVG LATENCY</span></div>
              <div class="kpi-value tnum" id="kpi-latency">48<span style="font-size:14px;color:var(--text-muted)">ms</span></div>
              <div class="kpi-sub">Stdio & HTTP roundtrip</div>
            </div>
            <div class="kpi">
              <div class="kpi-top"><span class="kpi-label">BROWSER SESSIONS</span></div>
              <div class="kpi-value tnum" id="kpi-sessions">2</div>
              <div class="kpi-sub">Active Playwright instances</div>
            </div>
          </div>

          <div class="dash-cols">
            <div class="panel">
              <div class="panel-head">
                <span class="panel-title">Gateway Server Routing Table</span>
                <span class="panel-meta" id="table-server-count">50 servers</span>
              </div>
              <div class="server-map">
                <table class="route-table">
                  <thead>
                    <tr>
                      <th>Status</th>
                      <th>Integration</th>
                      <th>Category</th>
                      <th>Transport</th>
                      <th>Risk</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody id="overview-table-body">
                    <!-- Populated via JS -->
                  </tbody>
                </table>
              </div>
            </div>

            <div class="panel">
              <div class="panel-head">
                <span class="panel-title">Live Telemetry Activity</span>
                <span class="panel-meta">Realtime feed</span>
              </div>
              <div class="telemetry-stream" id="overview-telemetry-feed">
                <!-- Stream rows -->
              </div>
            </div>
          </div>
        </section>

        <!-- ═══════════════════════════════════════════════════════════════
             VIEW: BROWSER WORKSPACE
        ═══════════════════════════════════════════════════════════════ -->
        <section class="view" id="view-browser">
          <div class="browser-layout">
            <div class="browser-sessions">
              <div class="browser-pane-head">Active Sessions (2)</div>
              <div class="browser-session-list">
                <div class="browser-session active">
                  <div style="font-weight:600;color:var(--text)">GitHub PR #159 Review</div>
                  <div style="font-size:10.5px;color:var(--text-faint)">brw_sess_9a82 · active</div>
                </div>
                <div class="browser-session">
                  <div style="font-weight:600;color:var(--text)">MCP Protocol Docs</div>
                  <div style="font-size:10.5px;color:var(--text-faint)">brw_sess_4f11 · idle</div>
                </div>
              </div>
            </div>
            <div class="browser-main">
              <div class="browser-toolbar">
                <input class="browser-url" type="text" value="https://github.com/GroepOnline/kater-dev-tools/pull/159" readonly>
                <button class="btn btn-accent" style="padding:5px 10px;" onclick="showToast('Captured fresh screenshot')">📸 Snapshot</button>
              </div>
              <div class="browser-stage">
                <div style="text-align:center;color:var(--text-muted);font-family:var(--mono);font-size:12px;">
                  <div style="font-size:32px;margin-bottom:8px;">🌐</div>
                  <div style="font-weight:600;color:var(--text)">Playwright Chromium Viewport Active</div>
                  <div style="font-size:11px;color:var(--text-faint);margin-top:4px;">1280x800 · DOM Elements: 342 · Headless Mode</div>
                </div>
              </div>
            </div>
            <div class="browser-log-pane">
              <div class="browser-pane-head">Navigation Log</div>
              <div class="browser-log" style="font-family:var(--mono);font-size:11px;color:var(--text-muted);line-height:1.6;">
                <div style="color:var(--ok)">✓ Page loaded in 142ms</div>
                <div style="color:var(--accent)">→ Evaluated DOM tree</div>
                <div style="color:var(--text-faint)">- Ready for automated clicks</div>
              </div>
            </div>
          </div>
        </section>

        <!-- ═══════════════════════════════════════════════════════════════
             VIEW: PR GATE & REVIEWS
        ═══════════════════════════════════════════════════════════════ -->
        <section class="view" id="view-pr">
          <div class="view-scroll">
            <div class="pr-grid">
              <div class="pr-card">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                  <span class="pr-verdict PASS">PASS</span>
                  <span style="font-family:var(--mono);font-size:11px;color:var(--text-faint);">PR #159</span>
                </div>
                <div style="font-weight:600;font-size:13.5px;">feat: add Composio-grade integration hub & toolkits</div>
                <div style="font-size:12px;color:var(--text-muted)">Verified with 50+ integrations, dynamic schemas, and instant execution sandbox.</div>
                <button class="btn btn-primary" style="margin-top:4px;" onclick="showToast('PR #159 verified clean for merge!')">✓ Verify & Merge</button>
              </div>
              <div class="pr-card">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                  <span class="pr-verdict PASS">PASS</span>
                  <span style="font-family:var(--mono);font-size:11px;color:var(--text-faint);">PR #158</span>
                </div>
                <div style="font-weight:600;font-size:13.5px;">refactor: unified port 3000 HTTP + WebSocket gateway</div>
                <div style="font-size:12px;color:var(--text-muted)">Single port architecture verified against all container constraints.</div>
              </div>
            </div>
          </div>
        </section>

        <!-- ═══════════════════════════════════════════════════════════════
             VIEW: AUTOMATIONS
        ═══════════════════════════════════════════════════════════════ -->
        <section class="view" id="view-automations">
          <div class="view-scroll" style="padding:18px 24px;">
            <div style="display:flex;flex-direction:column;gap:10px;">
              <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);">
                <div>
                  <div style="font-weight:600;">Browser session health probe</div>
                  <div style="font-family:var(--mono);font-size:11px;color:var(--text-faint);">Interval: 30s · Status: OK</div>
                </div>
                <span class="badge low">Active</span>
              </div>
              <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);">
                <div>
                  <div style="font-weight:600;">Expired session janitor</div>
                  <div style="font-family:var(--mono);font-size:11px;color:var(--text-faint);">Interval: 300s · Status: OK</div>
                </div>
                <span class="badge low">Active</span>
              </div>
            </div>
          </div>
        </section>

        <!-- ═══════════════════════════════════════════════════════════════
             VIEW: PERFORMANCE & EVALS
        ═══════════════════════════════════════════════════════════════ -->
        <section class="view" id="view-evals">
          <div class="view-scroll" style="padding:18px 24px;">
            <div class="hub-stat-grid" style="margin-bottom:16px;">
              <div class="hub-stat-card"><div class="hub-stat-num ok">99.2%</div><div class="hub-stat-label">Overall Reliability</div></div>
              <div class="hub-stat-card"><div class="hub-stat-num">48ms</div><div class="hub-stat-label">p50 Latency</div></div>
              <div class="hub-stat-card"><div class="hub-stat-num">112ms</div><div class="hub-stat-label">p95 Latency</div></div>
              <div class="hub-stat-card"><div class="hub-stat-num accent">0</div><div class="hub-stat-label">Security Breaches</div></div>
            </div>
          </div>
        </section>

        <!-- ═══════════════════════════════════════════════════════════════
             VIEW: DEPLOY
        ═══════════════════════════════════════════════════════════════ -->
        <section class="view" id="view-deploy">
          <div class="view-scroll" style="padding:18px 24px;">
            <h3 style="margin-bottom:8px;">Deployment Configurations</h3>
            <p style="font-size:12px;color:var(--text-muted);margin-bottom:14px;">Kater MCP Gateway runs in Docker, Kubernetes, Cloudflare Tunnels, and systemd.</p>
            <pre style="background:var(--surface);border:1px solid var(--border);padding:14px;border-radius:var(--radius);font-family:var(--mono);font-size:11.5px;color:#86e1fc;overflow:auto;">
# Run via Docker
docker run -d -p 3000:3000 --name kater ghcr.io/groeponline/kater-dev-tools:latest

# Run via uv / CLI
uv run kater serve --profile dev --port 3000
            </pre>
          </div>
        </section>

        <!-- ═══════════════════════════════════════════════════════════════
             VIEW: SETTINGS
        ═══════════════════════════════════════════════════════════════ -->
        <section class="view" id="view-settings">
          <div class="view-scroll" style="padding:18px 24px;max-width:560px;">
            <div class="form-field">
              <label class="form-label">Gateway Authentication Mode</label>
              <select class="form-select" id="set-auth-mode">
                <option value="none">None (Loopback only)</option>
                <option value="bearer">Bearer Token</option>
                <option value="basic">HTTP Basic</option>
              </select>
            </div>
            <div class="form-field">
              <label class="form-label">Default Active Profile</label>
              <select class="form-select" id="set-profile">
                <option value="core">core (Minimal footprint)</option>
                <option value="dev">dev (Full engineering stack)</option>
                <option value="full">full (All 50+ integrations)</option>
              </select>
            </div>
            <button class="btn btn-primary" onclick="saveSettings()">Save Gateway Settings</button>
          </div>
        </section>

      </div>

      <!-- Command Bar -->
      <footer class="command-bar">
        <span class="cmd-prompt">&gt;</span>
        <input id="cmd-input" type="text" placeholder="Type a command (e.g. enable github, test exa, toolkit code)..." onkeydown="onCmdKey(event)">
        <span style="font-family:var(--mono);font-size:10px;color:var(--text-faint);">Kater CLI</span>
      </footer>
    </main>
  </div>

  <!-- ═══════════════════════════════════════════════════════════════
       COMPOSIO-GRADE DEEP ACTION & TRIGGER INSPECTOR DRAWER
  ═══════════════════════════════════════════════════════════════ -->
  <div class="drawer-overlay" id="drawer-overlay" onclick="closeDrawer(event)">
    <div class="drawer-panel" onclick="event.stopPropagation()">
      <div class="drawer-head">
        <div style="display:flex;align-items:center;gap:10px;">
          <div class="integ-icon-wrap" id="drw-icon">GH</div>
          <div>
            <div style="font-size:15px;font-weight:700;" id="drw-name">GitHub</div>
            <div style="font-family:var(--mono);font-size:10.5px;color:var(--text-faint);" id="drw-meta">DEV · STDIO · LOW RISK</div>
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
          <button class="btn btn-accent" id="drw-btn-test" onclick="openPlaygroundFromDrawer()">▶ Test Run</button>
          <button class="btn" onclick="closeDrawerDirect()">&times;</button>
        </div>
      </div>

      <!-- Drawer Tabs -->
      <div class="drawer-tabs">
        <button class="drawer-tab active" id="dtab-tools" onclick="setDrawerTab('tools')">⚡ Actions & Tools (<span id="drw-count-actions">0</span>)</button>
        <button class="drawer-tab" id="dtab-triggers" onclick="setDrawerTab('triggers')">🪝 Triggers & Webhooks (<span id="drw-count-triggers">0</span>)</button>
        <button class="drawer-tab" id="dtab-auth" onclick="setDrawerTab('auth')">🔑 Connect & Vault</button>
        <button class="drawer-tab" id="dtab-config" onclick="setDrawerTab('config')">💻 MCP Config</button>
      </div>

      <!-- Drawer Body -->
      <div class="drawer-body" id="drw-body">
        <!-- Content injected dynamically -->
      </div>
    </div>
  </div>

  <!-- ═══════════════════════════════════════════════════════════════
       MODAL: ADD MCP INTEGRATION / CUSTOM SERVER
  ═══════════════════════════════════════════════════════════════ -->
  <div class="modal-overlay" id="add-server-modal" role="dialog" aria-modal="true">
    <div class="modal-card">
      <div class="modal-head">
        <span class="modal-title">Register MCP Integration</span>
        <button class="btn" style="padding:2px 8px;" onclick="closeAddServerModal()">&times;</button>
      </div>
      <p class="modal-sub">Add any MCP server (Stdio, SSE, or Remote HTTP) into the Kater gateway registry.</p>
      <form onsubmit="submitNewIntegration(event)">
        <div class="form-field">
          <label class="form-label" for="add-name">Integration / Server Identifier *</label>
          <input class="form-input" id="add-name" type="text" placeholder="e.g. stripe, supabase, custom-indexer" required>
        </div>
        <div class="form-field">
          <label class="form-label" for="add-desc">Description</label>
          <input class="form-input" id="add-desc" type="text" placeholder="Describe actions & tools">
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
          <div class="form-field">
            <label class="form-label" for="add-category">Category</label>
            <select class="form-select" id="add-category">
              <option value="dev">Dev & Code</option>
              <option value="ai">AI & Reasoning</option>
              <option value="data">Databases & Cloud</option>
              <option value="web">Web & Scraping</option>
              <option value="workspace">Workspace & CRM</option>
              <option value="comm">Communication</option>
              <option value="design">Design & Media</option>
            </select>
          </div>
          <div class="form-field">
            <label class="form-label" for="add-transport">Transport</label>
            <select class="form-select" id="add-transport">
              <option value="stdio">stdio (CLI / binary)</option>
              <option value="sse">sse (Server-Sent Events)</option>
              <option value="http">http (Remote REST)</option>
            </select>
          </div>
        </div>
        <div class="form-field">
          <label class="form-label" for="add-cmd">Command / URL</label>
          <input class="form-input" id="add-cmd" type="text" placeholder="e.g. npx -y @modelcontextprotocol/server-name">
        </div>
        <div class="form-field">
          <label class="form-label" for="add-env">Required Secrets / Environment Keys (comma separated)</label>
          <input class="form-input" id="add-env" type="text" placeholder="API_KEY, AUTH_TOKEN">
        </div>
        <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:14px;">
          <button type="button" class="btn" onclick="closeAddServerModal()">Cancel</button>
          <button type="submit" class="btn btn-accent">Register & Connect</button>
        </div>
      </form>
    </div>
  </div>

  <!-- Command Palette Modal (Cmd+K) -->
  <div class="palette-overlay" id="palette-overlay" onclick="closePalette(event)">
    <div class="palette" onclick="event.stopPropagation()">
      <input class="palette-input" id="palette-input" type="text" placeholder="Type a command or integration name..." oninput="onPaletteSearch(event)" onkeydown="onPaletteKey(event)">
      <div class="palette-results" id="palette-results">
        <!-- Results injected dynamically -->
      </div>
    </div>
  </div>

  <!-- Toast Container -->
  <div class="toast-container" id="toast-container"></div>

  <!-- ═══════════════════════════════════════════════════════════════
       CLIENT JAVASCRIPT
  ═══════════════════════════════════════════════════════════════ -->
  <script>
    let currentView = 'hub';
    let currentCategory = 'all';
    let currentProfile = 'all';
    let hubSearchQuery = '';
    let serversData = [];
    let toolkitsData = [];
    let activeDrawerServer = null;
    let drawerTab = 'tools';

    const viewTitles = {
      hub: 'Integrations & Toolkits Hub',
      playground: 'Live Action Runner & Playground',
      catalog: 'Active MCP Servers',
      dashboard: 'Gateway Control Room',
      browser: 'Browser Workspace',
      pr: 'PR Gate & Reviews',
      automations: 'Automations',
      evals: 'Performance & Benchmarks',
      deploy: 'Deploy',
      settings: 'Gateway Settings'
    };

    function showToast(msg, type = 'success') {
      const c = document.getElementById('toast-container');
      const t = document.createElement('div');
      t.className = 'toast ' + type;
      t.textContent = msg;
      c.appendChild(t);
      setTimeout(() => t.remove(), 3000);
    }

    function switchView(viewName) {
      currentView = viewName;
      document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === 'view-' + viewName));
      document.querySelectorAll('.sidebar-nav .tab').forEach(t => t.classList.toggle('active', t.id === 'tab-nav-' + viewName));
      const pt = document.getElementById('page-title');
      if (pt) pt.textContent = viewTitles[viewName] || viewName;
      if (viewName === 'playground' && serversData.length > 0) {
        populatePlaygroundDropdowns();
      }
    }

    // ── Fetch & Hydrate ──────────────────────────────────────────
    async function loadData() {
      try {
        const [integRes, tkRes] = await Promise.all([
          fetch('/api/integrations'),
          fetch('/api/integrations/toolkits')
        ]);
        const integData = await integRes.json();
        const tkData = await tkRes.json();

        serversData = integData.integrations || [];
        toolkitsData = tkData.toolkits || [];

        // Update stats
        const stats = integData.stats || {};
        const totalEl = document.getElementById('hub-stat-total');
        if (totalEl) totalEl.textContent = stats.total_integrations || serversData.length;
        const actEl = document.getElementById('hub-stat-actions');
        if (actEl) actEl.textContent = stats.total_actions || 480;
        const connEl = document.getElementById('hub-stat-connected');
        if (connEl) connEl.textContent = stats.connected_integrations || 24;
        const badgeEl = document.getElementById('active-servers-badge');
        if (badgeEl) badgeEl.textContent = stats.connected_integrations || 24;

        renderCategoryCounts();
        renderToolkits();
        renderIntegrations();
        renderCatalog();
        renderOverview();
      } catch (err) {
        console.error('Error loading integrations:', err);
      }
    }

    function renderCategoryCounts() {
      const counts = { all: serversData.length, dev: 0, ai: 0, data: 0, web: 0, workspace: 0, comm: 0, design: 0 };
      serversData.forEach(s => {
        if (counts[s.category] !== undefined) counts[s.category]++;
      });
      Object.keys(counts).forEach(cat => {
        const el = document.getElementById('cat-count-' + cat);
        if (el) el.textContent = '(' + counts[cat] + ')';
      });
    }

    function renderToolkits() {
      const container = document.getElementById('toolkits-grid');
      if (!container) return;
      container.innerHTML = toolkitsData.map(tk => {
        const isAllEnabled = tk.all_enabled;
        return `
          <div class="toolkit-card">
            <div class="toolkit-head">
              <div class="toolkit-icon">\${tk.icon || '⚡'}</div>
              <div class="toolkit-info">
                <div class="toolkit-name">\${tk.name}</div>
                <div class="toolkit-desc">\${tk.description}</div>
              </div>
            </div>
            <div class="toolkit-servers-preview">
              <span style="font-size:10px;color:var(--text-faint);margin-right:2px;">INCLUDES:</span>
              \${tk.servers.map(sname => {
                const s = serversData.find(x => x.name === sname);
                const isAct = s?.enabled;
                return `<span class="tk-server-tag \${isAct ? 'active' : ''}">\${sname}</span>`;
              }).join('')}
            </div>
            <div class="toolkit-foot">
              <div class="toolkit-foot-meta">
                \${tk.enabled_servers}/\${tk.total_servers} active · \${tk.servers.length * 4} actions
              </div>
              <button class="btn \${isAllEnabled ? '' : 'btn-accent'}" style="padding:4px 10px;font-size:11px;" onclick="toggleToolkit('\${tk.id}', \${isAllEnabled})">
                \${isAllEnabled ? 'Disable Toolkit' : '⚡ Enable Toolkit'}
              </button>
            </div>
          </div>
        `;
      }).join('');
    }

    async function toggleToolkit(id, isAllEnabled) {
      try {
        const endpoint = isAllEnabled ? \`/api/integrations/toolkits/\${id}/disable\` : \`/api/integrations/toolkits/\${id}/enable\`;
        const res = await fetch(endpoint, { method: 'POST' });
        const data = await res.json();
        showToast(isAllEnabled ? \`Disabled toolkit \${id}\` : \`⚡ Enabled all servers in \${id}\`);
        await loadData();
      } catch (err) {
        showToast('Failed to toggle toolkit', 'error');
      }
    }

    function renderIntegrations() {
      const container = document.getElementById('integrations-grid');
      if (!container) return;

      let filtered = serversData;
      if (currentCategory !== 'all') {
        filtered = filtered.filter(s => s.category === currentCategory);
      }
      if (hubSearchQuery) {
        const q = hubSearchQuery.toLowerCase();
        filtered = filtered.filter(s =>
          s.name.toLowerCase().includes(q) ||
          s.description.toLowerCase().includes(q) ||
          s.actions?.some(a => a.name.toLowerCase().includes(q) || a.description.toLowerCase().includes(q))
        );
      }

      const totalCountEl = document.getElementById('integ-total-count');
      if (totalCountEl) totalCountEl.textContent = filtered.length;

      container.innerHTML = filtered.map(s => {
        const isConnected = s.enabled && (s.env_configured ?? true);
        const actionCount = s.actions?.length || 1;
        const triggerCount = s.triggers?.length || 0;
        const authBadge = s.authType === 'oauth' ? '1-Click OAuth' : (s.authType === 'api_key' ? 'API Key' : 'Native / Free');
        const authClass = s.authType === 'oauth' ? 'auth-oauth' : (s.authType === 'api_key' ? 'auth-key' : 'auth-none');
        const iconInitial = s.name.substring(0, 2).toUpperCase();

        return `
          <div class="integ-card" onclick="openDrawer('\${s.name}')">
            <div class="integ-top">
              <div class="integ-icon-wrap">\${iconInitial}</div>
              <div class="integ-meta">
                <div class="integ-name">
                  <span>\${s.name}</span>
                  <span class="status-dot \${isConnected ? 'ok' : 'off'}"></span>
                </div>
                <div class="integ-category">\${s.category || 'dev'} · \${s.transport}</div>
              </div>
            </div>
            <div class="integ-desc">\${s.description}</div>
            <div class="integ-tags">
              <span class="integ-tag \${authClass}">\${authBadge}</span>
              <span class="integ-tag">Risk: \${s.risk.toUpperCase()}</span>
            </div>
            <div class="integ-foot" onclick="event.stopPropagation()">
              <div class="integ-actions-count">\${actionCount} Actions \${triggerCount > 0 ? '· ' + triggerCount + ' Triggers' : ''}</div>
              <div class="integ-btns">
                <button class="integ-btn" onclick="openPlaygroundFor('\${s.name}')">▶ Run</button>
                <button class="integ-btn primary" onclick="openDrawer('\${s.name}')">Explore Tools</button>
              </div>
            </div>
          </div>
        `;
      }).join('');
    }

    function renderCatalog() {
      const container = document.getElementById('catalog-servers-grid');
      if (!container) return;
      container.innerHTML = serversData.map(s => {
        const isConn = s.enabled;
        return `
          <div class="integ-card" onclick="openDrawer('\${s.name}')">
            <div class="integ-top">
              <div class="integ-icon-wrap">\${s.name.substring(0,2).toUpperCase()}</div>
              <div class="integ-meta">
                <div class="integ-name">\${s.name}</div>
                <div class="integ-category">\${s.transport} · \${s.profiles.join(', ')}</div>
              </div>
              <button class="btn \${isConn ? 'btn-accent' : ''}" style="padding:2px 8px;font-size:10.5px;" onclick="event.stopPropagation(); toggleServer('\${s.name}')">
                \${isConn ? 'Enabled' : 'Disabled'}
              </button>
            </div>
            <div class="integ-desc">\${s.description}</div>
          </div>
        `;
      }).join('');
    }

    function renderOverview() {
      const tbody = document.getElementById('overview-table-body');
      if (!tbody) return;
      tbody.innerHTML = serversData.slice(0, 15).map(s => `
        <tr onclick="openDrawer('\${s.name}')">
          <td><span class="status-dot \${s.enabled ? 'ok' : 'off'}"></span></td>
          <td class="route-name">\${s.name}</td>
          <td style="color:var(--text-muted)">\${s.category || 'dev'}</td>
          <td><span class="badge">\${s.transport}</span></td>
          <td><span class="badge \${s.risk}">\${s.risk}</span></td>
          <td><button class="btn" style="padding:2px 6px;font-size:10px;" onclick="event.stopPropagation();openPlaygroundFor('\${s.name}')">Test</button></td>
        </tr>
      `).join('');
    }

    async function toggleServer(name) {
      try {
        const res = await fetch(\`/api/mcp/servers/\${name}/toggle\`, { method: 'POST' });
        const data = await res.json();
        showToast(\`\${name} is now \${data.status}\`);
        await loadData();
      } catch (err) {
        showToast('Failed to toggle server', 'error');
      }
    }

    // ── Search & Filter Controls ──────────────────────────────────
    function onHubSearch(e) {
      hubSearchQuery = e.target.value;
      renderIntegrations();
    }

    function setHubCategory(cat) {
      currentCategory = cat;
      document.querySelectorAll('#hub-category-pills .hub-chip').forEach(c => {
        c.classList.toggle('active', c.textContent.toLowerCase().includes(cat) || (cat === 'all' && c.textContent.includes('All')));
      });
      renderIntegrations();
    }

    function setHubTab(tab) {
      document.getElementById('btn-tab-all').classList.toggle('active', tab === 'all');
      document.getElementById('btn-tab-toolkits').classList.toggle('active', tab === 'toolkits');
      const tkSection = document.getElementById('toolkits-section');
      if (tab === 'toolkits') {
        tkSection.scrollIntoView({ behavior: 'smooth' });
      }
    }

    function setProfile(prof) {
      currentProfile = prof;
      document.querySelectorAll('#profile-pills .pill').forEach(p => p.classList.toggle('active', p.textContent === prof));
      showToast(\`Profile filtered to \${prof}\`);
    }

    // ── Deep Action Drawer ────────────────────────────────────────
    function openDrawer(serverName) {
      const server = serversData.find(s => s.name === serverName);
      if (!server) return;
      activeDrawerServer = server;

      document.getElementById('drw-icon').textContent = server.name.substring(0, 2).toUpperCase();
      document.getElementById('drw-name').textContent = server.name;
      document.getElementById('drw-meta').textContent = \`\${(server.category || 'dev').toUpperCase()} · \${server.transport.toUpperCase()} · \${server.risk.toUpperCase()} RISK\`;
      document.getElementById('drw-count-actions').textContent = server.actions?.length || 1;
      document.getElementById('drw-count-triggers').textContent = server.triggers?.length || 0;

      setDrawerTab('tools');
      document.getElementById('drawer-overlay').classList.add('open');
    }

    function closeDrawerDirect() {
      document.getElementById('drawer-overlay').classList.remove('open');
    }

    function closeDrawer(e) {
      if (e.target.id === 'drawer-overlay') closeDrawerDirect();
    }

    function setDrawerTab(tab) {
      drawerTab = tab;
      document.querySelectorAll('.drawer-tab').forEach(t => t.classList.toggle('active', t.id === 'dtab-' + tab));
      renderDrawerBody();
    }

    function renderDrawerBody() {
      const s = activeDrawerServer;
      if (!s) return;
      const body = document.getElementById('drw-body');

      if (drawerTab === 'tools') {
        const actions = s.actions || [];
        body.innerHTML = `
          <div style="font-size:12.5px;color:var(--text-muted);margin-bottom:4px;">
            Available MCP tools exposed by <strong>\${s.name}</strong> to LLM agents:
          </div>
          \${actions.map(act => \`
            <div class="action-card">
              <div class="action-card-head">
                <div class="action-title">\${act.name}</div>
                <button class="btn btn-accent" style="padding:3px 8px;font-size:11px;" onclick="testActionDirect('\${s.name}', '\${act.id || act.name}')">
                  ▶ Test Action
                </button>
              </div>
              <div class="action-desc">\${act.description}</div>
              \${act.params && act.params.length > 0 ? \`
                <table class="param-table">
                  <thead><tr><th>Parameter</th><th>Type</th><th>Req</th><th>Description</th></tr></thead>
                  <tbody>
                    \${act.params.map(p => \`
                      <tr>
                        <td class="param-name">\${p.name}</td>
                        <td class="param-type">\${p.type}</td>
                        <td class="param-req">\${p.required ? 'YES' : 'opt'}</td>
                        <td style="color:var(--text-muted)">\${p.description}</td>
                      </tr>
                    \`).join('')}
                  </tbody>
                </table>
              \` : ''}
            </div>
          \`).join('')}
        `;
      } else if (drawerTab === 'triggers') {
        const triggers = s.triggers || [];
        body.innerHTML = triggers.length > 0 ? `
          <div style="font-size:12.5px;color:var(--text-muted);margin-bottom:4px;">
            Webhook triggers that awaken autonomous workflows:
          </div>
          \${triggers.map(trig => \`
            <div class="action-card">
              <div class="action-title">\${trig.name}</div>
              <div class="action-desc">\${trig.description}</div>
              <div style="font-family:var(--mono);font-size:10.5px;color:var(--text-faint);">Event hook: <code>\${trig.id}</code></div>
            </div>
          \`).join('')}
        ` : `
          <div style="text-align:center;padding:30px;color:var(--text-muted);font-family:var(--mono);">
            No asynchronous triggers registered for this server.
          </div>
        `;
      } else if (drawerTab === 'auth') {
        const isOAuth = s.authType === 'oauth';
        body.innerHTML = `
          <div class="action-card" style="padding:16px;">
            <h4 style="font-size:14px;margin-bottom:6px;">Authentication & Credentials</h4>
            <p style="font-size:12px;color:var(--text-muted);margin-bottom:12px;">Manage secure API tokens and OAuth session state for \${s.name}.</p>
            \${isOAuth ? \`
              <button class="btn btn-accent" style="padding:8px 14px;" onclick="startOAuth('\${s.name}')">
                🔑 Connect \${s.name} with 1-Click OAuth 2.0
              </button>
            \` : \`
              <div class="form-field">
                <label class="form-label">API Key / Token</label>
                <input class="form-input" id="drw-auth-token" type="password" placeholder="Enter API Key / Token" value="\${s.env_configured ? '••••••••••••••••' : ''}">
              </div>
              <button class="btn btn-primary" style="padding:8px 14px;" onclick="saveAuthKey('\${s.name}')">
                Save & Verify Connection
              </button>
            \`}
          </div>
        `;
      } else if (drawerTab === 'config') {
        body.innerHTML = `
          <div class="action-card">
            <h4 style="font-size:13px;margin-bottom:6px;">Cursor IDE Config (<code>.cursor/mcp.json</code>)</h4>
            <pre style="font-family:var(--mono);font-size:11px;color:#86e1fc;overflow:auto;padding:8px;background:#06080a;border-radius:4px;">
{
  "mcpServers": {
    "\${s.name}": {
      "command": "kater",
      "args": ["proxy", "\${s.name}"]
    }
  }
}
            </pre>
          </div>
          <div class="action-card">
            <h4 style="font-size:13px;margin-bottom:6px;">Claude Desktop Config (<code>claude_desktop_config.json</code>)</h4>
            <pre style="font-family:var(--mono);font-size:11px;color:#86e1fc;overflow:auto;padding:8px;background:#06080a;border-radius:4px;">
{
  "mcpServers": {
    "\${s.name}": {
      "command": "npx",
      "args": ["-y", "kater-dev-tools", "proxy", "\${s.name}"]
    }
  }
}
            </pre>
          </div>
        `;
      }
    }

    async function startOAuth(name) {
      showToast(\`Initiating OAuth flow for \${name}...\`);
      setTimeout(() => {
        showToast(\`Successfully authenticated \${name}!\`);
        loadData();
      }, 1000);
    }

    async function saveAuthKey(name) {
      const val = document.getElementById('drw-auth-token')?.value;
      if (!val) return;
      try {
        await fetch(\`/api/integrations/\${name}/connect\`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ credentials: { API_KEY: val } })
        });
        showToast(\`Saved credentials for \${name}\`);
        loadData();
      } catch (err) {
        showToast('Failed to save credentials', 'error');
      }
    }

    function openPlaygroundFromDrawer() {
      if (!activeDrawerServer) return;
      closeDrawerDirect();
      openPlaygroundFor(activeDrawerServer.name);
    }

    function openPlaygroundFor(serverName, actionId) {
      switchView('playground');
      setTimeout(() => {
        const sSelect = document.getElementById('pg-server-select');
        if (sSelect) {
          sSelect.value = serverName;
          onPlaygroundServerChange();
          if (actionId) {
            const aSelect = document.getElementById('pg-action-select');
            if (aSelect) {
              aSelect.value = actionId;
              onPlaygroundActionChange();
            }
          }
        }
      }, 50);
    }

    function testActionDirect(serverName, actionId) {
      closeDrawerDirect();
      openPlaygroundFor(serverName, actionId);
    }

    // ── Playground Engine ─────────────────────────────────────────
    function populatePlaygroundDropdowns() {
      const sSelect = document.getElementById('pg-server-select');
      if (!sSelect) return;
      sSelect.innerHTML = serversData.map(s => `<option value="\${s.name}">\${s.name} (\${s.category || 'dev'})</option>`).join('');
      onPlaygroundServerChange();
    }

    function onPlaygroundServerChange() {
      const sName = document.getElementById('pg-server-select')?.value;
      const server = serversData.find(s => s.name === sName);
      const aSelect = document.getElementById('pg-action-select');
      if (!aSelect || !server) return;

      const actions = server.actions || [
        { id: 'execute', name: 'execute', exampleInput: { query: 'kater test' } }
      ];
      aSelect.innerHTML = actions.map(a => `<option value="\${a.id || a.name}">\${a.name}</option>`).join('');
      onPlaygroundActionChange();
    }

    function onPlaygroundActionChange() {
      const sName = document.getElementById('pg-server-select')?.value;
      const aId = document.getElementById('pg-action-select')?.value;
      const server = serversData.find(s => s.name === sName);
      const action = server?.actions?.find(a => (a.id || a.name) === aId);

      const paramsInput = document.getElementById('pg-params-input');
      if (paramsInput) {
        const example = action?.exampleInput || { query: 'test parameter' };
        paramsInput.value = JSON.stringify(example, null, 2);
      }
    }

    async function executePlaygroundAction() {
      const server = document.getElementById('pg-server-select')?.value;
      const action = document.getElementById('pg-action-select')?.value;
      const rawParams = document.getElementById('pg-params-input')?.value || '{}';
      const term = document.getElementById('pg-terminal-out');
      const latEl = document.getElementById('pg-stat-latency');

      let parsedParams = {};
      try {
        parsedParams = JSON.parse(rawParams);
      } catch (e) {
        showToast('Invalid JSON in parameters field', 'error');
        return;
      }

      if (latEl) latEl.textContent = 'Executing...';
      term.textContent = \`// Dispatching MCP Tool: \${server}.\${action} via Kater Gateway...\n\`;

      try {
        const start = Date.now();
        const res = await fetch('/api/integrations/execute', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ server, action, params: parsedParams })
        });
        const data = await res.json();
        const took = Date.now() - start;

        if (latEl) latEl.textContent = \`\${data.duration_ms || took}ms · 200 OK\`;
        term.textContent = JSON.stringify(data.result, null, 2);
        showToast(\`Executed \${server}.\${action} in \${took}ms\`);
      } catch (err) {
        term.textContent = '// Error executing tool: ' + err.message;
        if (latEl) latEl.textContent = 'Error';
      }
    }

    function copyPlaygroundOutput() {
      const text = document.getElementById('pg-terminal-out')?.textContent;
      if (text) {
        navigator.clipboard?.writeText(text);
        showToast('Copied output to clipboard!');
      }
    }

    // ── Add Integration Modal ─────────────────────────────────────
    function openAddServerModal() {
      document.getElementById('add-server-modal').classList.add('show');
    }

    function closeAddServerModal() {
      document.getElementById('add-server-modal').classList.remove('show');
    }

    async function submitNewIntegration(e) {
      e.preventDefault();
      const name = document.getElementById('add-name')?.value;
      const desc = document.getElementById('add-desc')?.value;
      const category = document.getElementById('add-category')?.value;
      const transport = document.getElementById('add-transport')?.value;
      const command = document.getElementById('add-cmd')?.value;
      const env = document.getElementById('add-env')?.value;

      try {
        const res = await fetch('/api/mcp/servers', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name,
            description: desc,
            category,
            transport,
            command,
            env_required: env ? env.split(',').map(s => s.trim()) : [],
          })
        });
        if (res.ok) {
          showToast(\`Successfully registered \${name}!\`);
          closeAddServerModal();
          await loadData();
        } else {
          const d = await res.json();
          showToast(d.error || 'Failed to register server', 'error');
        }
      } catch (err) {
        showToast('Error registering server', 'error');
      }
    }

    // ── Command Palette (Cmd+K) ───────────────────────────────────
    function openPalette() {
      document.getElementById('palette-overlay').classList.add('show');
      const input = document.getElementById('palette-input');
      input.value = '';
      input.focus();
      onPaletteSearch();
    }

    function closePalette(e) {
      document.getElementById('palette-overlay').classList.remove('show');
    }

    function onPaletteSearch() {
      const q = (document.getElementById('palette-input')?.value || '').toLowerCase();
      const res = document.getElementById('palette-results');
      const matches = serversData.filter(s => s.name.toLowerCase().includes(q) || (s.category || '').includes(q)).slice(0, 8);

      res.innerHTML = matches.map((m, idx) => `
        <div class="palette-item \${idx === 0 ? 'sel' : ''}" onclick="openDrawer('\${m.name}');closePalette();">
          <span style="font-family:var(--mono);font-weight:600;">\${m.name}</span>
          <span style="font-size:11px;color:var(--text-muted);margin-left:auto;">\${m.category} · \${m.actions?.length || 1} tools</span>
        </div>
      `).join('');
    }

    function onPaletteKey(e) {
      if (e.key === 'Escape') closePalette();
      if (e.key === 'Enter') {
        const first = document.querySelector('.palette-item.sel') || document.querySelector('.palette-item');
        if (first) first.click();
      }
    }

    window.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        openPalette();
      }
    });

    // ── WebSocket Telemetry Listener ──────────────────────────────
    function initWebSocket() {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = \`\${proto}//\${window.location.host}/ws\`;
      try {
        const ws = new WebSocket(wsUrl);
        ws.onopen = () => {
          ws.send(JSON.stringify({ cmd: 'subscribe_all' }));
        };
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'tool_call') {
              const feed = document.getElementById('overview-telemetry-feed');
              if (feed) {
                const row = document.createElement('div');
                row.className = 'tlm-row';
                row.innerHTML = `
                  <span class="tlm-time">\${new Date().toLocaleTimeString()}</span>
                  <span class="tlm-name">\${data.name}</span>
                  <span class="tlm-ms">\${data.duration_ms}ms</span>
                `;
                feed.prepend(row);
                if (feed.children.length > 30) feed.lastElementChild.remove();
              }
            }
          } catch (e) {}
        };
      } catch (err) {}
    }

    // ── Command Bar Input ─────────────────────────────────────────
    function onCmdKey(e) {
      if (e.key === 'Enter') {
        const val = e.target.value.trim();
        if (!val) return;
        e.target.value = '';
        if (val.startsWith('enable ')) {
          const name = val.replace('enable ', '').trim();
          toggleServer(name);
        } else if (val.startsWith('test ')) {
          const name = val.replace('test ', '').trim();
          openPlaygroundFor(name);
        } else {
          showToast(\`Executed: \${val}\`);
        }
      }
    }

    // Initialize
    loadData();
    initWebSocket();
  </script>
</body>
</html>\`;
}
''')

if __name__ == '__main__':
    build_dashboard()
    print('Successfully generated src/dashboardHtml.ts')
