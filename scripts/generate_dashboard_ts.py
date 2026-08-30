import json

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en" class="h-full dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Kater Dev Tools — Apps & MCP Store</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: {
              400: '#2DD4BF',
              500: '#14B8A6',
              600: '#0D9488',
            },
            dark: {
              bg: '#0A0C10',
              panel: '#10141C',
              card: '#151B26',
              cardHover: '#1C2433',
              border: '#242F42',
              text: '#E2E8F0',
              muted: '#8B949E'
            }
          }
        }
      }
    }
  </script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    body { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #0A0C10; color: #E2E8F0; }
    code, pre, .font-mono { font-family: 'JetBrains Mono', monospace; }
    .custom-scroll::-webkit-scrollbar { width: 6px; height: 6px; }
    .custom-scroll::-webkit-scrollbar-track { background: transparent; }
    .custom-scroll::-webkit-scrollbar-thumb { background: #2A3447; border-radius: 3px; }
    select option {
      background-color: #151B26 !important;
      color: #E2E8F0 !important;
      padding: 6px 10px;
    }
    .outline-card {
      border: 1px solid #242F42;
      box-shadow: inset 0 1px 0 0 rgba(255, 255, 255, 0.05);
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .outline-card:hover {
      border-color: rgba(45, 212, 191, 0.45);
      box-shadow: 0 0 20px -4px rgba(45, 212, 191, 0.15), inset 0 1px 0 0 rgba(255, 255, 255, 0.1);
    }
    .tree-branch {
      position: relative;
    }
    .tree-branch::before {
      content: '';
      position: absolute;
      left: -16px;
      top: 14px;
      width: 12px;
      height: 1px;
      background: #2E3C52;
    }
  </style>
</head>
<body class="h-full overflow-hidden flex flex-col bg-[#0A0C10] text-[#E2E8F0]">
  <!-- Top Navigation Bar with high-contrast outlines -->
  <header id="top-nav" class="h-14 border-b border-[#242F42] bg-[#10141C] flex items-center justify-between px-5 flex-shrink-0 z-30 shadow-[0_4px_20px_rgba(0,0,0,0.5)]">
    <div class="flex items-center gap-3">
      <div class="w-8 h-8 rounded-lg bg-[#2DD4BF] flex items-center justify-center text-[#0B0D10] font-black text-base ring-1 ring-[#2DD4BF]/50 shadow-[0_0_12px_rgba(45,212,191,0.3)]">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none"><path d="M7 6v12M17 6l-7 6 7 6" stroke="#0B0D10" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </div>
      <div>
        <div class="flex items-center gap-2">
          <span class="font-bold text-sm tracking-tight text-white">KATER</span>
          <span class="text-xs px-1.5 py-0.5 rounded-md bg-[#2DD4BF]/10 text-[#2DD4BF] border border-[#2DD4BF]/30 font-mono font-medium">v1.1.0</span>
          <span class="text-xs text-[#8B949E] hidden sm:inline">Dev Tools & Integrations Hub</span>
        </div>
      </div>
    </div>

    <!-- Active Profile & Live Health -->
    <div class="flex items-center gap-3">
      <div class="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-[#151B26] border border-[#242F42] text-xs">
        <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse ring-4 ring-emerald-500/20"></span>
        <span class="text-[#8B949E]">Gateway:</span>
        <span class="font-mono text-emerald-400 font-medium">127.0.0.1:__PORT__</span>
      </div>

      <!-- Custom Styled Profile Dropdown (No native white OS select artifacts) -->
      <div class="relative" id="profile-dropdown-container">
        <button type="button" id="profile-dropdown-btn" onclick="toggleProfileDropdown()" class="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-[#151B26] border border-[#242F42] hover:border-[#2DD4BF]/50 text-xs text-white transition focus:outline-none shadow-sm">
          <span class="text-[#8B949E]">Profile:</span>
          <span id="profile-current-display" class="font-mono text-white font-bold">dev</span>
          <svg class="w-3.5 h-3.5 text-[#8B949E]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
        </button>

        <div id="profile-dropdown-menu" class="hidden absolute right-0 mt-1.5 w-56 bg-[#10141C] border border-[#242F42] rounded-xl shadow-2xl p-1.5 z-50 divide-y divide-[#242F42]/40">
          <div class="px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-[#6B7280]">Select Active Profile</div>
          <div class="pt-1 space-y-0.5" id="profile-options-list">
            <button onclick="selectProfile('core')" class="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs text-left hover:bg-[#151B26] text-slate-300 hover:text-white transition">
              <div class="flex items-center gap-2">
                <span class="w-1.5 h-1.5 rounded-full bg-slate-500"></span>
                <span class="font-mono font-medium">core</span>
              </div>
              <span class="text-[10px] text-[#8B949E]">Essential</span>
            </button>
            <button onclick="selectProfile('dev')" class="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs text-left bg-[#1C2433] text-[#2DD4BF] font-semibold transition">
              <div class="flex items-center gap-2">
                <span class="w-1.5 h-1.5 rounded-full bg-[#2DD4BF]"></span>
                <span class="font-mono font-bold">dev</span>
              </div>
              <span class="text-[10px] text-[#2DD4BF]">Active</span>
            </button>
            <button onclick="selectProfile('ops')" class="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs text-left hover:bg-[#151B26] text-slate-300 hover:text-white transition">
              <div class="flex items-center gap-2">
                <span class="w-1.5 h-1.5 rounded-full bg-blue-400"></span>
                <span class="font-mono font-medium">ops</span>
              </div>
              <span class="text-[10px] text-[#8B949E]">CI/CD</span>
            </button>
            <button onclick="selectProfile('research')" class="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs text-left hover:bg-[#151B26] text-slate-300 hover:text-white transition">
              <div class="flex items-center gap-2">
                <span class="w-1.5 h-1.5 rounded-full bg-purple-400"></span>
                <span class="font-mono font-medium">research</span>
              </div>
              <span class="text-[10px] text-[#8B949E]">AI & Search</span>
            </button>
            <button onclick="selectProfile('browser')" class="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs text-left hover:bg-[#151B26] text-slate-300 hover:text-white transition">
              <div class="flex items-center gap-2">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                <span class="font-mono font-medium">browser</span>
              </div>
              <span class="text-[10px] text-[#8B949E]">Playwright</span>
            </button>
            <button onclick="selectProfile('content')" class="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs text-left hover:bg-[#151B26] text-slate-300 hover:text-white transition">
              <div class="flex items-center gap-2">
                <span class="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
                <span class="font-mono font-medium">content</span>
              </div>
              <span class="text-[10px] text-[#8B949E]">Docs & Comm</span>
            </button>
            <button onclick="selectProfile('full')" class="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs text-left hover:bg-[#151B26] text-slate-300 hover:text-white transition">
              <div class="flex items-center gap-2">
                <span class="w-1.5 h-1.5 rounded-full bg-rose-400"></span>
                <span class="font-mono font-medium">full</span>
              </div>
              <span class="text-[10px] text-[#8B949E]">48 Servers</span>
            </button>
          </div>
        </div>
      </div>

      <button onclick="openCustomMcpModal()" class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#2DD4BF] text-[#0B0D10] text-xs font-bold hover:bg-[#20bdab] transition shadow-[0_0_15px_rgba(45,212,191,0.2)]">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        Add MCP Server
      </button>
    </div>
  </header>

  <!-- Main Layout -->
  <div class="flex-1 flex overflow-hidden">
    <!-- Sidebar Navigation with crisp border outline -->
    <aside class="w-64 border-r border-[#242F42] bg-[#10141C] flex flex-col justify-between flex-shrink-0 z-20">
      <div class="p-3 space-y-6">
        <div>
          <div class="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-[#6B7280]">Connect & Discover</div>
          <nav class="space-y-1">
            <button onclick="setTab('integrations')" id="nav-integrations" class="w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition bg-[#1C2433] text-[#2DD4BF] border border-[#2DD4BF]/30 shadow-[0_0_10px_rgba(45,212,191,0.1)]">
              <div class="flex items-center gap-2.5 min-w-0">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" class="flex-shrink-0"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><path d="M10 6.5h4M6.5 10v4M17.5 10v4M10 17.5h4" stroke-linecap="round"/></svg>
                <span class="truncate font-semibold">Integrations</span>
              </div>
              <span id="badge-integrations-count" class="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[#2DD4BF]/20 text-[#2DD4BF] border border-[#2DD4BF]/30 flex-shrink-0">48 MCP & Plugins</span>
            </button>
            <button onclick="setTab('apps')" id="nav-apps" class="w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition text-[#9CA3AF] hover:text-white hover:bg-[#151B26] border border-transparent">
              <div class="flex items-center gap-2.5 min-w-0">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="flex-shrink-0"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></svg>
                <span class="truncate">Apps & MCP Store</span>
              </div>
              <span id="badge-active-apps" class="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[#2DD4BF]/20 text-[#2DD4BF] border border-[#2DD4BF]/30 flex-shrink-0">12 Active</span>
            </button>
            <button onclick="setTab('hub')" id="nav-hub" class="w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition text-[#9CA3AF] hover:text-white hover:bg-[#151B26] border border-transparent">
              <div class="flex items-center gap-2.5 min-w-0">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="flex-shrink-0"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
                <span class="truncate">Toolkits & Runner</span>
              </div>
              <span class="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[#242F42] text-[#8B949E] border border-white/5 flex-shrink-0">5</span>
            </button>
            <button onclick="setTab('discovery')" id="nav-discovery" class="w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition text-[#9CA3AF] hover:text-white hover:bg-[#151B26] border border-transparent">
              <div class="flex items-center gap-2.5 min-w-0">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="flex-shrink-0"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>
                <span class="truncate">MCP.so Registry</span>
              </div>
              <span class="text-[10px] font-medium text-emerald-400 flex items-center gap-1 flex-shrink-0">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Live
              </span>
            </button>
          </nav>
        </div>

        <div>
          <div class="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-[#6B7280]">Workspace & Control</div>
          <nav class="space-y-1">
            <button onclick="setTab('overview')" id="nav-overview" class="w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition text-[#9CA3AF] hover:text-white hover:bg-[#151B26] border border-transparent">
              <div class="flex items-center gap-2.5 min-w-0">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" class="flex-shrink-0"><path d="M3 3v18h18"/><path d="M18 9l-5 5-4-4-3 3"/></svg>
                <span class="truncate">Control Room</span>
              </div>
            </button>
            <button onclick="setTab('browser')" id="nav-browser" class="w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition text-[#9CA3AF] hover:text-white hover:bg-[#151B26] border border-transparent">
              <div class="flex items-center gap-2.5 min-w-0">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" class="flex-shrink-0"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                <span class="truncate">Browser Workspace</span>
              </div>
            </button>
            <button onclick="setTab('prgate')" id="nav-prgate" class="w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition text-[#9CA3AF] hover:text-white hover:bg-[#151B26] border border-transparent">
              <div class="flex items-center gap-2.5 min-w-0">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" class="flex-shrink-0"><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7"/><line x1="6" y1="9" x2="6" y2="21"/></svg>
                <span class="truncate">PR Gate & CI</span>
              </div>
            </button>
            <button onclick="setTab('automations')" id="nav-automations" class="w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition text-[#9CA3AF] hover:text-white hover:bg-[#151B26] border border-transparent">
              <div class="flex items-center gap-2.5 min-w-0">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" class="flex-shrink-0"><rect x="3" y="3" width="6" height="6" rx="1"/><rect x="15" y="3" width="6" height="6" rx="1"/><rect x="9" y="15" width="6" height="6" rx="1"/><path d="M6 9v3a1 1 0 001 1h10a1 1 0 001-1V9M12 13v2"/></svg>
                <span class="truncate">Automations</span>
              </div>
            </button>
            <button onclick="setTab('telemetry')" id="nav-telemetry" class="w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition text-[#9CA3AF] hover:text-white hover:bg-[#151B26] border border-transparent">
              <div class="flex items-center gap-2.5 min-w-0">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" class="flex-shrink-0"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
                <span class="truncate">Telemetry & Events</span>
              </div>
            </button>
            <button onclick="setTab('settings')" id="nav-settings" class="w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition text-[#9CA3AF] hover:text-white hover:bg-[#151B26] border border-transparent">
              <div class="flex items-center gap-2.5 min-w-0">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" class="flex-shrink-0"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
                <span class="truncate">Settings & Ports</span>
              </div>
            </button>
          </nav>
        </div>
      </div>

      <!-- Footer Quick Status -->
      <div class="p-3 border-t border-[#242F42] bg-[#0D1017]">
        <div class="flex items-center justify-between text-xs text-[#8B949E]">
          <span class="font-medium">Kater SSE Core</span>
          <span class="font-mono text-emerald-400 font-semibold flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Active
          </span>
        </div>
      </div>
    </aside>

    <!-- Main Viewport -->
    <main class="flex-1 overflow-y-auto custom-scroll bg-[#0A0C10] p-6">
      
      <!-- TAB 0: INTEGRATIONS & PLUGINS GRID -->
      <section id="view-integrations" class="space-y-6">
        <!-- Header row -->
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div class="flex items-center gap-2.5">
              <h1 class="text-2xl font-bold text-white tracking-tight">Integrations</h1>
              <span id="integrations-total-pill" class="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-[#2DD4BF]/15 text-[#2DD4BF] border border-[#2DD4BF]/30">48 Available</span>
            </div>
            <p class="text-xs text-[#8B949E] mt-0.5">Explore, search, filter, and configure Model Context Protocol (MCP) servers and developer plugins across your workspace.</p>
          </div>
          
          <div class="flex items-center gap-2.5">
            <button onclick="openRequestAppModal()" class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#242F42] bg-[#151B26] hover:bg-[#1C2433] text-xs font-medium text-[#E2E8F0] transition shadow-sm">
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              Request Integration
            </button>
            <button onclick="openCustomMcpModal()" class="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-[#2DD4BF] text-[#0B0D10] text-xs font-bold hover:bg-[#20bdab] transition shadow-[0_0_15px_rgba(45,212,191,0.2)]">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              Add MCP Server
            </button>
          </div>
        </div>

        <!-- Metrics KPI Bar (Strictly SVG icons, no emojis) -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
          <div class="p-3.5 rounded-xl bg-[#10141C] border border-[#242F42] flex items-center gap-3 outline-card">
            <div class="w-9 h-9 rounded-lg bg-[#151B26] border border-[#242F42] flex items-center justify-center text-[#2DD4BF] flex-shrink-0">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></svg>
            </div>
            <div>
              <div class="text-[11px] text-[#8B949E] font-medium">Total Integrations</div>
              <div id="stat-integrations-total" class="text-base font-bold font-mono text-white">48</div>
            </div>
          </div>
          <div class="p-3.5 rounded-xl bg-[#10141C] border border-[#242F42] flex items-center gap-3 outline-card">
            <div class="w-9 h-9 rounded-lg bg-[#151B26] border border-[#242F42] flex items-center justify-center text-emerald-400 flex-shrink-0">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
            </div>
            <div>
              <div class="text-[11px] text-[#8B949E] font-medium">Active & Enabled</div>
              <div id="stat-integrations-active" class="text-base font-bold font-mono text-emerald-400">24 Active</div>
            </div>
          </div>
          <div class="p-3.5 rounded-xl bg-[#10141C] border border-[#242F42] flex items-center gap-3 outline-card">
            <div class="w-9 h-9 rounded-lg bg-[#151B26] border border-[#242F42] flex items-center justify-center text-sky-400 flex-shrink-0">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
            </div>
            <div>
              <div class="text-[11px] text-[#8B949E] font-medium">Available Tools</div>
              <div id="stat-integrations-tools" class="text-base font-bold font-mono text-white">64+ Actions</div>
            </div>
          </div>
          <div class="p-3.5 rounded-xl bg-[#10141C] border border-[#242F42] flex items-center gap-3 outline-card">
            <div class="w-9 h-9 rounded-lg bg-[#151B26] border border-[#242F42] flex items-center justify-center text-purple-400 flex-shrink-0">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
            </div>
            <div>
              <div class="text-[11px] text-[#8B949E] font-medium">Plugins & Satellites</div>
              <div id="stat-integrations-plugins" class="text-base font-bold font-mono text-purple-400">8 Plugins</div>
            </div>
          </div>
        </div>

        <!-- Filter & Search Toolbar -->
        <div class="space-y-3 p-4 rounded-xl bg-[#10141C] border border-[#242F42]">
          <div class="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
            <!-- Type Selector Tabs -->
            <div class="flex flex-wrap items-center gap-2" id="integrations-type-pills">
              <button onclick="setIntegrationsFilter('all')" id="btn-int-filter-all" class="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-[#242F42] text-white border border-[#2DD4BF]/40 transition shadow-sm">
                All Integrations
              </button>
              <button onclick="setIntegrationsFilter('server')" id="btn-int-filter-server" class="px-3.5 py-1.5 rounded-lg text-xs font-medium text-[#8B949E] hover:text-white hover:bg-[#151B26] border border-[#242F42] transition">
                MCP Servers
              </button>
              <button onclick="setIntegrationsFilter('plugin')" id="btn-int-filter-plugin" class="px-3.5 py-1.5 rounded-lg text-xs font-medium text-[#8B949E] hover:text-white hover:bg-[#151B26] border border-[#242F42] transition">
                Dev Plugins
              </button>
              <button onclick="setIntegrationsFilter('connected')" id="btn-int-filter-connected" class="px-3.5 py-1.5 rounded-lg text-xs font-medium text-[#8B949E] hover:text-white hover:bg-[#151B26] border border-[#242F42] transition">
                Connected
              </button>
            </div>

            <!-- Search input with SVG magnifying glass -->
            <div class="relative w-full lg:w-80">
              <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#8B949E]">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
              </div>
              <input type="text" id="integrations-search-input" oninput="handleIntegrationsSearch(this.value)" placeholder="Search MCP servers, plugins, tools..." class="w-full pl-9 pr-4 py-1.5 bg-[#151B26] border border-[#242F42] rounded-lg text-xs text-white placeholder-[#6B7280] focus:outline-none focus:border-[#2DD4BF] focus:ring-2 focus:ring-[#2DD4BF]/30 transition shadow-inner">
            </div>
          </div>

          <!-- Secondary Filters Row (Category, Transport, Count) -->
          <div class="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-[#242F42]/60 text-xs">
            <div class="flex flex-wrap items-center gap-3">
              <div class="flex items-center gap-2">
                <span class="text-[#8B949E] font-medium">Category:</span>
                <select id="integrations-category-select" onchange="filterIntegrationsCategory(this.value)" class="bg-[#151B26] border border-[#242F42] rounded-lg px-2.5 py-1 text-xs text-[#E2E8F0] focus:outline-none focus:border-[#2DD4BF]">
                  <option value="all">All Categories</option>
                  <option value="workspace">Workspace & Productivity</option>
                  <option value="dev">Developer & Engineering</option>
                  <option value="plugins">Dev Plugins & Satellites</option>
                  <option value="ai">AI & Reasoning</option>
                  <option value="data">Databases & Cloud</option>
                  <option value="web">Search & Scraping</option>
                  <option value="comm">Communication & Social</option>
                  <option value="design">Design & Media</option>
                </select>
              </div>

              <div class="flex items-center gap-2">
                <span class="text-[#8B949E] font-medium">Transport:</span>
                <select id="integrations-transport-select" onchange="filterIntegrationsTransport(this.value)" class="bg-[#151B26] border border-[#242F42] rounded-lg px-2.5 py-1 text-xs text-[#E2E8F0] focus:outline-none focus:border-[#2DD4BF]">
                  <option value="all">All Transports</option>
                  <option value="stdio">stdio (Local Subprocess)</option>
                  <option value="http">http / sse (Cloud Stream)</option>
                  <option value="native">native (In-Process Gateway)</option>
                  <option value="plugin">plugin (Satellite Agent)</option>
                </select>
              </div>
            </div>

            <div class="flex items-center gap-2 text-[#8B949E]">
              <span id="integrations-display-count" class="font-mono text-xs text-[#8B949E]">Showing 48 integrations</span>
            </div>
          </div>
        </div>

        <!-- Grid Layout Component for MCP Servers and Plugins -->
        <div id="integrations-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"></div>
      </section>

      <!-- TAB 1: APPS & MCP STORE -->
      <section id="view-apps" class="space-y-6 hidden">
        <!-- Header row -->
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 class="text-2xl font-bold text-white tracking-tight">Apps & MCP Store</h1>
            <p class="text-xs text-[#8B949E] mt-0.5">Explore, connect, and manage authenticated MCP integrations and autonomous agent toolkits.</p>
          </div>
          
          <div class="flex items-center gap-3">
            <!-- View Mode Switcher (Grid vs Outline Hierarchy) -->
            <div class="flex items-center bg-[#151B26] border border-[#242F42] rounded-lg p-0.5">
              <button onclick="setViewMode('grid')" id="btn-view-grid" class="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-[#242F42] text-white transition">
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
                Grid
              </button>
              <button onclick="setViewMode('outline')" id="btn-view-outline" class="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium text-[#8B949E] hover:text-white transition">
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
                Outline View
              </button>
            </div>

            <button onclick="openRequestAppModal()" class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#242F42] bg-[#151B26] hover:bg-[#1C2433] text-xs font-medium text-[#E2E8F0] transition shadow-sm">
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              Request App
            </button>
            <button onclick="openCustomMcpModal()" class="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-[#2DD4BF] text-[#0B0D10] text-xs font-bold hover:bg-[#20bdab] transition shadow-[0_0_15px_rgba(45,212,191,0.2)]">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              Add Custom MCP
            </button>
          </div>
        </div>

        <!-- Filter Pill Bar & Search -->
        <div class="flex flex-col sm:flex-row items-center justify-between gap-4 pb-2 border-b border-[#242F42]">
          <div class="flex items-center gap-2 w-full sm:w-auto">
            <button onclick="filterConnected('all')" id="filter-all" class="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-[#242F42] text-white border border-[#2DD4BF]/40 transition shadow-sm">
              All
            </button>
            <button onclick="filterConnected('connected')" id="filter-connected" class="px-3.5 py-1.5 rounded-lg text-xs font-medium text-[#8B949E] hover:text-white hover:bg-[#151B26] border border-[#242F42] transition">
              Connected
            </button>
            <div class="h-4 w-px bg-[#242F42] mx-1"></div>
            <select id="category-filter-select" onchange="filterCategory(this.value)" class="bg-[#151B26] border border-[#242F42] rounded-lg px-2.5 py-1.5 text-xs text-[#E2E8F0] focus:outline-none focus:border-[#2DD4BF]">
              <option value="all">All Categories</option>
              <option value="workspace">Workspace & CRM</option>
              <option value="dev">Developer & Engineering</option>
              <option value="ai">AI & Reasoning</option>
              <option value="data">Databases & Cloud</option>
              <option value="web">Search & Scraping</option>
              <option value="comm">Communication</option>
              <option value="design">Design & Media</option>
            </select>
          </div>

          <!-- Search Input with dual-state ring outline -->
          <div class="relative w-full sm:w-80">
            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#8B949E]">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            </div>
            <input type="text" id="app-search-input" oninput="handleAppSearch(this.value)" placeholder="Search apps, MCP tools, actions..." class="w-full pl-9 pr-4 py-1.5 bg-[#151B26] border border-[#242F42] rounded-lg text-xs text-white placeholder-[#6B7280] focus:outline-none focus:border-[#2DD4BF] focus:ring-2 focus:ring-[#2DD4BF]/30 transition shadow-inner">
          </div>
        </div>

        <!-- 3-column App Grid Mode -->
        <div id="apps-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"></div>

        <!-- Outline / Tree Hierarchy View Mode (Hidden by default) -->
        <div id="apps-outline-view" class="hidden space-y-4"></div>
      </section>

      <!-- TAB 2: AGENT TOOLKITS -->
      <section id="view-hub" class="space-y-6 hidden">
        <div>
          <h1 class="text-2xl font-bold text-white tracking-tight">Agent Toolkits & Action Runner</h1>
          <p class="text-xs text-[#8B949E] mt-0.5">Pre-configured bundles of verified MCP servers grouped for specific autonomous workflows.</p>
        </div>

        <div id="toolkits-grid" class="grid grid-cols-1 lg:grid-cols-2 gap-4"></div>

        <div class="mt-8 border border-[#242F42] rounded-xl bg-[#10141C] p-5 space-y-4 shadow-lg">
          <div class="flex items-center justify-between border-b border-[#242F42] pb-3">
            <div class="flex items-center gap-2">
              <span class="w-2.5 h-2.5 rounded-full bg-[#2DD4BF] ring-4 ring-[#2DD4BF]/20"></span>
              <h2 class="text-sm font-bold text-white uppercase tracking-wider">Interactive Action Playground</h2>
            </div>
            <span class="text-xs text-[#8B949E] font-mono">Proxy Transport: stdio / http</span>
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div class="space-y-3">
              <label class="block text-xs font-semibold text-[#8B949E]">Target MCP Action</label>
              <select id="playground-action-select" onchange="onPlaygroundActionChange(this.value)" class="w-full bg-[#151B26] border border-[#242F42] rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-[#2DD4BF]"></select>
              <div id="playground-action-desc" class="text-xs text-[#8B949E] bg-[#151B26] p-3 rounded-lg border border-[#242F42]">
                Select an action to inspect parameters and test live execution.
              </div>
            </div>

            <div class="space-y-3">
              <label class="block text-xs font-semibold text-[#8B949E]">Input Payload (JSON)</label>
              <textarea id="playground-payload-input" rows="6" class="w-full bg-[#151B26] border border-[#242F42] rounded-lg p-2.5 text-xs font-mono text-white focus:outline-none focus:border-[#2DD4BF]" placeholder='{"query": "example"}'></textarea>
              <button onclick="runPlaygroundAction()" id="btn-run-action" class="w-full py-2 rounded-lg bg-[#2DD4BF] text-[#0B0D10] text-xs font-bold hover:bg-[#20bdab] transition flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(45,212,191,0.2)]">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                Execute Action
              </button>
            </div>

            <div class="space-y-3">
              <label class="block text-xs font-semibold text-[#8B949E]">Execution Output</label>
              <pre id="playground-output-result" class="h-44 bg-[#0D1017] border border-[#242F42] rounded-lg p-3 text-xs font-mono text-emerald-400 overflow-y-auto custom-scroll shadow-inner">Ready to execute.</pre>
            </div>
          </div>
        </div>
      </section>

      <!-- TAB 3: DISCOVERY -->
      <section id="view-discovery" class="space-y-6 hidden">
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 class="text-2xl font-bold text-white tracking-tight">MCP.so Server Registry & Community</h1>
            <p class="text-xs text-[#8B949E] mt-0.5">Discover trending open-source Model Context Protocol servers verified for Kater Dev Tools.</p>
          </div>
          <div class="flex items-center gap-2">
            <a href="https://mcp.so/servers" target="_blank" class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#242F42] bg-[#151B26] text-xs font-medium text-[#8B949E] hover:text-white transition">
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              Open MCP.so
            </a>
            <a href="https://dashboard.composio.dev" target="_blank" class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#242F42] bg-[#151B26] text-xs font-medium text-[#8B949E] hover:text-white transition">
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              Composio Dashboard
            </a>
          </div>
        </div>
        <div id="discovery-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"></div>
      </section>

      <!-- TAB 4: CONTROL ROOM -->
      <section id="view-overview" class="space-y-6 hidden">
        <div>
          <h1 class="text-2xl font-bold text-white tracking-tight">Gateway Control Room</h1>
          <p class="text-xs text-[#8B949E] mt-0.5">System health, SSE streaming listeners, and database statistics.</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div class="p-4 rounded-xl bg-[#10141C] border border-[#242F42] space-y-1 outline-card border-t-2 border-t-[#2DD4BF]">
            <div class="text-xs text-[#8B949E]">Gateway Port</div>
            <div class="text-xl font-bold font-mono text-[#2DD4BF]">3000</div>
            <div class="text-[11px] text-emerald-400 font-medium">Reverse proxy active</div>
          </div>
          <div class="p-4 rounded-xl bg-[#10141C] border border-[#242F42] space-y-1 outline-card border-t-2 border-t-blue-400">
            <div class="text-xs text-[#8B949E]">Active Servers</div>
            <div id="stat-active-servers" class="text-xl font-bold font-mono text-white">12 / 36</div>
            <div class="text-[11px] text-[#8B949E]">Native & stdio proxies</div>
          </div>
          <div class="p-4 rounded-xl bg-[#10141C] border border-[#242F42] space-y-1 outline-card border-t-2 border-t-emerald-400">
            <div class="text-xs text-[#8B949E]">Telemetry Events</div>
            <div id="stat-telemetry-count" class="text-xl font-bold font-mono text-white">184</div>
            <div class="text-[11px] text-emerald-400 font-medium">Stream connected</div>
          </div>
          <div class="p-4 rounded-xl bg-[#10141C] border border-[#242F42] space-y-1 outline-card border-t-2 border-t-purple-400">
            <div class="text-xs text-[#8B949E]">Storage State</div>
            <div class="text-xl font-bold font-mono text-white">SQLite</div>
            <div class="text-[11px] text-[#8B949E]">.kater/kater.db</div>
          </div>
        </div>

        <div class="p-5 rounded-xl bg-[#10141C] border border-[#242F42] space-y-3">
          <h3 class="text-sm font-bold text-white">Architecture & Verification Matrix</h3>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div class="p-3.5 bg-[#151B26] border border-[#242F42] rounded-xl outline-card">
              <div class="flex items-center justify-between">
                <div class="text-xs font-bold text-white">REST API & Health</div>
                <span class="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">200 OK</span>
              </div>
              <div class="text-xs text-[#8B949E] mt-1.5 font-mono bg-[#0D1017] p-2 rounded border border-white/5">curl -s http://127.0.0.1:__PORT__/health</div>
            </div>
            <div class="p-3.5 bg-[#151B26] border border-[#242F42] rounded-xl outline-card">
              <div class="flex items-center justify-between">
                <div class="text-xs font-bold text-white">MCP SSE Endpoint</div>
                <span class="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">SSE Stream</span>
              </div>
              <div class="text-xs text-[#8B949E] mt-1.5 font-mono bg-[#0D1017] p-2 rounded border border-white/5">http://127.0.0.1:__PORT__/sse</div>
            </div>
            <div class="p-3.5 bg-[#151B26] border border-[#242F42] rounded-xl outline-card">
              <div class="flex items-center justify-between">
                <div class="text-xs font-bold text-white">WebSocket Telemetry</div>
                <span class="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">ws://</span>
              </div>
              <div class="text-xs text-[#8B949E] mt-1.5 font-mono bg-[#0D1017] p-2 rounded border border-white/5">ws://127.0.0.1:__PORT__/ws</div>
            </div>
          </div>
        </div>
      </section>

      <!-- TAB 5: BROWSER -->
      <section id="view-browser" class="space-y-6 hidden">
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-2xl font-bold text-white tracking-tight">Browser Automation Workspace</h1>
            <p class="text-xs text-[#8B949E] mt-0.5">Autonomous Playwright & Puppeteer browser sessions with live viewport capture.</p>
          </div>
          <button onclick="createBrowserSession()" class="px-3.5 py-1.5 bg-[#2DD4BF] text-[#0B0D10] text-xs font-bold rounded-lg hover:bg-[#20bdab] transition shadow-sm">
            + New Browser Session
          </button>
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4" id="browser-sessions-grid"></div>
      </section>

      <!-- TAB 6: PR GATE -->
      <section id="view-prgate" class="space-y-6 hidden">
        <div>
          <h1 class="text-2xl font-bold text-white tracking-tight">PR Gate & CI Pipeline</h1>
          <p class="text-xs text-[#8B949E] mt-0.5">Automated merge-ready checks, ruff linter, mypy types, and test suites.</p>
        </div>
        <div class="space-y-3" id="pr-list-container"></div>
      </section>

      <!-- TAB 7: AUTOMATIONS -->
      <section id="view-automations" class="space-y-6 hidden">
        <div>
          <h1 class="text-2xl font-bold text-white tracking-tight">Autonomous Cron & Event Automations</h1>
          <p class="text-xs text-[#8B949E] mt-0.5">Scheduled tasks, webhooks, and multi-step agent triggers.</p>
        </div>
        <div class="space-y-3" id="automations-list-container"></div>
      </section>

      <!-- TAB 8: TELEMETRY -->
      <section id="view-telemetry" class="space-y-6 hidden">
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-2xl font-bold text-white tracking-tight">Live Telemetry & MCP Event Stream</h1>
            <p class="text-xs text-[#8B949E] mt-0.5">Real-time WebSocket events from connected tool calls, proxy dispatches, and agent sessions.</p>
          </div>
          <button onclick="clearTelemetryLog()" class="px-3 py-1.5 bg-[#151B26] border border-[#242F42] text-xs text-[#8B949E] hover:text-white rounded-lg transition">
            Clear Stream
          </button>
        </div>
        <div id="telemetry-log-box" class="h-96 bg-[#0D1017] border border-[#242F42] rounded-xl p-4 font-mono text-xs text-[#E2E8F0] overflow-y-auto custom-scroll space-y-2 shadow-inner"></div>
      </section>

      <!-- TAB 9: SETTINGS -->
      <section id="view-settings" class="space-y-6 hidden">
        <div>
          <h1 class="text-2xl font-bold text-white tracking-tight">Settings & Gateway Config</h1>
          <p class="text-xs text-[#8B949E] mt-0.5">Environment, authentication modes, CORS policies, and SQLite persistence.</p>
        </div>
        <div class="max-w-2xl bg-[#10141C] border border-[#242F42] rounded-xl p-5 space-y-4 outline-card">
          <div>
            <label class="block text-xs font-semibold text-white mb-1">Gateway Auth Mode</label>
            <div class="text-xs text-[#8B949E] mb-2">Controls whether bearer tokens are required on MCP and REST endpoints.</div>
            <select id="settings-auth-mode" class="bg-[#151B26] border border-[#242F42] rounded-lg p-2 text-xs text-white w-full">
              <option value="none" selected>none (Open local development)</option>
              <option value="token">token (Bearer token authentication)</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-semibold text-white mb-1">CORS Origins</label>
            <input type="text" value="*" class="w-full bg-[#151B26] border border-[#242F42] rounded-lg p-2 text-xs text-white font-mono">
          </div>
          <div class="pt-2 border-t border-[#242F42] flex justify-end">
            <button onclick="alert('Configuration saved successfully')" class="px-4 py-2 bg-[#2DD4BF] text-[#0B0D10] text-xs font-bold rounded-lg hover:bg-[#20bdab] transition shadow-[0_0_15px_rgba(45,212,191,0.2)]">
              Save Configuration
            </button>
          </div>
        </div>
      </section>

    </main>
  </div>

  <!-- MODAL: Connect App -->
  <div id="modal-connect-app" class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 hidden">
    <div class="bg-[#10141C] border border-[#242F42] rounded-2xl w-full max-w-md p-6 space-y-5 shadow-2xl">
      <div class="flex items-center justify-between border-b border-[#242F42] pb-4">
        <div class="flex items-center gap-3">
          <div id="modal-app-icon" class="w-9 h-9 rounded-lg bg-[#151B26] border border-[#242F42] flex items-center justify-center p-1.5"></div>
          <div>
            <h3 id="modal-app-name" class="text-sm font-bold text-white">Connect App</h3>
            <div id="modal-app-category" class="text-[11px] text-[#8B949E]">Workspace Integration</div>
          </div>
        </div>
        <button onclick="closeConnectModal()" class="text-[#8B949E] hover:text-white">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
      <div class="space-y-4" id="modal-connect-body"></div>
      <div class="flex items-center justify-end gap-2 border-t border-[#242F42] pt-4">
        <button onclick="closeConnectModal()" class="px-3.5 py-1.5 rounded-lg border border-[#242F42] text-xs text-[#8B949E] hover:text-white">Cancel</button>
        <button id="modal-btn-confirm-connect" onclick="submitAppConnection()" class="px-4 py-1.5 rounded-lg bg-[#2DD4BF] text-[#0B0D10] text-xs font-bold hover:bg-[#20bdab] transition shadow-sm">Connect & Enable</button>
      </div>
    </div>
  </div>

  <!-- MODAL: Add Custom MCP Server -->
  <div id="modal-custom-mcp" class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 hidden">
    <div class="bg-[#10141C] border border-[#242F42] rounded-2xl w-full max-w-lg p-6 space-y-4 shadow-2xl">
      <div class="flex items-center justify-between border-b border-[#242F42] pb-3">
        <h3 class="text-base font-bold text-white">Add Custom MCP Server</h3>
        <button onclick="closeCustomMcpModal()" class="text-[#8B949E] hover:text-white">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
      <div class="space-y-3 text-xs">
        <div>
          <label class="block text-[#8B949E] mb-1 font-medium">Server Identifier (Name)</label>
          <input type="text" id="custom-server-name" placeholder="my-custom-mcp" class="w-full bg-[#151B26] border border-[#242F42] rounded-lg p-2 text-white font-mono focus:outline-none focus:border-[#2DD4BF]">
        </div>
        <div>
          <label class="block text-[#8B949E] mb-1 font-medium">Transport Type</label>
          <select id="custom-server-transport" class="w-full bg-[#151B26] border border-[#242F42] rounded-lg p-2 text-white focus:outline-none">
            <option value="stdio">stdio (Subprocess / CLI Command)</option>
            <option value="http">http / sse (Remote URL Stream)</option>
          </select>
        </div>
        <div>
          <label class="block text-[#8B949E] mb-1 font-medium">Command / Remote URL</label>
          <input type="text" id="custom-server-command" placeholder="npx -y my-mcp-server@latest or https://mcp.example.com/sse" class="w-full bg-[#151B26] border border-[#242F42] rounded-lg p-2 text-white font-mono focus:outline-none focus:border-[#2DD4BF]">
        </div>
        <div>
          <label class="block text-[#8B949E] mb-1 font-medium">Category</label>
          <select id="custom-server-category" class="w-full bg-[#151B26] border border-[#242F42] rounded-lg p-2 text-white focus:outline-none">
            <option value="dev">Developer & Engineering</option>
            <option value="workspace">Workspace & CRM</option>
            <option value="ai">AI & Reasoning</option>
            <option value="data">Databases & Cloud</option>
            <option value="web">Search & Web Scraping</option>
            <option value="comm">Communication</option>
            <option value="design">Design & Media</option>
          </select>
        </div>
      </div>
      <div class="flex items-center justify-end gap-2 border-t border-[#242F42] pt-3">
        <button onclick="closeCustomMcpModal()" class="px-3 py-1.5 rounded-lg border border-[#242F42] text-xs text-[#8B949E]">Cancel</button>
        <button onclick="submitCustomMcp()" class="px-4 py-1.5 rounded-lg bg-[#2DD4BF] text-[#0B0D10] text-xs font-bold hover:bg-[#20bdab]">Register MCP Server</button>
      </div>
    </div>
  </div>

  <!-- MODAL: Request App -->
  <div id="modal-request-app" class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 hidden">
    <div class="bg-[#10141C] border border-[#242F42] rounded-2xl w-full max-w-md p-6 space-y-4 shadow-2xl">
      <div class="flex items-center justify-between border-b border-[#242F42] pb-3">
        <h3 class="text-base font-bold text-white">Request an App or MCP Tool</h3>
        <button onclick="closeRequestAppModal()" class="text-[#8B949E] hover:text-white">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
      <div class="space-y-3 text-xs">
        <p class="text-[#8B949E]">Can't find the integration you need? Submit your request and our team will build an official connector.</p>
        <div>
          <label class="block text-[#8B949E] mb-1 font-medium">App Name / Service</label>
          <input type="text" id="request-app-name" placeholder="e.g. Asana, Snowflake, Intercom" class="w-full bg-[#151B26] border border-[#242F42] rounded-lg p-2 text-white focus:outline-none focus:border-[#2DD4BF]">
        </div>
        <div>
          <label class="block text-[#8B949E] mb-1 font-medium">Use Case / Actions Needed</label>
          <textarea id="request-app-usecase" rows="3" placeholder="Briefly describe what your autonomous agents will do with this integration..." class="w-full bg-[#151B26] border border-[#242F42] rounded-lg p-2 text-white focus:outline-none focus:border-[#2DD4BF]"></textarea>
        </div>
      </div>
      <div class="flex items-center justify-end gap-2 border-t border-[#242F42] pt-3">
        <button onclick="closeRequestAppModal()" class="px-3 py-1.5 rounded-lg border border-[#242F42] text-xs text-[#8B949E]">Cancel</button>
        <button onclick="submitRequestApp()" class="px-4 py-1.5 rounded-lg bg-[#2DD4BF] text-[#0B0D10] text-xs font-bold hover:bg-[#20bdab]">Submit Request</button>
      </div>
    </div>
  </div>

  <script>
    const BRAND_SVGS = {
      gmail: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="4" fill="#F2F2F2"/><path d="M4 6l8 6 8-6" stroke="#EA4335" stroke-width="2" stroke-linecap="round"/><path d="M4 6v12h4v-7l4 3 4-3v7h4V6" fill="#EA4335"/></svg>`,
      googlecalendar: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect x="3" y="4" width="18" height="18" rx="4" fill="#4285F4"/><rect x="6" y="8" width="12" height="11" rx="2" fill="#fff"/><text x="12" y="16.5" font-size="7.5" font-family="sans-serif" font-weight="bold" fill="#4285F4" text-anchor="middle">31</text><path d="M7 2v4M17 2v4" stroke="#4285F4" stroke-width="2" stroke-linecap="round"/></svg>`,
      calendar: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect x="3" y="4" width="18" height="18" rx="4" fill="#4285F4"/><rect x="6" y="8" width="12" height="11" rx="2" fill="#fff"/><text x="12" y="16.5" font-size="7.5" font-family="sans-serif" font-weight="bold" fill="#4285F4" text-anchor="middle">31</text><path d="M7 2v4M17 2v4" stroke="#4285F4" stroke-width="2" stroke-linecap="round"/></svg>`,
      googlesheets: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="18" height="18" rx="3" fill="#0F9D58"/><path d="M7 8h10v8H7V8z" fill="#fff" fill-opacity="0.2"/><path d="M7 11h10M7 14h10M12 8v8" stroke="#fff" stroke-width="1.5"/><path d="M15 3l6 6h-6V3z" fill="#0B8043"/></svg>`,
      sheets: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="18" height="18" rx="3" fill="#0F9D58"/><path d="M7 8h10v8H7V8z" fill="#fff" fill-opacity="0.2"/><path d="M7 11h10M7 14h10M12 8v8" stroke="#fff" stroke-width="1.5"/><path d="M15 3l6 6h-6V3z" fill="#0B8043"/></svg>`,
      composio: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#090A0F"/><path d="M6 8h4v8H6V8z" fill="#00E599"/><path d="M14 8h4v8h-4V8z" fill="#2E90FA"/><path d="M10 12h4v4h-4v-4z" fill="#fff"/></svg>`,
      github: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="#FFFFFF"><path fill-rule="evenodd" clip-rule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/></svg>`,
      gitlab: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><path d="M22.65 14.39L12 22.13 1.35 14.39a.84.84 0 01-.3-.94l1.22-3.78L5.6 1.95a.43.43 0 01.82 0l2.36 7.25h6.44l2.36-7.25a.43.43 0 01.82 0l3.33 7.72 1.22 3.78a.84.84 0 01-.3.94z" fill="#E24329"/><path d="M12 22.13l-3.37-10.4h6.74L12 22.13z" fill="#E24329"/><path d="M12 22.13L8.63 11.73H1.35l10.65 10.4z" fill="#FC6D26"/><path d="M1.35 14.39l-.3-.94a.84.84 0 01.3-.94L8.63 11.73 1.35 14.39z" fill="#FCA326"/><path d="M12 22.13l3.37-10.4h7.28L12 22.13z" fill="#FC6D26"/><path d="M22.65 14.39l.3-.94a.84.84 0 00-.3-.94l-7.28-1.78 7.28 3.66z" fill="#FCA326"/></svg>`,
      sentry: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><path d="M13.1 3.5l8.6 15c.6 1.1-.2 2.5-1.5 2.5H3.8c-1.3 0-2.1-1.4-1.5-2.5l8.6-15c.6-1.1 2.4-1.1 3 0z" fill="#362D59" stroke="#9B51E0" stroke-width="1.5"/><circle cx="12" cy="14" r="2.5" fill="#FF5277"/><path d="M12 7v3.5" stroke="#FF5277" stroke-width="2" stroke-linecap="round"/></svg>`,
      sequentialthinking: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#151B26" stroke="#2DD4BF" stroke-opacity="0.3"/><circle cx="7" cy="12" r="2.5" fill="#2DD4BF"/><circle cx="17" cy="8" r="2.5" fill="#38BDF8"/><circle cx="15" cy="16" r="2" fill="#818CF8"/><path d="M9.5 12h5M17 10.5v3.5M9 13.5l4.5 2" stroke="#64748B" stroke-width="1.5" stroke-linecap="round"/></svg>`,
      context7: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#0E1B2A" stroke="#06B6D4" stroke-opacity="0.4"/><path d="M7 6h7l3 3v9a1 1 0 01-1 1H7a1 1 0 01-1-1V7a1 1 0 011-1z" stroke="#22D3EE" stroke-width="1.5"/><path d="M14 6v3h3M9 13h6M9 16h4" stroke="#22D3EE" stroke-width="1.5" stroke-linecap="round"/></svg>`,
      deepwiki: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#181E29" stroke="#6366F1" stroke-opacity="0.4"/><path d="M4 19.5A2.5 2.5 0 016.5 17H20" stroke="#A5B4FC" stroke-width="1.5"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" stroke="#A5B4FC" stroke-width="1.5"/><text x="12" y="14" font-family="'JetBrains Mono', monospace" font-weight="bold" font-size="9" fill="#818CF8" text-anchor="middle">W</text></svg>`,
      filesystem: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#151E2E" stroke="#3B82F6" stroke-opacity="0.3"/><path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" fill="#1D4ED8" fill-opacity="0.3" stroke="#60A5FA" stroke-width="1.5"/></svg>`,
      postgres: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#111C2D" stroke="#336791" stroke-opacity="0.5"/><ellipse cx="12" cy="7" rx="6" ry="2.5" stroke="#336791" stroke-width="1.5" fill="#336791" fill-opacity="0.2"/><path d="M6 7v5c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5V7M6 12v5c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5v-5" stroke="#336791" stroke-width="1.5"/></svg>`,
      postgresql: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#111C2D" stroke="#336791" stroke-opacity="0.5"/><ellipse cx="12" cy="7" rx="6" ry="2.5" stroke="#336791" stroke-width="1.5" fill="#336791" fill-opacity="0.2"/><path d="M6 7v5c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5V7M6 12v5c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5v-5" stroke="#336791" stroke-width="1.5"/></svg>`,
      sqlite: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#0F172A" stroke="#003B57" stroke-opacity="0.8"/><ellipse cx="12" cy="7" rx="6" ry="2.5" stroke="#38BDF8" stroke-width="1.5"/><path d="M6 7v5c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5V7M6 12v5c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5v-5" stroke="#38BDF8" stroke-width="1.5"/></svg>`,
      bravesearch: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#26160F" stroke="#FB542B" stroke-opacity="0.3"/><path d="M12 4L5 7v6c0 4 3 7 7 8 4-1 7-4 7-8V7l-7-3z" stroke="#FB542B" stroke-width="1.5" fill="#FB542B" fill-opacity="0.2"/><circle cx="11" cy="11" r="2.5" stroke="#FFF" stroke-width="1.5"/><path d="M13 13l2.5 2.5" stroke="#FFF" stroke-width="1.5" stroke-linecap="round"/></svg>`,
      brave: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#26160F" stroke="#FB542B" stroke-opacity="0.3"/><path d="M12 4L5 7v6c0 4 3 7 7 8 4-1 7-4 7-8V7l-7-3z" stroke="#FB542B" stroke-width="1.5" fill="#FB542B" fill-opacity="0.2"/><circle cx="11" cy="11" r="2.5" stroke="#FFF" stroke-width="1.5"/><path d="M13 13l2.5 2.5" stroke="#FFF" stroke-width="1.5" stroke-linecap="round"/></svg>`,
      fetch: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#06201B" stroke="#10B981" stroke-opacity="0.3"/><path d="M4 14.899A7 7 0 1115.71 8h1.79a4.5 4.5 0 012.5 8.242M12 12v9m0 0l-3-3m3 3l3-3" stroke="#34D399" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
      puppeteer: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#0C1D1B" stroke="#00D8A2" stroke-opacity="0.4"/><circle cx="12" cy="8" r="4" stroke="#00D8A2" stroke-width="1.5"/><path d="M6 18c0-3.3 2.7-6 6-6s6 2.7 6 6" stroke="#00D8A2" stroke-width="1.5"/><path d="M4 4l5 4M20 4l-5 4" stroke="#6EE7B7" stroke-width="1.5"/></svg>`,
      playwright: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#1C1824" stroke="#45BA4B" stroke-opacity="0.4"/><circle cx="9" cy="12" r="5" stroke="#22C55E" stroke-width="1.5"/><circle cx="15" cy="12" r="5" stroke="#EF4444" stroke-width="1.5"/></svg>`,
      memory: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#1E162A" stroke="#A855F7" stroke-opacity="0.4"/><rect x="6" y="6" width="12" height="12" rx="2" stroke="#C084FC" stroke-width="1.5"/><path d="M9 3v3M15 3v3M9 18v3M15 18v3M3 9h3M3 15h3M18 9h3M18 15h3" stroke="#A855F7" stroke-width="1.5" stroke-linecap="round"/></svg>`,
      notion: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="#FFFFFF"><path d="M4.459 4.208c.746.606 1.026.56 2.428.466l11.377-.84c1.12-.093 1.587.374 1.353 1.493l-1.96 9.42c-.234 1.12-.887 1.586-2.007 1.68l-11.377.84c-1.12.093-1.633-.42-1.353-1.54l1.539-7.464c.28-1.12.046-1.586-1.026-2.193L3 5.42l1.459-1.213zm3.78 2.893l-1.353 6.626c-.094.466.093.746.607.7l1.493-.094 1.306-6.44 3.733 6.16 2.38-.14 1.4-6.86c.094-.467-.093-.747-.607-.7l-1.493.093-1.307 6.44-3.733-6.16-2.427.375z"/></svg>`,
      slack: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><path d="M5.5 10a2.5 2.5 0 100-5 2.5 2.5 0 000 5z" fill="#E01E5A"/><path d="M7 10h3V7.5A2.5 2.5 0 007.5 5 2.5 2.5 0 005 7.5c0 .28.05.54.13.79L7 10z" fill="#E01E5A"/><path d="M14 5.5a2.5 2.5 0 105 0 2.5 2.5 0 00-5 0z" fill="#36C5F0"/><path d="M14 7v3h2.5A2.5 2.5 0 0019 7.5 2.5 2.5 0 0016.5 5c-.28 0-.54.05-.79.13L14 7z" fill="#36C5F0"/><path d="M18.5 14a2.5 2.5 0 100 5 2.5 2.5 0 000-5z" fill="#2EB67D"/><path d="M17 14h-3v2.5a2.5 2.5 0 002.5 2.5 2.5 2.5 0 002.5-2.5c0-.28-.05-.54-.13-.79L17 14z" fill="#2EB67D"/><path d="M10 18.5a2.5 2.5 0 10-5 0 2.5 2.5 0 005 0z" fill="#ECB22E"/><path d="M10 17v-3H7.5A2.5 2.5 0 005 16.5 2.5 2.5 0 007.5 19c.28 0 .54-.05.79-.13L10 17z" fill="#ECB22E"/></svg>`,
      supabase: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><path d="M13.4 2.1c-.8-.9-2.2-.4-2.3.8l-1.3 10.3h7.6c1.3 0 2 1.5 1.2 2.4L9.8 22.9c-.8.9-2.2.4-2.3-.8l1.3-10.3H1.2C0 11.8-.7 10.3.1 9.4L8.9 1.1c.9-.9 2.4-.4 2.5.8l-.8 7.3h4.9c.7 0 1.2-.6.9-1.2L13.4 2.1z" fill="#3ECF8E"/></svg>`,
      kater: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="6" fill="#2DD4BF"/><path d="M7 6v12M17 6l-7 6 7 6" stroke="#0B0D10" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
      linear: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#1C1D29" stroke="#5E6AD2" stroke-opacity="0.4"/><path d="M6 18L18 6M6 12l6-6M12 18l6-6" stroke="#828FFF" stroke-width="1.8" stroke-linecap="round"/></svg>`,
      jira: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#111B2C" stroke="#2684FF" stroke-opacity="0.4"/><path d="M12 3L4 11l8 8 8-8-8-8z" fill="#2684FF"/><path d="M12 7l4 4-4 4-4-4 4-4z" fill="#FFF"/></svg>`,
      huggingface: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#2E2310" stroke="#FFD21E" stroke-opacity="0.4"/><circle cx="12" cy="12" r="7" fill="#FFD21E"/><circle cx="9.5" cy="10.5" r="1" fill="#000"/><circle cx="14.5" cy="10.5" r="1" fill="#000"/><path d="M9 14.5c1 1.5 5 1.5 6 0" stroke="#000" stroke-width="1.2" stroke-linecap="round"/></svg>`,
      perplexity: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#101F22" stroke="#22B8CF" stroke-opacity="0.4"/><path d="M12 4v16M4 12h16M6.3 6.3l11.4 11.4M6.3 17.7L17.7 6.3" stroke="#22B8CF" stroke-width="1.8" stroke-linecap="round"/></svg>`,
      resend: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#000" stroke="#333"/><path d="M5 7h14l-7 6-7-6z" fill="#FFF"/><path d="M5 7v10h14V7" stroke="#FFF" stroke-width="1.5"/></svg>`,
      figma: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#1E1E1E"/><circle cx="9" cy="6" r="3" fill="#F24E1E"/><circle cx="15" cy="6" r="3" fill="#FF7262"/><circle cx="9" cy="12" r="3" fill="#A259FF"/><circle cx="15" cy="12" r="3" fill="#1ABCFE"/><circle cx="9" cy="18" r="3" fill="#0ACF83"/></svg>`,
      hubspot: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#251610" stroke="#FF7A59" stroke-opacity="0.4"/><circle cx="12" cy="12" r="4" stroke="#FF7A59" stroke-width="2"/><circle cx="12" cy="4" r="2" fill="#FF7A59"/><circle cx="19" cy="12" r="2" fill="#FF7A59"/><path d="M12 6v2M16 12h1" stroke="#FF7A59" stroke-width="2"/></svg>`,
      firecrawl: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#2A170A" stroke="#F97316" stroke-opacity="0.4"/><path d="M12 3c-1 3-4 5-4 9a4 4 0 008 0c0-4-3-6-4-9z" fill="#F97316"/><path d="M12 11c-.5 1-2 2-2 3.5a2 2 0 004 0c0-1.5-1.5-2.5-2-3.5z" fill="#FEF08A"/></svg>`,
      exa: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#141E28" stroke="#38BDF8" stroke-opacity="0.4"/><circle cx="12" cy="12" r="6" stroke="#38BDF8" stroke-width="1.8"/><path d="M8 8l8 8M16 8l-8 8" stroke="#38BDF8" stroke-width="1.5"/></svg>`,
      katerdoctor: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#1C2030" stroke="#38BDF8" stroke-opacity="0.4"/><path d="M12 4v16M4 12h16" stroke="#38BDF8" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="12" r="9" stroke="#38BDF8" stroke-width="1.5"/></svg>`,
      katere2e: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#112528" stroke="#2DD4BF" stroke-opacity="0.4"/><path d="M4 12l5 5L20 7" stroke="#2DD4BF" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
      katerpotetomode: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#2E1C14" stroke="#FB923C" stroke-opacity="0.4"/><circle cx="12" cy="12" r="6" fill="#F97316"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4" stroke="#FDBA74" stroke-width="1.5" stroke-linecap="round"/></svg>`,
      prgate: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#1E192B" stroke="#A855F7" stroke-opacity="0.4"/><circle cx="18" cy="18" r="3" stroke="#C084FC" stroke-width="1.5"/><circle cx="6" cy="6" r="3" stroke="#C084FC" stroke-width="1.5"/><path d="M13 6h3a2 2 0 0 1 2 2v7M6 9v12" stroke="#C084FC" stroke-width="1.5" stroke-linecap="round"/></svg>`,
      cifixer: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#261A1D" stroke="#F43F5E" stroke-opacity="0.4"/><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" stroke="#FB7185" stroke-width="1.5" fill="#FB7185" fill-opacity="0.2"/></svg>`,
      chefgroepskills: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#1A202C" stroke="#E2E8F0" stroke-opacity="0.3"/><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="#94A3B8" stroke-width="1.5" stroke-linecap="round"/></svg>`,
      compoundengineering: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#1A1829" stroke="#818CF8" stroke-opacity="0.4"/><path d="M4 19.5A2.5 2.5 0 016.5 17H20" stroke="#818CF8" stroke-width="1.5"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" stroke="#818CF8" stroke-width="1.5"/></svg>`,
      docker: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#0B1D2D" stroke="#2496ED" stroke-opacity="0.4"/><path d="M4 13h16c0 3.5-3 6-8 6s-8-2.5-8-6z" fill="#2496ED" fill-opacity="0.3" stroke="#2496ED" stroke-width="1.5"/><rect x="6" y="9" width="2" height="2" fill="#2496ED"/><rect x="9" y="9" width="2" height="2" fill="#2496ED"/><rect x="12" y="9" width="2" height="2" fill="#2496ED"/><rect x="9" y="6" width="2" height="2" fill="#2496ED"/></svg>`,
      kubernetes: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#101C33" stroke="#326CE5" stroke-opacity="0.4"/><polygon points="12 3 20 7.5 20 16.5 12 21 4 16.5 4 7.5" stroke="#326CE5" stroke-width="1.5" fill="#326CE5" fill-opacity="0.2"/><circle cx="12" cy="12" r="3" stroke="#FFF" stroke-width="1.5"/></svg>`,
      terraform: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#1D172E" stroke="#844FBA" stroke-opacity="0.4"/><polygon points="4 4 10 7.5 10 14.5 4 11" fill="#844FBA"/><polygon points="11 8 17 11.5 17 18.5 11 15" fill="#844FBA"/><polygon points="18 4 24 7.5 24 14.5 18 11" fill="#844FBA" fill-opacity="0.7"/></svg>`,
      discord: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#181A35" stroke="#5865F2" stroke-opacity="0.4"/><path d="M18.5 6.5A14.8 14.8 0 0 0 14.7 5c-.2.4-.4.8-.5 1.2a13.7 13.7 0 0 0-4.4 0A8.4 8.4 0 0 0 9.3 5c-1.4.5-2.7 1-3.8 1.5C3.2 10.2 2.6 15 3 19.8a15 15 0 0 0 4.6 2.3c.4-.5.7-1 1-1.6a9.8 9.8 0 0 1-1.6-.8c.1-.1.3-.2.4-.3 3.1 1.4 6.5 1.4 9.6 0 .1.1.3.2.4.3-.5.3-1 .6-1.6.8.3.6.6 1.1 1 1.6a15 15 0 0 0 4.6-2.3c.5-5.5-.9-10.2-2.5-13.3z" fill="#5865F2"/></svg>`,
      telegram: `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="5" fill="#0C1D2B" stroke="#229ED9" stroke-opacity="0.4"/><path d="M19.5 4.5l-16 6.2c-1.1.4-1.1 1.1-.2 1.4l4.1 1.3 9.5-6c.4-.3.9-.1.5.2l-7.7 7 0 0-.3 4.2c.4 0 .6-.2.8-.4l2-1.9 4.2 3.1c.8.4 1.3.2 1.5-.7l2.8-13.2c.3-1.1-.4-1.6-1.2-1.2z" fill="#229ED9"/></svg>`
    };

    function getBrandSvg(name, sizeClass = "w-full h-full") {
      if (!name) return BRAND_SVGS.kater;
      const key = name.toLowerCase().replace(/[^a-z0-9]/g, '');
      if (BRAND_SVGS[key]) {
        return BRAND_SVGS[key];
      }
      // Clean fallback icon for any unlisted MCP
      const initial = (name[0] || 'M').toUpperCase();
      return `<svg class="w-full h-full" viewBox="0 0 24 24" fill="none">
        <rect width="24" height="24" rx="5" fill="#151B26" stroke="#242F42"/>
        <text x="12" y="16" font-family="'JetBrains Mono', monospace" font-weight="700" font-size="11" fill="#2DD4BF" text-anchor="middle">${initial}</text>
      </svg>`;
    }

    let state = {
      servers: [],
      toolkits: [],
      filter: 'all',
      category: 'all',
      searchQuery: '',
      viewMode: 'grid',
      currentConnectingApp: null,
      telemetryEvents: [],
      browserSessions: [],
      prs: [],
      automations: []
    };

    function setTab(tabId) {
      const tabs = ['integrations', 'apps', 'hub', 'discovery', 'overview', 'browser', 'prgate', 'automations', 'telemetry', 'settings'];
      tabs.forEach(t => {
        const viewEl = document.getElementById('view-' + t);
        const navEl = document.getElementById('nav-' + t);
        if (viewEl) viewEl.classList.toggle('hidden', t !== tabId);
        if (navEl) {
          if (t === tabId) {
            navEl.className = 'w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition bg-[#1C2433] text-[#2DD4BF] border border-[#2DD4BF]/30 shadow-[0_0_10px_rgba(45,212,191,0.1)]';
          } else {
            navEl.className = 'w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition text-[#9CA3AF] hover:text-white hover:bg-[#151B26] border border-transparent';
          }
        }
      });
    }

    function setViewMode(mode) {
      state.viewMode = mode;
      const btnGrid = document.getElementById('btn-view-grid');
      const btnOutline = document.getElementById('btn-view-outline');
      const gridEl = document.getElementById('apps-grid');
      const outlineEl = document.getElementById('apps-outline-view');

      if (mode === 'grid') {
        btnGrid.className = 'flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-[#242F42] text-white transition';
        btnOutline.className = 'flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium text-[#8B949E] hover:text-white transition';
        gridEl.classList.remove('hidden');
        outlineEl.classList.add('hidden');
      } else {
        btnGrid.className = 'flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium text-[#8B949E] hover:text-white transition';
        btnOutline.className = 'flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-[#242F42] text-white transition';
        gridEl.classList.add('hidden');
        outlineEl.classList.remove('hidden');
        renderOutlineView();
      }
    }

    function filterConnected(type) {
      state.filter = type;
      document.getElementById('filter-all').className = type === 'all' 
        ? 'px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-[#242F42] text-white border border-[#2DD4BF]/40 transition shadow-sm'
        : 'px-3.5 py-1.5 rounded-lg text-xs font-medium text-[#8B949E] hover:text-white hover:bg-[#151B26] border border-[#242F42] transition';
      document.getElementById('filter-connected').className = type === 'connected'
        ? 'px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-[#242F42] text-white border border-[#2DD4BF]/40 transition shadow-sm'
        : 'px-3.5 py-1.5 rounded-lg text-xs font-medium text-[#8B949E] hover:text-white hover:bg-[#151B26] border border-[#242F42] transition';
      renderIntegrationsGrid();
        renderAppsGrid();
      if (state.viewMode === 'outline') renderOutlineView();
    }

    function filterCategory(cat) {
      state.category = cat;
      renderAppsGrid();
      if (state.viewMode === 'outline') renderOutlineView();
    }

    function handleAppSearch(q) {
      state.searchQuery = (q || '').toLowerCase().trim();
      renderAppsGrid();
      if (state.viewMode === 'outline') renderOutlineView();
    }


    let integrationsState = {
      filterType: 'all', // 'all', 'server', 'plugin', 'connected'
      category: 'all',
      transport: 'all',
      searchQuery: ''
    };

    function setIntegrationsFilter(type) {
      integrationsState.filterType = type;
      const pills = ['all', 'server', 'plugin', 'connected'];
      pills.forEach(p => {
        const btn = document.getElementById('btn-int-filter-' + p);
        if (btn) {
          if (p === type) {
            btn.className = 'px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-[#242F42] text-white border border-[#2DD4BF]/40 transition shadow-sm';
          } else {
            btn.className = 'px-3.5 py-1.5 rounded-lg text-xs font-medium text-[#8B949E] hover:text-white hover:bg-[#151B26] border border-[#242F42] transition';
          }
        }
      });
      renderIntegrationsGrid();
    }

    function filterIntegrationsCategory(cat) {
      integrationsState.category = cat;
      renderIntegrationsGrid();
    }

    function filterIntegrationsTransport(trans) {
      integrationsState.transport = trans;
      renderIntegrationsGrid();
    }

    function handleIntegrationsSearch(q) {
      integrationsState.searchQuery = (q || '').toLowerCase().trim();
      renderIntegrationsGrid();
    }

    function getFilteredIntegrations() {
      let list = state.servers || [];
      
      // Filter by type
      if (integrationsState.filterType === 'server') {
        list = list.filter(s => (s.itemType || 'server') === 'server');
      } else if (integrationsState.filterType === 'plugin') {
        list = list.filter(s => s.itemType === 'plugin' || s.transport === 'plugin');
      } else if (integrationsState.filterType === 'connected') {
        list = list.filter(s => s.enabled);
      }

      // Filter by category
      if (integrationsState.category !== 'all') {
        list = list.filter(s => s.category === integrationsState.category);
      }

      // Filter by transport
      if (integrationsState.transport !== 'all') {
        list = list.filter(s => s.transport === integrationsState.transport);
      }

      // Filter by search query
      if (integrationsState.searchQuery) {
        const q = integrationsState.searchQuery;
        list = list.filter(s => 
          (s.displayName || s.name).toLowerCase().includes(q) ||
          (s.description || '').toLowerCase().includes(q) ||
          (s.category || '').toLowerCase().includes(q) ||
          (s.profiles || []).some(p => p.toLowerCase().includes(q)) ||
          (s.actions || []).some(a => a.name.toLowerCase().includes(q) || a.label.toLowerCase().includes(q))
        );
      }

      return list;
    }

    function renderIntegrationsGrid() {
      const grid = document.getElementById('integrations-grid');
      if (!grid) return;
      
      const filtered = getFilteredIntegrations();
      const totalCount = state.servers.length;
      const activeCount = state.servers.filter(s => s.enabled).length;
      const pluginCount = state.servers.filter(s => s.itemType === 'plugin' || s.transport === 'plugin').length;
      const totalActions = state.servers.reduce((sum, s) => sum + (s.actions?.length || 1), 0);

      // Update statistics
      const statTotal = document.getElementById('stat-integrations-total');
      if (statTotal) statTotal.innerText = `${totalCount}`;
      const statActive = document.getElementById('stat-integrations-active');
      if (statActive) statActive.innerText = `${activeCount} Active`;
      const statTools = document.getElementById('stat-integrations-tools');
      if (statTools) statTools.innerText = `${totalActions}+ Tools`;
      const statPlugins = document.getElementById('stat-integrations-plugins');
      if (statPlugins) statPlugins.innerText = `${pluginCount} Plugins`;
      
      const pillTotal = document.getElementById('integrations-total-pill');
      if (pillTotal) pillTotal.innerText = `${totalCount} Available`;

      const displayCount = document.getElementById('integrations-display-count');
      if (displayCount) displayCount.innerText = `Showing ${filtered.length} of ${totalCount} items`;

      if (filtered.length === 0) {
        grid.innerHTML = `
          <div class="col-span-full py-16 text-center text-[#8B949E] bg-[#10141C] border border-[#242F42] rounded-2xl outline-card p-6">
            <div class="w-12 h-12 rounded-xl bg-[#151B26] border border-[#242F42] flex items-center justify-center mx-auto text-[#8B949E] mb-3">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            </div>
            <div class="text-sm font-semibold text-white">No matching integrations found</div>
            <div class="text-xs text-[#8B949E] mt-1 max-w-sm mx-auto">Try clearing search filters or selecting another category from the toolbar above.</div>
            <button onclick="setIntegrationsFilter('all'); document.getElementById('integrations-search-input').value = ''; integrationsState.searchQuery = ''; renderIntegrationsGrid();" class="mt-4 px-3.5 py-1.5 rounded-lg bg-[#151B26] border border-[#242F42] hover:border-[#2DD4BF]/50 text-xs font-semibold text-white transition">
              Reset Filters
            </button>
          </div>
        `;
        return;
      }

      const shieldSvg = `<svg viewBox="0 0 24 24" width="13" height="13" fill="none"><path d="M12 2L4 5v6.09c0 5.05 3.41 9.76 8 10.91 4.59-1.15 8-5.86 8-10.91V5l-8-3z" stroke="#38BDF8" stroke-width="1.8" fill="rgba(56,189,248,0.15)" stroke-linecap="round" stroke-linejoin="round"/><path d="M9 11.5l2 2 4-4" stroke="#38BDF8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

      grid.innerHTML = filtered.map(item => {
        const isConnected = item.enabled;
        const isPlugin = item.itemType === 'plugin' || item.transport === 'plugin';
        const brandSvg = getBrandSvg(item.name);
        const displayName = item.displayName || item.name;
        const actionsCount = item.actions?.length || 1;
        const transport = item.transport || 'stdio';

        // Transport badge color
        const transportBadge = transport === 'native' 
          ? '<span class="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">native</span>'
          : transport === 'http' || transport === 'sse'
          ? '<span class="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">http stream</span>'
          : transport === 'plugin'
          ? '<span class="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">satellite</span>'
          : '<span class="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">stdio cli</span>';

        const typeBadge = isPlugin
          ? '<span class="text-[10px] font-semibold px-2 py-0.5 rounded bg-purple-500/15 text-purple-300 border border-purple-500/30">Plugin</span>'
          : '<span class="text-[10px] font-semibold px-2 py-0.5 rounded bg-[#2DD4BF]/15 text-[#2DD4BF] border border-[#2DD4BF]/30">MCP Server</span>';

        const statusPill = isConnected
          ? `<span class="flex items-center gap-1 text-[11px] font-semibold text-emerald-400">
               <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
               Active
             </span>`
          : `<span class="flex items-center gap-1 text-[11px] font-medium text-[#8B949E]">
               <span class="w-1.5 h-1.5 rounded-full bg-[#374151]"></span>
               Ready
             </span>`;

        return `
          <div class="p-4 rounded-xl bg-[#10141C] border border-[#242F42] outline-card flex flex-col justify-between space-y-3 min-h-[220px]">
            <div class="space-y-2.5">
              <!-- Top Row: Icon + Name + Type -->
              <div class="flex items-start justify-between gap-2.5">
                <div class="flex items-center gap-3 min-w-0">
                  <div class="w-10 h-10 rounded-lg bg-[#151B26] border border-[#242F42] flex items-center justify-center p-2 flex-shrink-0 shadow-inner">
                    ${brandSvg}
                  </div>
                  <div class="min-w-0">
                    <div class="flex items-center gap-1.5">
                      <h3 class="font-bold text-xs text-white truncate">${displayName}</h3>
                      ${item.verified ? `<span title="Verified Enterprise Integration">${shieldSvg}</span>` : ''}
                    </div>
                    <div class="flex items-center gap-1.5 mt-1">
                      ${typeBadge}
                      ${transportBadge}
                    </div>
                  </div>
                </div>
                ${statusPill}
              </div>

              <!-- Description -->
              <p class="text-xs text-[#8B949E] line-clamp-2 leading-relaxed">${item.description || 'Verified Model Context Protocol integration connector.'}</p>

              <!-- Profiles / Tools Tags -->
              <div class="flex flex-wrap items-center gap-1 pt-1">
                <span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#151B26] border border-[#242F42] text-[#8B949E] flex items-center gap-1">
                  <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
                  ${actionsCount} ${actionsCount === 1 ? 'Action' : 'Actions'}
                </span>
                ${(item.profiles || []).slice(0, 2).map(p => `
                  <span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#151B26] border border-[#242F42] text-[#8B949E]">${p}</span>
                `).join('')}
              </div>
            </div>

            <!-- Bottom Action Controls -->
            <div class="pt-3 border-t border-[#242F42] flex items-center justify-between gap-2 mt-auto">
              <button onclick="openConnectModal('${item.name}')" class="px-2.5 py-1.5 rounded-lg border border-[#242F42] hover:bg-[#1C2433] text-[11px] font-medium text-[#8B949E] hover:text-white transition flex items-center gap-1.5">
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
                Config
              </button>

              <button onclick="toggleIntegrationState('${item.name}')" class="px-3.5 py-1.5 rounded-lg text-xs font-bold transition ${
                isConnected
                  ? 'bg-rose-500/15 text-rose-300 border border-rose-500/30 hover:bg-rose-500/25'
                  : 'bg-[#2DD4BF] text-[#0B0D10] hover:bg-[#20bdab] shadow-[0_0_12px_rgba(45,212,191,0.2)]'
              }">
                ${isConnected ? 'Disconnect' : 'Connect'}
              </button>
            </div>
          </div>
        `;
      }).join('');
    }

    async function toggleIntegrationState(name) {
      try {
        const item = state.servers.find(s => s.name === name);
        const endpoint = item?.enabled 
          ? `/api/mcp/servers/${name}/disable` 
          : `/api/mcp/servers/${name}/enable`;
        
        await fetch(endpoint, { method: 'POST' });
        await loadData();
        addTelemetryLine(`Toggled integration [${name}] -> ${item?.enabled ? 'Disabled' : 'Enabled'}`);
      } catch (err) {
        alert('Failed updating integration: ' + err.message);
      }
    }

    async function loadData() {
      try {
        const [resInt, resTk, resBrw, resPr, resAuto] = await Promise.all([
          fetch('/api/integrations').then(r => r.json()),
          fetch('/api/integrations/toolkits').then(r => r.json()),
          fetch('/api/browser/sessions').then(r => r.json()).catch(() => ({ sessions: [] })),
          fetch('/api/pr/items').then(r => r.json()).catch(() => ({ prs: [] })),
          fetch('/api/automations').then(r => r.json()).catch(() => ({ automations: [] }))
        ]);

        state.servers = resInt.integrations || [];
        state.toolkits = resTk.toolkits || [];
        state.browserSessions = resBrw.sessions || [];
        state.prs = resPr.prs || [];
        state.automations = resAuto.automations || [];

        renderAppsGrid();
        renderToolkits();
        renderPlaygroundOptions();
        renderDiscoveryGrid();
        renderBrowserSessions();
        renderPrs();
        renderAutomations();
        updateStats(resInt.stats);
      } catch (err) {
        console.error('Failed loading dashboard data:', err);
      }
    }

    function updateStats(stats) {
      const activeCount = state.servers.filter(s => s.enabled).length;
      const totalCount = state.servers.length;
      
      const badge = document.getElementById('badge-active-apps');
      if (badge) badge.innerText = `${activeCount} Active`;
      
      const statActive = document.getElementById('stat-active-servers');
      if (statActive) statActive.innerText = `${activeCount} / ${totalCount}`;
    }

    function getFilteredServers() {
      let filtered = state.servers;
      if (state.filter === 'connected') {
        filtered = filtered.filter(s => s.enabled);
      }
      if (state.category !== 'all') {
        filtered = filtered.filter(s => s.category === state.category);
      }
      if (state.searchQuery) {
        filtered = filtered.filter(s => 
          (s.displayName || s.name).toLowerCase().includes(state.searchQuery) ||
          (s.description || '').toLowerCase().includes(state.searchQuery) ||
          (s.category || '').toLowerCase().includes(state.searchQuery)
        );
      }
      return filtered;
    }

    function renderAppsGrid() {
      const grid = document.getElementById('apps-grid');
      if (!grid) return;
      const filtered = getFilteredServers();

      if (filtered.length === 0) {
        grid.innerHTML = `
          <div class="col-span-full py-12 text-center text-[#8B949E] bg-[#10141C] border border-[#242F42] rounded-2xl outline-card">
            <div class="text-sm font-semibold text-white">No applications found</div>
            <div class="text-xs mt-1">Try adjusting your search query or filters.</div>
          </div>
        `;
        return;
      }

      const shieldSvg = `<svg viewBox="0 0 24 24" width="14" height="14" fill="none"><path d="M12 2L4 5v6.09c0 5.05 3.41 9.76 8 10.91 4.59-1.15 8-5.86 8-10.91V5l-8-3z" stroke="#4880FF" stroke-width="1.8" fill="rgba(72,128,255,0.15)" stroke-linecap="round" stroke-linejoin="round"/><path d="M9 11.5l2 2 4-4" stroke="#4880FF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

      grid.innerHTML = filtered.map(app => {
        const isConnected = app.enabled;
        const brandSvg = getBrandSvg(app.name);
        const displayName = app.displayName || app.name;
        const activeCount = app.activeCount || (isConnected ? 1 : 0);

        let buttonHtml = '';
        if (isConnected) {
          buttonHtml = `
            <div class="flex items-center gap-2">
              <span class="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1 shadow-sm">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                ${activeCount} Active
              </span>
              <button onclick="event.stopPropagation(); openConnectModal('${app.name}')" class="px-2 py-0.5 rounded-md border border-[#242F42] hover:bg-[#1C2433] text-[11px] font-medium text-[#8B949E] hover:text-white transition">
                + Config
              </button>
            </div>
          `;
        } else {
          buttonHtml = `
            <button onclick="event.stopPropagation(); openConnectModal('${app.name}')" class="px-3 py-1 rounded-md bg-[#2DD4BF] text-[#0B0D10] hover:bg-[#20bdab] text-xs font-bold transition shadow-[0_0_12px_rgba(45,212,191,0.15)]">
              Connect
            </button>
          `;
        }

        return `
          <div onclick="selectAppForDetails('${app.name}')" class="p-4 rounded-xl bg-[#10141C] outline-card flex items-center justify-between cursor-pointer group">
            <div class="flex items-center gap-3.5 min-w-0">
              <div class="w-10 h-10 rounded-lg bg-[#151B26] border border-[#242F42] flex items-center justify-center p-2 flex-shrink-0 group-hover:border-[#2DD4BF]/40 transition shadow-inner">
                ${brandSvg}
              </div>
              <div class="min-w-0">
                <div class="flex items-center gap-1.5">
                  <span class="font-bold text-sm text-white truncate">${displayName}</span>
                  ${app.verified ? `<span title="Verified Enterprise MCP">${shieldSvg}</span>` : ''}
                </div>
                <div class="text-xs text-[#8B949E] truncate capitalize font-medium">${app.category || 'Tool'} • ${app.actions?.length || 1} Actions</div>
              </div>
            </div>
            <div class="flex-shrink-0 ml-3">
              ${buttonHtml}
            </div>
          </div>
        `;
      }).join('');
    }

    function renderOutlineView() {
      const container = document.getElementById('apps-outline-view');
      if (!container) return;
      const filtered = getFilteredServers();

      // Group by category for crisp outline tree structure
      const grouped = {};
      filtered.forEach(s => {
        const cat = s.category || 'other';
        if (!grouped[cat]) grouped[cat] = [];
        grouped[cat].push(s);
      });

      const categories = Object.keys(grouped);
      if (categories.length === 0) {
        container.innerHTML = `
          <div class="py-10 text-center text-[#8B949E] bg-[#10141C] border border-[#242F42] rounded-xl">
            No items in outline hierarchy.
          </div>
        `;
        return;
      }

      container.innerHTML = categories.map(cat => {
        const catServers = grouped[cat];
        return `
          <div class="border border-[#242F42] rounded-xl bg-[#10141C] p-4 space-y-3 outline-card">
            <div class="flex items-center justify-between border-b border-[#242F42] pb-2.5">
              <div class="flex items-center gap-2">
                <span class="w-2 h-2 rounded bg-[#2DD4BF]"></span>
                <span class="text-xs font-bold uppercase tracking-wider text-white">${cat} Integrations</span>
                <span class="text-xs text-[#8B949E] font-mono font-medium">(${catServers.length} Servers)</span>
              </div>
              <span class="text-[11px] text-[#8B949E]">Hierarchical Schema Map</span>
            </div>

            <div class="pl-4 border-l-2 border-[#242F42] space-y-3 mt-2">
              ${catServers.map(s => {
                const actions = s.actions || [];
                return `
                  <div class="tree-branch bg-[#151B26] border border-[#242F42] rounded-lg p-3 space-y-2">
                    <div class="flex items-center justify-between">
                      <div class="flex items-center gap-2">
                        <div class="w-5 h-5">${getBrandSvg(s.name)}</div>
                        <span class="font-bold text-xs text-white font-mono">${s.displayName || s.name}</span>
                        <span class="text-[10px] px-1.5 py-0.5 rounded ${s.enabled ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-[#242F42] text-[#8B949E]'} font-mono">
                          ${s.enabled ? 'ENABLED' : 'DISABLED'}
                        </span>
                      </div>
                      <button onclick="openConnectModal('${s.name}')" class="text-[11px] px-2 py-0.5 rounded bg-[#242F42] hover:bg-[#2DD4BF] hover:text-[#0B0D10] text-[#E2E8F0] font-medium transition">
                        Inspect Schema
                      </button>
                    </div>

                    <!-- Actions tree breakdown -->
                    <div class="pl-4 border-l border-[#2E3C52] space-y-1.5 mt-2">
                      ${actions.map(a => `
                        <div class="flex items-center justify-between text-xs font-mono py-1 px-2 rounded bg-[#0D1017] border border-white/5">
                          <div class="flex items-center gap-2">
                            <span class="text-[#2DD4BF]">›</span>
                            <span class="text-white font-semibold">${a.name || a.id}</span>
                            <span class="text-[#8B949E] text-[10px]">(${Object.keys(a.parameters?.properties || {}).join(', ') || 'no params'})</span>
                          </div>
                          <span class="text-[10px] px-1.5 py-0.2 rounded bg-[#242F42] text-amber-300">${a.risk || 'low'}</span>
                        </div>
                      `).join('')}
                    </div>
                  </div>
                `;
              }).join('')}
            </div>
          </div>
        `;
      }).join('');
    }

    function renderToolkits() {
      const grid = document.getElementById('toolkits-grid');
      if (!grid) return;

      grid.innerHTML = state.toolkits.map(tk => {
        return `
          <div class="p-5 rounded-xl bg-[#10141C] border border-[#242F42] outline-card flex flex-col justify-between space-y-4">
            <div class="space-y-3">
              <div class="flex items-start justify-between gap-3">
                <div>
                  <div class="flex items-center gap-2">
                    <h3 class="text-base font-bold text-white tracking-tight">${tk.name}</h3>
                    <span class="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-[#2DD4BF]/10 text-[#2DD4BF] border border-[#2DD4BF]/30 whitespace-nowrap">${tk.badge}</span>
                  </div>
                  <p class="text-xs text-[#8B949E] mt-1.5 leading-relaxed">${tk.description}</p>
                </div>
              </div>

              <div class="space-y-2 pt-1">
                <div class="text-[10px] font-bold text-[#8B949E] uppercase tracking-wider">Included MCP Servers:</div>
                <div class="flex flex-wrap gap-2">
                  ${tk.servers.map(sname => `
                    <span class="inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-[#151B26] border border-[#242F42] hover:border-[#2DD4BF]/40 text-xs font-mono text-[#E2E8F0] shadow-sm transition">
                      <span class="w-4 h-4 flex-shrink-0 flex items-center justify-center">
                        ${getBrandSvg(sname)}
                      </span>
                      <span class="leading-none text-[11px] font-medium text-slate-200">${sname}</span>
                    </span>
                  `).join('')}
                </div>
              </div>
            </div>

            <div class="flex items-center justify-between pt-3 border-t border-[#242F42] gap-3 mt-auto">
              <div class="text-xs text-[#8B949E] flex items-center gap-1.5">
                <span>Recommended Profile:</span>
                <span class="font-mono text-white font-bold px-2 py-0.5 rounded bg-[#151B26] border border-[#242F42] text-[11px]">${tk.recommendedProfile}</span>
              </div>
              <button onclick="enableToolkit('${tk.id}')" class="px-3.5 py-2 rounded-lg bg-[#2DD4BF] text-[#0B0D10] text-xs font-bold hover:bg-[#20bdab] transition whitespace-nowrap flex items-center gap-1.5 shadow-[0_0_12px_rgba(45,212,191,0.2)] flex-shrink-0">
                <span>Enable All</span>
                <span class="px-1.5 py-0.2 rounded-full bg-[#0B0D10]/20 text-[#0B0D10] font-mono font-black text-[10px]">(${tk.servers.length})</span>
              </button>
            </div>
          </div>
        `;
      }).join('');
    }

    function renderDiscoveryGrid() {
      const grid = document.getElementById('discovery-grid');
      if (!grid) return;

      const curated = [
        { name: 'firecrawl', title: 'Firecrawl LLM Scraper', desc: 'Converts entire web pages into clean LLM markdown.', tags: ['Scraping', 'Web'] },
        { name: 'notion', title: 'Notion Database Sync', desc: 'Sync knowledge base, engineering docs, and agile boards.', tags: ['Workspace', 'Docs'] },
        { name: 'github', title: 'GitHub CI & PR Agent', desc: 'Automate repo reviews, file commits, and workflow runs.', tags: ['DevOps', 'Code'] },
        { name: 'perplexity', title: 'Perplexity Search', desc: 'Grounded web queries with deep multi-source citations.', tags: ['AI', 'Search'] },
        { name: 'resend', title: 'Resend Transactional', desc: 'Deliver instant automated emails and client reports.', tags: ['Email', 'API'] },
        { name: 'supabase', title: 'Supabase Vector & SQL', desc: 'Serverless PostgreSQL with pgvector embeddings.', tags: ['Database', 'Cloud'] }
      ];

      grid.innerHTML = curated.map(item => `
        <div class="p-5 rounded-xl bg-[#10141C] border border-[#242F42] outline-card flex flex-col justify-between space-y-3 min-h-[180px]">
          <div class="space-y-3">
            <div class="flex items-start justify-between gap-3">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-[#151B26] border border-[#242F42] flex items-center justify-center p-2 flex-shrink-0 shadow-inner">
                  ${getBrandSvg(item.name)}
                </div>
                <div>
                  <h4 class="text-xs font-bold text-white tracking-tight">${item.title}</h4>
                  <div class="flex flex-wrap gap-1 mt-1">
                    ${item.tags.map(t => `<span class="text-[9px] font-semibold px-2 py-0.5 rounded-md bg-[#151B26] border border-[#242F42] text-[#8B949E]">${t}</span>`).join('')}
                  </div>
                </div>
              </div>
            </div>
            <p class="text-xs text-[#8B949E] leading-relaxed">${item.desc}</p>
          </div>

          <div class="pt-3 border-t border-[#242F42] flex items-center justify-between mt-auto">
            <span class="text-[11px] text-emerald-400 font-mono font-medium flex items-center gap-1.5">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Verified MCP
            </span>
            <button onclick="openConnectModal('${item.name}')" class="px-3.5 py-1.5 rounded-lg bg-[#2DD4BF] text-[#0B0D10] text-xs font-bold hover:bg-[#20bdab] transition shadow-[0_0_12px_rgba(45,212,191,0.2)]">
              Install
            </button>
          </div>
        </div>
      `).join('');
    }

    function openConnectModal(name) {
      const server = state.servers.find(s => s.name === name);
      state.currentConnectingApp = server || { name, displayName: name, category: 'General' };

      document.getElementById('modal-app-name').innerText = `Configure ${server?.displayName || name}`;
      document.getElementById('modal-app-category').innerText = server?.category || 'Custom MCP Tool';
      document.getElementById('modal-app-icon').innerHTML = getBrandSvg(name);

      const body = document.getElementById('modal-connect-body');
      const isOAuth = (server?.authMethods || []).includes('oauth2');
      const isApiKey = (server?.authMethods || []).includes('apiKey') || !isOAuth;

      body.innerHTML = `
        <div class="text-xs text-[#8B949E] bg-[#151B26] p-3 rounded-lg border border-[#242F42]">
          ${server?.description || 'Configure credentials and activate this MCP server in Kater Dev Tools.'}
        </div>
        ${isOAuth ? `
          <div class="p-3 bg-[#151B26] border border-[#242F42] rounded-lg flex items-center justify-between">
            <div>
              <div class="text-xs font-bold text-white">OAuth 2.0 Direct Connect</div>
              <div class="text-[11px] text-[#8B949E]">1-Click authentication with scope delegation</div>
            </div>
            <button onclick="alert('OAuth flow initiated successfully!')" class="px-3 py-1.5 bg-[#2DD4BF] text-[#0B0D10] text-xs font-bold rounded-md hover:bg-[#20bdab]">
              Authorize
            </button>
          </div>
        ` : ''}
        ${isApiKey ? `
          <div class="space-y-2">
            <label class="block text-xs font-semibold text-white">API Key / Token</label>
            <input type="password" id="modal-input-apikey" placeholder="Enter API secret key..." class="w-full bg-[#151B26] border border-[#242F42] rounded-lg p-2 text-xs text-white font-mono focus:outline-none focus:border-[#2DD4BF]">
          </div>
        ` : ''}
      `;

      document.getElementById('modal-connect-app').classList.remove('hidden');
    }

    function closeConnectModal() {
      document.getElementById('modal-connect-app').classList.add('hidden');
      state.currentConnectingApp = null;
    }

    async function submitAppConnection() {
      if (!state.currentConnectingApp) return;
      const name = state.currentConnectingApp.name;
      try {
        await fetch(`/api/mcp/servers/${name}/enable`, { method: 'POST' });
        closeConnectModal();
        await loadData();
        addTelemetryLine(`Connected & enabled [${name}]`);
      } catch (err) {
        alert('Failed connecting: ' + err.message);
      }
    }

    function openCustomMcpModal() {
      document.getElementById('modal-custom-mcp').classList.remove('hidden');
    }

    function closeCustomMcpModal() {
      document.getElementById('modal-custom-mcp').classList.add('hidden');
    }

    async function submitCustomMcp() {
      const name = document.getElementById('custom-server-name').value.trim();
      const transport = document.getElementById('custom-server-transport').value;
      const command = document.getElementById('custom-server-command').value.trim();
      const category = document.getElementById('custom-server-category').value;

      if (!name) return alert('Server name is required');

      try {
        const res = await fetch('/api/mcp/servers', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name,
            transport,
            category,
            command: transport === 'stdio' ? command : undefined,
            url: transport === 'http' ? command : undefined,
            risk: 'medium'
          })
        });
        if (!res.ok) {
          const err = await res.json();
          return alert(err.error || 'Failed adding custom server');
        }
        closeCustomMcpModal();
        await loadData();
        addTelemetryLine(`Registered custom MCP server: ${name}`);
      } catch (err) {
        alert('Error: ' + err.message);
      }
    }

    function openRequestAppModal() {
      document.getElementById('modal-request-app').classList.remove('hidden');
    }

    function closeRequestAppModal() {
      document.getElementById('modal-request-app').classList.add('hidden');
    }

    function submitRequestApp() {
      const name = document.getElementById('request-app-name').value.trim();
      if (!name) return alert('Please enter an app name');
      closeRequestAppModal();
      alert(`Thank you! Request for "${name}" submitted to the Kater roadmap.`);
      addTelemetryLine(`App request submitted: ${name}`);
    }

    function renderPlaygroundOptions() {
      const select = document.getElementById('playground-action-select');
      if (!select) return;

      const actions = [];
      state.servers.forEach(s => {
        if (s.actions) {
          s.actions.forEach(a => actions.push({ app: s.displayName || s.name, action: a }));
        }
      });

      select.innerHTML = actions.map(item => `
        <option value="${item.action.id}">[${item.app}] ${item.action.label || item.action.name}</option>
      `).join('');

      if (actions.length > 0) {
        onPlaygroundActionChange(actions[0].action.id);
      }
    }

    function onPlaygroundActionChange(actionId) {
      let found = null;
      for (const s of state.servers) {
        const a = s.actions?.find(x => x.id === actionId);
        if (a) { found = a; break; }
      }
      if (found) {
        document.getElementById('playground-action-desc').innerHTML = `
          <strong>${found.label || found.name}</strong>: ${found.description}<br>
          <span class="text-emerald-400 font-mono text-[10px]">Risk: ${found.risk}</span>
        `;
        document.getElementById('playground-payload-input').value = JSON.stringify(found.exampleInput || {}, null, 2);
      }
    }

    async function runPlaygroundAction() {
      const out = document.getElementById('playground-output-result');
      const actionId = document.getElementById('playground-action-select').value;
      const rawPayload = document.getElementById('playground-payload-input').value;

      out.innerText = 'Executing action via Kater Gateway...';
      try {
        const payload = JSON.parse(rawPayload || '{}');
        const res = await fetch('/api/actions/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ actionId, params: payload })
        });
        const data = await res.json();
        out.innerText = JSON.stringify(data, null, 2);
        addTelemetryLine(`Action run [${actionId}] => ${data.status || 'OK'}`);
      } catch (err) {
        out.innerText = 'Execution error: ' + err.message;
      }
    }

    async function enableToolkit(id) {
      try {
        await fetch(`/api/integrations/toolkits/${id}/enable`, { method: 'POST' });
        await loadData();
        addTelemetryLine(`Enabled toolkit [${id}]`);
      } catch (err) {
        alert('Failed enabling toolkit: ' + err.message);
      }
    }

    function renderBrowserSessions() {
      const grid = document.getElementById('browser-sessions-grid');
      if (!grid) return;
      grid.innerHTML = state.browserSessions.map(b => `
        <div class="p-4 rounded-xl bg-[#10141C] border border-[#242F42] space-y-3 outline-card">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-white font-mono">${b.session_id}</span>
            <span class="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 uppercase font-bold">${b.state}</span>
          </div>
          <div class="text-xs font-semibold text-white">${b.label || b.title}</div>
          <div class="text-xs text-[#8B949E] font-mono truncate">${b.current_url}</div>
        </div>
      `).join('');
    }

    function renderPrs() {
      const container = document.getElementById('pr-list-container');
      if (!container) return;
      container.innerHTML = state.prs.map(p => `
        <div class="p-4 rounded-xl bg-[#10141C] border border-[#242F42] flex items-center justify-between outline-card">
          <div>
            <div class="text-xs font-bold text-white">#${p.number} — ${p.title}</div>
            <div class="text-[11px] text-[#8B949E]">Author: ${p.author} • Branch: ${p.branch}</div>
          </div>
          <span class="px-2 py-1 rounded text-xs font-bold ${p.status === 'clean' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'}">${p.status}</span>
        </div>
      `).join('');
    }

    function renderAutomations() {
      const container = document.getElementById('automations-list-container');
      if (!container) return;
      container.innerHTML = state.automations.map(a => `
        <div class="p-4 rounded-xl bg-[#10141C] border border-[#242F42] flex items-center justify-between outline-card">
          <div>
            <div class="text-xs font-bold text-white">${a.name}</div>
            <div class="text-[11px] text-[#8B949E] font-mono">Schedule: ${a.schedule} • Target: ${a.target}</div>
          </div>
          <span class="px-2 py-1 rounded text-xs font-mono bg-[#151B26] text-white border border-[#242F42]">${a.status}</span>
        </div>
      `).join('');
    }

    function addTelemetryLine(msg) {
      const box = document.getElementById('telemetry-log-box');
      if (!box) return;
      const time = new Date().toLocaleTimeString();
      const div = document.createElement('div');
      div.className = 'flex items-center gap-2';
      div.innerHTML = `<span class="text-[#8B949E]">[${time}]</span> <span class="text-[#2DD4BF]">›</span> <span>${msg}</span>`;
      box.appendChild(div);
      box.scrollTop = box.scrollHeight;
    }

    function clearTelemetryLog() {
      const box = document.getElementById('telemetry-log-box');
      if (box) box.innerHTML = '';
    }

    function selectAppForDetails(name) {
      openConnectModal(name);
    }

    function toggleProfileDropdown() {
      const menu = document.getElementById('profile-dropdown-menu');
      if (menu) menu.classList.toggle('hidden');
    }

    async function selectProfile(profile) {
      const displayEl = document.getElementById('profile-current-display');
      if (displayEl) displayEl.innerText = profile;
      
      const menu = document.getElementById('profile-dropdown-menu');
      if (menu) menu.classList.add('hidden');

      // Update options styling
      const list = document.getElementById('profile-options-list');
      if (list) {
        const buttons = list.querySelectorAll('button');
        buttons.forEach(btn => {
          const isSelected = btn.getAttribute('onclick')?.includes(`'${profile}'`);
          if (isSelected) {
            btn.className = 'w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs text-left bg-[#1C2433] text-[#2DD4BF] font-semibold transition';
            const badge = btn.querySelector('span:last-child');
            if (badge) {
              badge.className = 'text-[10px] text-[#2DD4BF] font-semibold';
              badge.innerText = 'Active';
            }
          } else {
            btn.className = 'w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs text-left hover:bg-[#151B26] text-slate-300 hover:text-white transition';
            const badge = btn.querySelector('span:last-child');
            if (badge && badge.innerText === 'Active') {
              badge.className = 'text-[10px] text-[#8B949E]';
              badge.innerText = 'Ready';
            }
          }
        });
      }

      await switchProfile(profile);
    }

    async function switchProfile(profile) {
      try {
        await fetch('/api/profiles/active', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ profile })
        });
        addTelemetryLine(`Switched active profile to [${profile}]`);
      } catch (e) {
        console.error(e);
      }
    }

    // Close profile dropdown when clicking outside
    document.addEventListener('click', (e) => {
      const container = document.getElementById('profile-dropdown-container');
      const menu = document.getElementById('profile-dropdown-menu');
      if (container && menu && !container.contains(e.target)) {
        menu.classList.add('hidden');
      }
    });

    function setupWs() {
      const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${location.host}/ws`;
      const ws = new WebSocket(wsUrl);
      ws.onopen = () => addTelemetryLine('WebSocket connected to Kater Gateway telemetry stream.');
      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          addTelemetryLine(`Event [${data.type}]: ${JSON.stringify(data.detail || data.name || data)}`);
        } catch {}
      };
      ws.onclose = () => setTimeout(setupWs, 3000);
    }

    window.addEventListener('DOMContentLoaded', () => {
      loadData();
      setupWs();
    });
  </script>
</body>
</html>
"""

with open('src/dashboardHtml.ts', 'w', encoding='utf-8') as f:
    f.write(f'''// Generated by scripts/generate_dashboard_ts.py
const RAW_HTML = {json.dumps(HTML_CONTENT)};

export function getDashboardHtml(port: number): string {{
  return RAW_HTML.split('__PORT__').join(String(port));
}}
''')

print("Generated src/dashboardHtml.ts successfully")
