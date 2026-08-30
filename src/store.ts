import {
  McpServerDoc,
  TelemetryEvent,
  BrowserSession,
  AutomationItem,
  CapabilityItem,
  ContextItem,
  PRItem,
  IntegrationToolkit
} from './types.js';
import { INITIAL_SERVERS, PROFILES_LIST } from './catalogData.js';
import { RICH_INTEGRATIONS, TOOLKITS_LIST, INTEGRATION_CATEGORIES } from './integrationsCatalog.js';
import { config } from './config.js';

function buildInitialServers(): McpServerDoc[] {
  const map = new Map<string, McpServerDoc>();
  // Start with INITIAL_SERVERS
  for (const s of INITIAL_SERVERS) {
    const defaultCategory = (s.profiles.includes('dev') || s.profiles.includes('code')) ? 'dev' :
                           (s.profiles.includes('cloud') || s.profiles.includes('data')) ? 'data' :
                           (s.profiles.includes('web') || s.profiles.includes('browser')) ? 'web' :
                           (s.profiles.includes('research') || s.profiles.includes('reasoning')) ? 'ai' :
                           (s.profiles.includes('email') || s.profiles.includes('ops')) ? 'comm' : 'dev';
    map.set(s.name, {
      ...s,
      itemType: s.itemType || 'server',
      category: defaultCategory,
      authType: s.oauth ? 'oauth' : (s.env_required && s.env_required.length > 0 ? 'api_key' : 'none'),
      actions: [
        {
          id: `${s.name}.execute`,
          name: 'execute',
          label: `Execute ${s.name} Tool`,
          description: `Execute standard tool endpoint on the ${s.name} server.`,
          params: [
            { name: 'query', type: 'string', required: false, description: 'Tool query or payload argument' }
          ],
          exampleInput: { query: 'kater gateway check' },
          risk: s.risk,
        }
      ],
      triggers: [],
    });
  }

  // Merge rich metadata overrides
  for (const rich of RICH_INTEGRATIONS) {
    const existing = map.get(rich.name);
    if (existing) {
      map.set(rich.name, {
        ...existing,
        ...rich,
        actions: rich.actions || existing.actions,
        triggers: rich.triggers || existing.triggers,
        category: rich.category || existing.category,
      });
    } else {
      map.set(rich.name, rich);
    }
  }

  return Array.from(map.values());
}

export class AppStore {
  public servers: McpServerDoc[] = buildInitialServers();
  public toolkits: IntegrationToolkit[] = JSON.parse(JSON.stringify(TOOLKITS_LIST));
  public profiles: string[] = [...PROFILES_LIST];
  public defaultProfile: string = config.KATER_PROFILE || config.KATER_DEFAULT_PROFILE || 'core';
  public authMode: string = config.KATER_AUTH_MODE || 'none';
  public corsOrigins: string[] = [config.KATER_CORS_ORIGINS || '*'];
  public rateLimit: number = 0;
  public storageBackend: string = config.KATER_STORAGE_BACKEND || 'sqlite';

  public tunnels = {
    cloudflare: { running: true, url: 'https://gateway.kater.internal' },
    tailscale: { funnel: false, ip: '100.64.0.14' },
  };

  public browserSessions: BrowserSession[] = [
    {
      session_id: 'brw_sess_9a82',
      label: 'GitHub PR #159 Review',
      title: 'GitHub PR #159',
      state: 'active',
      current_url: 'https://github.com/GroepOnline/kater-dev-tools/pull/159',
      created_at: Date.now() - 3600000,
      profile: 'ops',
    },
    {
      session_id: 'brw_sess_4f11',
      label: 'Model Context Protocol Spec Docs',
      title: 'MCP Specification v1.1.0',
      state: 'idle',
      current_url: 'https://modelcontextprotocol.io/docs/concepts/servers',
      created_at: Date.now() - 7200000,
      profile: 'dev',
    },
  ];

  public automations: AutomationItem[] = [
    {
      id: 'auto_browser_health',
      name: 'Browser session health probe',
      kind: 'system',
      schedule_seconds: 30,
      enabled: true,
      last_status: 'ok',
      last_run: Date.now() - 15000,
    },
    {
      id: 'auto_janitor',
      name: 'Expired session janitor',
      kind: 'cleanup',
      schedule: '0 */4 * * *',
      enabled: true,
      last_status: 'ok',
      last_run: Date.now() - 7200000,
    },
    {
      id: 'auto_drift_check',
      name: 'MCP catalog schema drift audit',
      kind: 'audit',
      schedule: '0 0 * * *',
      enabled: true,
      last_status: 'idle',
      last_run: Date.now() - 86400000,
    },
    {
      id: 'auto_telemetry_rollup',
      name: 'Telemetry metrics rollup & compression',
      kind: 'telemetry',
      schedule_seconds: 60,
      enabled: true,
      last_status: 'ok',
      last_run: Date.now() - 25000,
    },
  ];

