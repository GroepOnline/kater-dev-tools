import http from 'http';
import { randomBytes } from 'node:crypto';
import express from 'express';
import cors from 'cors';
import { WebSocketServer, WebSocket } from 'ws';
import { getDashboardHtml } from './src/dashboardHtml.js';
import { store } from './src/store.js';
import { config } from './config.js';
import type { BrowserSession, TelemetryEvent } from './src/types.js';

const app = express();
const PORT = config.PORT;

app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Create HTTP Server
const server = http.createServer(app);

// Create WebSocket Server on the same HTTP server
const wss = new WebSocketServer({ server, path: '/ws' });

const clients = new Set<WebSocket>();

wss.on('connection', (ws) => {
  clients.add(ws);

  ws.on('message', (message) => {
    try {
      const data = JSON.parse(message.toString());
      if (data.cmd === 'subscribe_all' || data.cmd === 'subscribe') {
        ws.send(JSON.stringify({ type: 'subscribed', status: 'ok' }));
      } else if (data.cmd === 'ping') {
        ws.send(JSON.stringify({ type: 'pong', ts: Date.now() }));
      }
    } catch {
      // ignore
    }
  });

  ws.on('close', () => {
    clients.delete(ws);
  });

  ws.on('error', () => {
    clients.delete(ws);
  });
});

function broadcast(payload: object) {
  const msg = JSON.stringify(payload);
  for (const client of clients) {
    if (client.readyState === WebSocket.OPEN) {
      client.send(msg);
    }
  }
}

// Background live telemetry generator
const toolNames = [
  'kater.doctor',
  'github.search_code',
  'github.list_pull_requests',
  'linear.list_issues',
  'sentry.get_event',
  'browser.navigate',
  'browser.evaluate',
  'sequential_thinking.step',
  'memory.query',
  'context7.resolve_docs',
  'deepwiki.query',
  'filesystem.read_file',
  'fetch.url_to_markdown',
  'time.get_current_time',
];

setInterval(() => {
  if (clients.size > 0) {
    const randomTool = toolNames[Math.floor(Math.random() * toolNames.length)];
    const duration = Math.floor(Math.random() * 180) + 15;
    const ok = Math.random() > 0.04;
    const now = Date.now() / 1000;

    store.totalToolCalls++;
    if (ok) store.successfulToolCalls++;

    const event: TelemetryEvent = {
      type: 'tool_call',
      name: randomTool,
      duration_ms: duration,
      success: ok,
      ts: now,
      timestamp: now,
    };

    store.telemetryEvents.unshift(event);
    if (store.telemetryEvents.length > 200) store.telemetryEvents.pop();

    broadcast(event);
  }
}, 3000);

// ── Health Endpoints ──────────────────────────────────────────
app.get('/health', (req, res) => {
  res.json({ status: 'ok', version: '1.1.0', auth_mode: store.authMode });
});

app.get('/health/live', (req, res) => {
  res.json({ status: 'ok', version: '1.1.0', auth_mode: store.authMode });
});

app.get('/health/ready', (req, res) => {
  res.json({
    status: 'ok',
    service: 'kater',
    version: '1.1.0',
    auth_mode: store.authMode,
    components: {
      api: { status: 'ok' },
      settings: { status: 'ok' },
      mcp: { status: 'ok' },
      telemetry: { status: 'ok' },
    },
  });
});

// ── Status & Metrics ──────────────────────────────────────────
app.get('/api/status', (req, res) => {
  res.json(store.getStats());
});

app.get('/api/backends', (req, res) => {
  const list = store.servers.map(s => ({
    name: s.name,
    healthy: s.enabled,
    running: s.enabled,
    tool_count: s.context_cost * 3 + 2,
    latency_ms: Math.floor(Math.random() * 45) + 12,
    breaker_state: 'closed',
    enabled: s.enabled,
    configured: s.env_configured ?? true,
    missing_env: (s.env_required || []).filter(v => !s.env_configured),
  }));

  res.json({
    backends: list,
    servers: list,
    totals: {
      total: list.length,
      enabled: list.filter(b => b.enabled).length,
      healthy: list.filter(b => b.healthy).length,
    },
  });
});

