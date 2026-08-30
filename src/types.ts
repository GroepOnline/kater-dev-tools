export type TransportType = 'native' | 'stdio' | 'http' | 'sse' | 'plugin';
export type RiskLevel = 'low' | 'medium' | 'high';

export interface McpServerConfig {
  command?: string;
  args?: string[];
  url?: string;
  env_template?: Record<string, string>;
  headers_template?: Record<string, string>;
}

export interface OAuthConnectConfig {
  provider: string;
  authorize_url: string;
  token_url: string;
  client_id_env: string;
  client_secret_env?: string;
  scopes?: string[];
  pkce?: boolean;
  token_env?: string;
  refresh_env?: string;
  resource?: string;
}

export interface IntegrationAction {
  id: string;
  name: string;
  label: string;
  description: string;
  params: {
    name: string;
    type: string;
    required: boolean;
    description: string;
    default?: any;
  }[];
  exampleInput: Record<string, any>;
  risk: RiskLevel;
}

export interface IntegrationTrigger {
  id: string;
  name: string;
  label: string;
  description: string;
  eventType: string;
}

export interface IntegrationToolkit {
  id: string;
  name: string;
  headline: string;
  description: string;
  icon?: string;
  iconName?: string;
  badge: string;
  servers: string[];
  recommendedProfile: string;
}

export interface McpServerDoc {
  name: string;
  displayName?: string;
  itemType?: 'server' | 'plugin';
  description: string;
  transport: TransportType;
  risk: RiskLevel;
  profiles: string[];
  category?: string;
  icon?: string;
  iconSvg?: string;
  verified?: boolean;
  activeCount?: number;
  isPopular?: boolean;
  tags?: string[];
  authType?: 'oauth' | 'api_key' | 'none' | 'custom';
  env_required?: string[];
  env_configured?: boolean;
  enabled: boolean;
  context_cost: number;
  homepage?: string;
  mcp?: McpServerConfig;
  oauth?: OAuthConnectConfig;
  custom_env?: Record<string, string>;
  actions?: IntegrationAction[];
  triggers?: IntegrationTrigger[];
}

export interface TelemetryEvent {
  type: 'tool_call' | 'chain_run' | 'telemetry' | 'server_enabled' | 'server_disabled' | 'server_toggled' | 'server_credentials' | 'browser_action' | 'automation_run';
  name?: string;
  ts?: number;
  timestamp?: number;
  duration_ms?: number;
  success?: boolean;
  kind?: string;
  detail?: string;
  session_id?: string;
  error?: string;
}

export interface BrowserSession {
  session_id: string;
  label?: string;
  title?: string;
  state: 'idle' | 'active' | 'navigating' | 'closed';
  current_url: string;
  created_at: number;
  profile: string;
}

export interface AutomationItem {
  id: string;
  name: string;
  kind?: string;
  schedule?: string;
  schedule_seconds?: number;
  enabled: boolean;
  last_status?: string;
  last_error?: string;
  last_run?: number;
}

export interface CapabilityItem {
  capability_id: string;
  manifest?: {
    capability_id: string;
    risk_class: string;
    transport: string;
  };
  score?: number;
  risk_class?: string;
  transport?: string;
}

export interface ContextItem {
  context_id: string;
  label: string;
  principal_id: string;
  profile: string;
  active: boolean;
}

export interface PRItem {
  number: number;
  title: string;
  head_ref: string;
  base_ref: string;
  head_sha: string;
  gate: {
    verdict: 'PASS' | 'WARN' | 'FAIL';
    reasons: string[];
  };
}