  public capabilities: CapabilityItem[] = [
    {
      capability_id: 'browser.navigate',
      manifest: {
        capability_id: 'browser.navigate',
        risk_class: 'medium',
        transport: 'stdio',
      },
      score: 98,
    },
    {
      capability_id: 'browser.evaluate',
      manifest: {
        capability_id: 'browser.evaluate',
        risk_class: 'high',
        transport: 'stdio',
      },
      score: 94,
    },
    {
      capability_id: 'kater.doctor',
      manifest: {
        capability_id: 'kater.doctor',
        risk_class: 'low',
        transport: 'native',
      },
      score: 100,
    },
    {
      capability_id: 'github.pr.list',
      manifest: {
        capability_id: 'github.pr.list',
        risk_class: 'medium',
        transport: 'stdio',
      },
      score: 96,
    },
    {
      capability_id: 'computer.execute',
      manifest: {
        capability_id: 'computer.execute',
        risk_class: 'high',
        transport: 'native',
      },
      score: 92,
    },
    {
      capability_id: 'automation.run_now',
      manifest: {
        capability_id: 'automation.run_now',
        risk_class: 'low',
        transport: 'native',
      },
      score: 99,
    },
  ];

  public contexts: ContextItem[] = [
    {
      context_id: 'ctx_agent_worker_1',
      label: 'AI Studio Workspace Subagent #1',
      principal_id: 'antigravity-agent',
      profile: 'core',
      active: true,
    },
    {
      context_id: 'ctx_cloud_run_ingress',
      label: 'Cloud Run Ingress Gateway',
      principal_id: 'kater-ingress',
      profile: 'ops',
      active: true,
    },
  ];

  public computerStatus = {
    configured: true,
    active: true,
    capability_count: 8,
    profile: 'core',
    base_url_host: '127.0.0.1:3000',
  };

  public prList: PRItem[] = [
    {
      number: 159,
      title: 'feat(control-room): unified MCP gateway status & telemetry dashboard',
      head_ref: 'feat/control-room-v2',
      base_ref: 'main',
      head_sha: 'a8f7c9e1204',
      gate: {
        verdict: 'PASS',
        reasons: ['Ruff check passed (0 warnings)', 'Mypy clean (31 source files)', '551 tests passing'],
      },
    },
    {
      number: 158,
      title: 'fix(browser): eliminate popup block on OAuth handshake',
      head_ref: 'fix/oauth-popup',
      base_ref: 'main',
      head_sha: '3c8e4d10129',
      gate: {
        verdict: 'PASS',
        reasons: ['Unit tests passed (12/12)'],
      },
    },
  ];

  public telemetryEvents: TelemetryEvent[] = [
    {
      type: 'tool_call',
      name: 'kater.doctor',
      duration_ms: 18,
      success: true,
      ts: (Date.now() - 4000) / 1000,
    },
    {
      type: 'tool_call',
      name: 'github.search_code',
      duration_ms: 84,
      success: true,
      ts: (Date.now() - 3000) / 1000,
    },
    {
      type: 'tool_call',
      name: 'linear.list_issues',
      duration_ms: 112,
      success: true,
      ts: (Date.now() - 2000) / 1000,
    },
    {
      type: 'tool_call',
      name: 'browser.navigate',
      duration_ms: 195,
      success: true,
      ts: (Date.now() - 1000) / 1000,
    },
  ];

  public totalToolCalls: number = 428;
  public successfulToolCalls: number = 422;

  public getServer(name: string): McpServerDoc | undefined {
    return this.servers.find(s => s.name.toLowerCase() === name.toLowerCase());
  }

  public enableServer(name: string): boolean {
    const s = this.getServer(name);
    if (s) {
      s.enabled = true;
      return true;
    }
    return false;
  }

  public disableServer(name: string): boolean {
    const s = this.getServer(name);
    if (s) {
      s.enabled = false;
      return true;
    }
    return false;
  }

  public toggleServer(name: string): boolean {
    const s = this.getServer(name);
    if (s) {
      s.enabled = !s.enabled;
      return s.enabled;
    }
    return false;
  }

  public setCredentials(name: string, env: Record<string, string>): boolean {
    const s = this.getServer(name);
    if (!s) return false;
    s.custom_env = { ...(s.custom_env || {}), ...env };
    s.env_configured = true;
    return true;
  }

  public enableToolkit(toolkitId: string): { enabled: string[]; count: number } {
    const tk = this.toolkits.find(t => t.id === toolkitId);
    if (!tk) return { enabled: [], count: 0 };
    const changed: string[] = [];
    for (const sname of tk.servers) {
      const server = this.getServer(sname);
      if (server) {
        server.enabled = true;
        changed.push(sname);
      }
    }
    return { enabled: changed, count: changed.length };
  }

  public disableToolkit(toolkitId: string): { disabled: string[]; count: number } {
    const tk = this.toolkits.find(t => t.id === toolkitId);
    if (!tk) return { disabled: [], count: 0 };
    const changed: string[] = [];
    for (const sname of tk.servers) {
      const server = this.getServer(sname);
      if (server && sname !== 'kater') {
        server.enabled = false;
        changed.push(sname);
      }
    }
    return { disabled: changed, count: changed.length };
  }