app.get('/api/events', (req, res) => {
  const limit = Math.min(parseInt(req.query.limit as string || '50', 10), 200);
  const events = store.telemetryEvents.slice(0, limit).map((e, idx) => ({
    id: `evt_${idx}_${Math.floor((e.ts || Date.now()) * 1000)}`,
    type: e.type,
    name: e.name || 'kater.tool',
    timestamp: e.ts || Date.now() / 1000,
    duration_ms: e.duration_ms || 32,
    success: e.success ?? true,
    profile: store.defaultProfile,
    metadata: { source: 'gateway' },
  }));
  res.json({ total: events.length, events });
});

app.get('/api/profiles', (req, res) => {
  res.json({ profiles: store.profiles, default_profile: store.defaultProfile });
});

// ── Catalog & MCP Servers ──────────────────────────────────────
app.get(['/api/catalog', '/api/mcp/servers'], (req, res) => {
  const profile = (req.query.profile as string) || '';
  const query = (req.query.q as string || '').toLowerCase();

  let list = store.servers;
  if (profile && profile !== 'all') {
    list = list.filter(s => s.profiles.includes(profile) || s.name === 'kater');
  }
  if (query) {
    list = list.filter(s =>
      s.name.toLowerCase().includes(query) ||
      s.description.toLowerCase().includes(query)
    );
  }

  res.json({ total: list.length, servers: list });
});

app.post('/api/mcp/servers', (req, res) => {
  const { name, description, transport, risk, profiles, env_required, command, args, url, homepage } = req.body;
  if (!name || typeof name !== 'string' || !name.trim()) {
    return res.status(400).json({ error: 'Server name is required' });
  }

  const cleanName = name.trim().toLowerCase().replace(/[^a-z0-9_-]/g, '-');
  const existing = store.getServer(cleanName);
  if (existing) {
    return res.status(409).json({ error: `Server "${cleanName}" already exists` });
  }

  const parsedProfiles = Array.isArray(profiles)
    ? profiles
    : typeof profiles === 'string'
      ? profiles.split(',').map(p => p.trim()).filter(Boolean)
      : ['dev', 'core', 'full'];

  const parsedEnv = Array.isArray(env_required)
    ? env_required
    : typeof env_required === 'string'
      ? env_required.split(',').map(e => e.trim()).filter(Boolean)
      : [];

  const newServer = {
    name: cleanName,
    description: description || `Custom ${cleanName} integration`,
    transport: transport || 'stdio',
    risk: risk || 'medium',
    profiles: parsedProfiles.length > 0 ? parsedProfiles : ['core', 'dev', 'full'],
    enabled: true,
    env_required: parsedEnv,
    env_configured: parsedEnv.length === 0,
    context_cost: 3,
    homepage: homepage || '',
    mcp: command ? { command, args: Array.isArray(args) ? args : [] } : (url ? { url } : undefined),
  };

  store.servers.push(newServer);
  broadcast({ type: 'server_added', name: cleanName, server: newServer });
  res.status(201).json({ status: 'created', server: newServer });
});

app.get('/api/mcp/servers/:name', (req, res) => {
  const s = store.getServer(req.params.name);
  if (!s) {
    return res.status(404).json({ error: 'Server not found' });
  }
  res.json(s);
});

app.post('/api/mcp/servers/:name/enable', (req, res) => {
  const name = req.params.name;
  const ok = store.enableServer(name);
  if (!ok) return res.status(404).json({ error: 'Server not found' });
  broadcast({ type: 'server_enabled', name });
  res.json({ status: 'enabled', name });
});

app.post('/api/mcp/servers/:name/disable', (req, res) => {
  const name = req.params.name;
  const ok = store.disableServer(name);
  if (!ok) return res.status(404).json({ error: 'Server not found' });
  broadcast({ type: 'server_disabled', name });
  res.json({ status: 'disabled', name });
});

app.post('/api/mcp/servers/:name/toggle', (req, res) => {
  const name = req.params.name;
  const s = store.getServer(name);
  if (!s) return res.status(404).json({ error: 'Server not found' });
  const newState = store.toggleServer(name);
  broadcast({ type: 'server_toggled', name, enabled: newState });
  res.json({ status: newState ? 'enabled' : 'disabled', name, enabled: newState });
});

app.post('/api/mcp/servers/:name/credentials', (req, res) => {
  const name = req.params.name;
  const env = req.body.env || {};
  const ok = store.setCredentials(name, env);
  if (!ok) return res.status(404).json({ error: 'Server not found' });
  const s = store.getServer(name);
  broadcast({ type: 'server_credentials', name });
  res.json({ status: 'saved', name, env_configured: s?.env_configured });
});

app.post('/api/mcp/servers/:name/oauth/start', (req, res) => {
  const s = store.getServer(req.params.name);
  if (!s || !s.oauth) {
    return res.status(400).json({ error: 'OAuth not supported for this server' });
  }
  res.json({
    authorize_url: s.oauth.authorize_url + '?client_id=demo&redirect_uri=http://localhost:3000/oauth/callback',
  });
});

// ── Composio-Style Integrations & Toolkits API ────────────────
app.get('/api/integrations', (req, res) => {
  const category = (req.query.category as string) || 'all';
  const query = ((req.query.q as string) || '').toLowerCase();
  const authFilter = (req.query.auth as string) || 'all';

  let list = store.servers;
  if (category !== 'all') {
    list = list.filter(s => s.category === category);
  }
  if (authFilter !== 'all') {
    list = list.filter(s => s.authType === authFilter);
  }
  if (query) {
    list = list.filter(s =>
      s.name.toLowerCase().includes(query) ||
      s.description.toLowerCase().includes(query) ||
      s.actions?.some(a => a.name.toLowerCase().includes(query) || a.description.toLowerCase().includes(query))
    );
  }

  const totalActions = store.servers.reduce((acc, s) => acc + (s.actions?.length || 1), 0);
  const totalTriggers = store.servers.reduce((acc, s) => acc + (s.triggers?.length || 0), 0);
  const connectedCount = store.servers.filter(s => s.enabled && (s.env_configured ?? true)).length;

  res.json({
    total: list.length,
    stats: {
      total_integrations: store.servers.length,
      connected_integrations: connectedCount,
      total_actions: totalActions,
      total_triggers: totalTriggers,
      active_toolkits: store.toolkits.length,
    },
    integrations: list,
  });
});

app.get('/api/integrations/toolkits', (req, res) => {
  const toolkits = store.toolkits.map(tk => {
    const servers = tk.servers.map(sname => store.getServer(sname)).filter(Boolean);
    const enabledServers = servers.filter(s => s?.enabled);
    return {
      ...tk,
      total_servers: servers.length,
      enabled_servers: enabledServers.length,
      all_enabled: servers.length > 0 && enabledServers.length === servers.length,
      servers_detail: servers,
    };
  });
  res.json({ toolkits });
});

app.post('/api/integrations/toolkits/:id/enable', (req, res) => {
  const { id } = req.params;
  const result = store.enableToolkit(id);
  broadcast({ type: 'telemetry', kind: 'toolkit_enabled', detail: `Enabled toolkit ${id}` });
  res.json({ status: 'enabled', toolkit: id, ...result });
});

app.post('/api/integrations/toolkits/:id/disable', (req, res) => {
  const { id } = req.params;
  const result = store.disableToolkit(id);
  broadcast({ type: 'telemetry', kind: 'toolkit_disabled', detail: `Disabled toolkit ${id}` });
  res.json({ status: 'disabled', toolkit: id, ...result });
});

app.post('/api/integrations/execute', (req, res) => {
  const { server, action, params = {} } = req.body;
  if (!server || !action) {
    return res.status(400).json({ error: 'Both server and action are required' });
  }

  const s = store.getServer(server);
  if (!s) {
    return res.status(404).json({ error: `Server "${server}" not found in catalog` });
  }

  const out = store.executeAction(server, action, params);
  broadcast({
    type: 'tool_call',
    name: `${server}.${action}`,
    duration_ms: out.duration_ms,
    success: out.success,
    ts: Date.now() / 1000,
  });

  res.json(out);
});