  public executeAction(serverName: string, actionId: string, params: Record<string, any>): {
    success: boolean;
    duration_ms: number;
    result: any;
    error?: string;
  } {
    const server = this.getServer(serverName);
    const start = Date.now();
    this.totalToolCalls++;

    // Generate realistic Composio / MCP execution output
    let result: any = {};
    const act = server?.actions?.find(a => a.id === actionId || a.name === actionId);

    if (serverName === 'github') {
      if (actionId.includes('list_pull_requests') || actionId.includes('pull_requests')) {
        result = {
          pull_requests: [
            { number: 159, title: 'feat: add Composio-grade integration hub and toolkits', state: 'open', user: 'antigravity-agent', draft: false, labels: ['enhancement', 'mcp-gateway'] },
            { number: 158, title: 'refactor: streamline REST gateway routing and websocket sse', state: 'merged', user: 'kater-core', draft: false, labels: ['internal'] },
          ],
          total_count: 2,
          repository: `${params.owner || 'GroepOnline'}/${params.repo || 'kater-dev-tools'}`
        };
      } else if (actionId.includes('search_code')) {
        result = {
          total_count: 14,
          items: [
            { path: 'src/integrationsCatalog.ts', line: 42, match: 'export const RICH_INTEGRATIONS' },
            { path: 'src/store.ts', line: 88, match: 'public toolkits: IntegrationToolkit[]' },
          ]
        };
      } else {
        result = { status: 'success', message: `Executed ${actionId} on GitHub successfully`, commit_sha: 'a7b93f8e12d45c67' };
      }
    } else if (serverName === 'linear') {
      result = {
        success: true,
        issue: {
          id: 'KAT-204',
          identifier: 'KAT-204',
          title: params.title || 'Configure MCP Gateway Adapter',
          state: 'in_progress',
          priority: params.priority || 2,
          url: 'https://linear.app/groep/issue/KAT-204'
        }
      };
    } else if (serverName === 'browser') {
      result = {
        success: true,
        url: params.url || 'https://modelcontextprotocol.io',
        title: 'Model Context Protocol Documentation',
        status: 200,
        dom_elements_count: 342,
        snapshot_preview: '# Model Context Protocol\n\nOpen standard for agent integrations...'
      };
    } else if (serverName === 'slack') {
      result = {
        ok: true,
        channel: params.channel || 'C01234567',
        ts: (Date.now() / 1000).toFixed(6),
        message: { text: params.text || 'Notification from Kater' }
      };
    } else if (serverName === 'postgres') {
      result = {
        command: 'SELECT',
        rowCount: 4,
        rows: [
          { id: 1, table_name: 'mcp_servers', schema: 'public', rows_count: 48 },
          { id: 2, table_name: 'telemetry_events', schema: 'public', rows_count: 1420 },
          { id: 3, table_name: 'browser_sessions', schema: 'public', rows_count: 6 },
          { id: 4, table_name: 'auth_tokens', schema: 'public', rows_count: 12 },
        ]
      };
    } else if (serverName === 'exa') {
      result = {
        results: [
          { title: 'Model Context Protocol (MCP) Official Spec', url: 'https://modelcontextprotocol.io', score: 0.98 },
          { title: 'Kater Dev Tools — High Speed MCP Gateway', url: 'https://github.com/GroepOnline/kater-dev-tools', score: 0.94 },
        ],
        autoprompt_used: true
      };
    } else {
      result = {
        success: true,
        server: serverName,
        action: actionId,
        params,
        timestamp: new Date().toISOString(),
        gateway_status: '200 OK',
        detail: 'Action dispatched through Kater MCP Gateway runtime.',
      };
    }

    const duration_ms = Math.floor(Math.random() * 45) + 30;
    this.successfulToolCalls++;

    const te: TelemetryEvent = {
      type: 'tool_call',
      name: `${serverName}.${act?.name || actionId}`,
      duration_ms,
      success: true,
      ts: Date.now() / 1000,
      detail: JSON.stringify(params),
    };
    this.telemetryEvents.unshift(te);
    if (this.telemetryEvents.length > 50) this.telemetryEvents.pop();

    return {
      success: true,
      duration_ms,
      result,
    };
  }

  public getStats() {
    const enabled = this.servers.filter(s => s.enabled).length;
    const total = this.servers.length;
    const successRate = this.totalToolCalls > 0
      ? Math.round((this.successfulToolCalls / this.totalToolCalls) * 1000) / 10
      : 98.4;
    return {
      version: '1.1.0',
      auth_mode: this.authMode,
      servers: {
        total,
        enabled,
      },
      telemetry: {
        success_rate: successRate,
        tool_calls: this.totalToolCalls,
        total_events: this.totalToolCalls + 120,
        avg_latency_ms: 94,
      },
      browser: {
        sessions_active: this.browserSessions.filter(b => b.state !== 'closed').length,
      },
    };
  }
}

export const store = new AppStore();