app.post('/api/integrations/:name/connect', (req, res) => {
  const { name } = req.params;
  const { credentials = {}, authType } = req.body;
  const s = store.getServer(name);
  if (!s) return res.status(404).json({ error: 'Server not found' });

  s.custom_env = { ...(s.custom_env || {}), ...credentials };
  s.env_configured = true;
  s.enabled = true;

  broadcast({ type: 'server_credentials', name });
  res.json({
    status: 'connected',
    server: name,
    enabled: true,
    env_configured: true,
    message: `Successfully authenticated ${name} integration into Kater Gateway`,
  });
});

// ── Telemetry & Evals ──────────────────────────────────────────
app.get('/api/telemetry', (req, res) => {
  res.json({ events: store.telemetryEvents });
});

app.get('/api/evals', (req, res) => {
  const perTool: Record<string, { total: number; success: number; success_rate: number; avg_duration_ms: number }> = {};
  for (const name of toolNames) {
    const total = Math.floor(Math.random() * 45) + 5;
    const errors = Math.floor(Math.random() * 2);
    const success = total - errors;
    const rate = Math.round((success / total) * 100);
    const avg = Math.floor(Math.random() * 120) + 20;
    perTool[name] = { total, success, success_rate: rate, avg_duration_ms: avg };
  }

  res.json({
    summary: {
      overall_success_rate: 98.4,
      total_errors: 6,
      average_latency_ms: 94,
    },
    tool_calls: {
      total: store.totalToolCalls,
      unique_tools: toolNames.length,
      per_tool: perTool,
    },
  });
});

// ── Tunnels ───────────────────────────────────────────────────
app.get(['/api/tunnel', '/api/tunnels'], (req, res) => {
  res.json(store.tunnels);
});

app.post('/api/tunnel/:provider/:action', (req, res) => {
  const { provider, action } = req.params;
  if (provider === 'cloudflare') {
    store.tunnels.cloudflare.running = action === 'start';
    res.json({ provider, running: store.tunnels.cloudflare.running, url: store.tunnels.cloudflare.url });
  } else if (provider === 'tailscale') {
    store.tunnels.tailscale.funnel = action === 'start';
    res.json({ provider, running: store.tunnels.tailscale.funnel, ip: store.tunnels.tailscale.ip });
  } else {
    res.status(400).json({ error: 'Unknown tunnel provider' });
  }
});

// ── Browser Workspace ─────────────────────────────────────────
app.get('/api/browser/providers', (req, res) => {
  res.json({
    providers: [
      { kind: 'playwright-local', available: true, headless: true },
      { kind: 'cdp-remote', available: true, endpoint: 'ws://127.0.0.1:9222' },
    ],
  });
});

app.get('/api/browser/sessions', (req, res) => {
  res.json({ sessions: store.browserSessions });
});

app.post('/api/browser/sessions', (req, res) => {
  const profile = req.body.profile || 'core';
  const newSession: BrowserSession = {
    session_id: `brw_sess_${randomBytes(4).toString('hex')}`,
    label: `Browser Session (${profile})`,
    title: 'New Tab',
    state: 'active',
    current_url: 'https://github.com/GroepOnline/kater-dev-tools',
    created_at: Date.now(),
    profile,
  };
  store.browserSessions.unshift(newSession);
  broadcast({ type: 'browser_session', session_id: newSession.session_id, action: 'created' });
  res.json({ session: newSession });
});

app.delete('/api/browser/sessions/:id', (req, res) => {
  const id = req.params.id;
  const idx = store.browserSessions.findIndex(s => s.session_id === id);
  if (idx >= 0) {
    store.browserSessions.splice(idx, 1);
    broadcast({ type: 'browser_session', session_id: id, action: 'closed' });
    res.json({ status: 'deleted', session_id: id });
  } else {
    res.status(404).json({ error: 'Session not found' });
  }
});

// Helper for generating dynamic mock screenshots
function generateMockScreenshotB64(url: string) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540">
    <rect width="960" height="540" fill="#0d1117"/>
    <rect x="0" y="0" width="960" height="42" fill="#161b22"/>
    <circle cx="24" cy="21" r="5" fill="#ff5f56"/>
    <circle cx="40" cy="21" r="5" fill="#ffbd2e"/>
    <circle cx="56" cy="21" r="5" fill="#27c93f"/>
    <rect x="80" y="10" width="600" height="22" rx="4" fill="#0d1117" stroke="#30363d"/>
    <text x="96" y="25" fill="#58a6ff" font-family="-apple-system,BlinkMacSystemFont,monospace" font-size="12">${url}</text>
    
    <rect x="40" y="70" width="880" height="120" rx="8" fill="#161b22" stroke="#30363d"/>
    <text x="64" y="110" fill="#f0f6fc" font-family="-apple-system,BlinkMacSystemFont,sans-serif" font-size="20" font-weight="600">Kater Dev Tools — MCP Browser Workspace</text>
    <text x="64" y="145" fill="#8b949e" font-family="-apple-system,BlinkMacSystemFont,sans-serif" font-size="14">Navigated to: ${url}</text>
    <rect x="64" y="160" width="120" height="24" rx="12" fill="#238636"/>
    <text x="124" y="176" fill="#ffffff" font-family="-apple-system,sans-serif" font-size="12" font-weight="600" text-anchor="middle">HTTP 200 OK</text>

    <rect x="40" y="210" width="420" height="290" rx="8" fill="#161b22" stroke="#30363d"/>
    <text x="64" y="245" fill="#58a6ff" font-family="monospace" font-size="14">DOM State &amp; Elements</text>
    <rect x="64" y="265" width="370" height="18" rx="3" fill="#21262d"/>
    <rect x="64" y="295" width="320" height="18" rx="3" fill="#21262d"/>
    <rect x="64" y="325" width="350" height="18" rx="3" fill="#21262d"/>
    <rect x="64" y="355" width="280" height="18" rx="3" fill="#21262d"/>

    <rect x="500" y="210" width="420" height="290" rx="8" fill="#161b22" stroke="#30363d"/>
    <text x="524" y="245" fill="#2dd4bf" font-family="monospace" font-size="14">MCP Tool Execution Stream</text>
    <text x="524" y="280" fill="#8b949e" font-family="monospace" font-size="12">&gt; Playwright session active</text>
    <text x="524" y="305" fill="#8b949e" font-family="monospace" font-size="12">&gt; Click handler attached</text>
    <text x="524" y="330" fill="#8b949e" font-family="monospace" font-size="12">&gt; Snapshot rendered: ${new Date().toLocaleTimeString()}</text>
  </svg>`;
  return Buffer.from(svg).toString('base64');
}

app.post('/api/browser/sessions/:id/act', (req, res) => {
  const { id } = req.params;
  const { kind, url } = req.body;
  const session = store.browserSessions.find(s => s.session_id === id);

  if (!session) return res.status(404).json({ error: 'Session not found' });

  if (kind === 'navigate' && url) {
    session.current_url = url;
    session.title = url;
  }

  const b64 = generateMockScreenshotB64(session.current_url);

  broadcast({
    type: 'browser_action',
    session_id: id,
    kind: kind || 'navigate',
    url: session.current_url,
    ok: true,
    timestamp: Date.now() / 1000,
  });

  res.json({
    ok: true,
    url: session.current_url,
    screenshot_b64: b64,
  });
});

app.post('/api/browser/sessions/:id/screenshot', (req, res) => {
  const session = store.browserSessions.find(s => s.session_id === req.params.id);
  if (!session) return res.status(404).json({ error: 'Session not found' });

  const b64 = generateMockScreenshotB64(session.current_url);
  res.json({
    url: session.current_url,
    screenshot_b64: b64,
  });
});

// ── Automations ───────────────────────────────────────────────
app.get('/api/automations', (req, res) => {
  res.json({ automations: store.automations });
});

app.post('/api/automations/:id/enable', (req, res) => {
  const item = store.automations.find(a => a.id === req.params.id);
  if (!item) return res.status(404).json({ error: 'Automation not found' });
  item.enabled = true;
  broadcast({ type: 'automation_enabled', id: item.id });
  res.json({ status: 'enabled', id: item.id });
});

app.post('/api/automations/:id/disable', (req, res) => {
  const item = store.automations.find(a => a.id === req.params.id);
  if (!item) return res.status(404).json({ error: 'Automation not found' });
  item.enabled = false;
  broadcast({ type: 'automation_disabled', id: item.id });
  res.json({ status: 'disabled', id: item.id });
});

app.post('/api/automations/:id/run', (req, res) => {
  const item = store.automations.find(a => a.id === req.params.id);
  if (!item) return res.status(404).json({ error: 'Automation not found' });
  item.last_run = Date.now();
  item.last_status = 'ok';
  broadcast({ type: 'automation_run', id: item.id, status: 'ok' });
  res.json({ status: 'queued', id: item.id });
});

// ── Fabric (Capabilities, Contexts, Computer) ─────────────────
app.get('/api/capabilities', (req, res) => {
  res.json({ capabilities: store.capabilities });
});

app.get('/api/contexts', (req, res) => {
  res.json({ contexts: store.contexts });
});

app.get('/api/computer', (req, res) => {
  res.json(store.computerStatus);
});

// ── PR Control ────────────────────────────────────────────────
app.get('/api/pr/list', (req, res) => {
  res.json({ pulls: store.prList, count: store.prList.length });
});

app.post('/api/pr/:number/merge', (req, res) => {
  const num = parseInt(req.params.number, 10);
  const idx = store.prList.findIndex(p => p.number === num);
  if (idx >= 0) {
    store.prList.splice(idx, 1);
    res.json({ status: 'merged', number: num });
  } else {
    res.status(404).json({ error: 'PR not found or already merged' });
  }
});

// ── Deploy Formats ────────────────────────────────────────────
const DEPLOY_TEMPLATES: Record<string, { description: string; content: Record<string, unknown> }> = {
  docker: {
    description: 'Standalone Docker Compose deployment with background daemon and SQLite volume mount.',
    content: {
      version: '3.8',
      services: {
        kater: {
          image: 'ghcr.io/groeponline/kater-dev-tools:latest',
          restart: 'unless-stopped',
          ports: ['3000:3000'],
          environment: {
            PORT: '3000',
            KATER_PROFILE: 'core',
            KATER_AUTH_MODE: 'none',
          },
          volumes: ['kater_data:/app/.kater'],
        },
      },
      volumes: { kater_data: {} },
    },
  },
  systemd: {
    description: 'Systemd service unit for native Linux host supervisor.',
    content: {
      Unit: {
        Description: 'Kater MCP Gateway Service',
        After: 'network.target',
      },
      Service: {
        Type: 'simple',
        ExecStart: '/usr/local/bin/node /opt/kater/dist/server.js',
        Restart: 'always',
        Environment: 'PORT=3000',
      },
      Install: { WantedBy: 'multi-user.target' },
    },
  },
  cloudflare: {
    description: 'Cloudflare Tunnel configuration routing public HTTPS traffic to port 3000.',
    content: {
      tunnel: 'kater-gateway-tunnel',
      ingress: [
        { hostname: 'gateway.kater.internal', service: 'http://localhost:3000' },
        { service: 'http_status:404' },
      ],
    },
  },
  kubernetes: {
    description: 'Kubernetes Deployment and ClusterIP Service definition.',
    content: {
      apiVersion: 'apps/v1',
      kind: 'Deployment',
      metadata: { name: 'kater-gateway' },
      spec: {
        replicas: 1,
        template: {
          spec: {
            containers: [
              {
                name: 'kater',
                image: 'ghcr.io/groeponline/kater-dev-tools:latest',
                ports: [{ containerPort: 3000 }],
              },
            ],
          },
        },
      },
    },
  },
};

app.get('/api/deploy', (req, res) => {
  const formats = Object.keys(DEPLOY_TEMPLATES).map(name => ({
    name,
    description: DEPLOY_TEMPLATES[name].description,
  }));
  res.json({ formats });
});

app.get('/api/deploy/:format', (req, res) => {
  const fmt = req.params.format;
  const template = DEPLOY_TEMPLATES[fmt];
  if (!template) return res.status(404).json({ error: 'Deploy format not found' });
  res.json({
    format: fmt,
    description: template.description,
    ...template.content,
  });
});

// ── Settings ──────────────────────────────────────────────────
app.get('/api/settings', (req, res) => {
  res.json({
    auth: { mode: store.authMode },
    cors_origins: store.corsOrigins,
    rate_limit_per_min: store.rateLimit,
    default_profile: store.defaultProfile,
    storage_backend: store.storageBackend,
  });
});

app.post('/api/settings', (req, res) => {
  const { auth, cors_origins, rate_limit_per_min, default_profile, storage_backend } = req.body;
  if (auth && auth.mode) store.authMode = auth.mode;
  if (Array.isArray(cors_origins)) store.corsOrigins = cors_origins;
  if (typeof rate_limit_per_min === 'number') store.rateLimit = rate_limit_per_min;
  if (default_profile) store.defaultProfile = default_profile;
  if (storage_backend) store.storageBackend = storage_backend;
  res.json({ status: 'ok', settings: store });
});

// ── Commands & Tickets ────────────────────────────────────────
app.post('/api/command', (req, res) => {
  const { cmd } = req.body;
  res.json({ status: 'ok', command: cmd, output: `Executed ${cmd}` });
});

app.post('/api/ws-ticket', (req, res) => {
  res.json({ ticket: `tk_${Math.random().toString(36).substring(2, 12)}` });
});

// ── Extended Integrations (Reviews, Cursor, Compound Engineering) ────────
app.get('/api/reviews', (req, res) => {
  res.json({
    sessions: [
      {
        id: 'rev_2026_08_30_gateway',
        date: '2026-08-30',
        title: 'MCP Gateway Control Room & Browser Workspace Hardening',
        verdict: 'PASS',
        lessons: [
          'Workflow YAML guarded by plain-text regression tests',
          'Single port 3000 mapping with unified HTTP + WebSocket server',
          'Playwright browser workspace stream hydration verified',
        ],
      },
    ],
    continual_learning: [
      {
        topic: 'Workflow YAML tests',
        rule: 'Always verify plain-text substring matches in CI workflows before committing changes.',
      },
      {
        topic: 'Runner model',
        rule: 'Public jobs standard on ubuntu-latest; dedicated runners restricted to private fleet.',
      },
    ],
  });
});

app.get('/api/compound-engineering', (req, res) => {
  res.json({
    overlay: {
      active: true,
      config: 'config.yaml',
      artifacts_root: '.compound-engineering/artifacts/',
      lanes: ['lane-gateway', 'lane-browser', 'lane-pr-gate', 'lane-telemetry'],
    },
    taste_scorecard: {
      overall: 99.2,
      metrics: {
        typography: 100,
        contrast: 100,
        anti_slop_compliance: 100,
        zero_runtime_patches: 100,
      },
    },
  });
});

app.get('/api/cursor/skills', (req, res) => {
  res.json({
    skills: [
      { name: 'local-verify', path: '.cursor/skills/local-verify/', role: 'Verify matrix' },
      { name: 'kater-gateway', path: '.cursor/skills/kater-gateway/', role: 'Serve, health, smoke ladder' },
      { name: 'kater-doctor', path: '.cursor/skills/kater-doctor/', role: 'Diagnostics & fix-plan' },
      { name: 'kater-e2e', path: '.cursor/skills/kater-e2e/', role: 'E2E MCP client test' },
      { name: 'kater-dashboard', path: '.cursor/skills/kater-dashboard/', role: 'REST + dashboard control room' },
      { name: 'pr-gate', path: '.cursor/skills/pr-gate/', role: 'Merge-ready PR checks' },
      { name: 'parallel-lanes', path: '.cursor/skills/parallel-lanes/', role: 'Disjoint parallel lanes' },
    ],
  });
});

// ── Web Dashboard Rendering ────────────────────────────────────
app.get(['/', '/dashboard', '/index.html'], (req, res) => {
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.send(getDashboardHtml(PORT));
});

// Start listening
server.listen(PORT, '0.0.0.0', () => {
  console.log(`Kater Dev Tools server running on http://0.0.0.0:${PORT}`);
});
