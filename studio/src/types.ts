export type HealthState = 'healthy' | 'degraded' | 'offline' | 'unknown';

export interface CatalogServer {
  name: string;
  description?: string;
  transport?: string;
  risk?: string;
  profiles?: string[];
  enabled?: boolean;
  configured?: boolean;
  env_configured?: boolean;
  missing_env?: string[] | boolean;
  context_cost?: number;
}

export interface CatalogResponse {
  total: number;
  servers: CatalogServer[];
  by_transport?: Record<string, number>;
  by_risk?: Record<string, number>;
}

export interface StatusResponse {
  version?: string;
  profile?: string;
  auth_mode?: string;
  servers?: { enabled?: number; disabled?: number; configured?: number; missing_env?: number };
  [key: string]: unknown;
}

export type PrGateVerdict = 'PASS' | 'WARN' | 'BLOCK' | 'FAIL' | string;

export interface PullRequestItem {
  number: number;
  title: string;
  url: string;
  head_ref: string;
  base_ref: string;
  head_sha: string;
  base_sha: string;
  draft: boolean;
  mergeable: string;
  review_decision?: string;
  open_threads: number;
  pending_checks: number;
  failed_checks: number;
  approving_reviews: number;
  independent_approvals: number;
  author_login: string;
  repo: string;
  required_failed?: number;
  required_pending?: number;
  required_missing?: number;
  required_success?: number;
  gate: {
    verdict: PrGateVerdict;
    reasons: string[];
    details?: Record<string, unknown>;
  };
}

export interface PrListResponse {
  state: string;
  count: number;
  pulls: PullRequestItem[];
}


export interface BrowserProvider {
  kind: string;
  available: boolean;
  detail?: string;
  version?: string | null;
}

export interface BrowserProvidersResponse { providers: BrowserProvider[]; }

export interface BrowserSession {
  id?: string; session_id?: string; state?: string; provider?: string; url?: string;
  created_at?: string; updated_at?: string; [key: string]: unknown;
}

export interface BrowserSessionsResponse {
  sessions: BrowserSession[];
  stats: { sessions: number; live: number; by_state: Record<string, number>; provider?: string; provider_started?: boolean; provider_info?: unknown; total_actions?: number; persisted_actions?: number; max_sessions?: number; last_error?: string | null; };
}

export interface AutomationItem {
  id: string; name: string; enabled: boolean; kind: string; schedule_seconds: number;
  config: Record<string, unknown>; last_run_at?: number | null; last_status?: string | null;
  last_error?: string | null; created_at?: number; updated_at?: number;
}

export interface AutomationsResponse { automations: AutomationItem[]; total: number; }

export interface TelemetryEvent {
  id: string | number; type?: string; name?: string; timestamp?: number | string;
  duration_ms: number; success: boolean; profile?: string; metadata?: Record<string, unknown>;
}

export interface EventsResponse { total: number; events: TelemetryEvent[]; }

export interface RemoteContext {
  context_id: string; principal_id: string; label?: string | null; profile: string;
  scopes: string[]; repository?: string | null; environment?: string | null;
  allowed_capabilities: string[]; expires_at?: number | null; revoked_at?: number | null;
  created_at: number; active: boolean; metadata?: Record<string, unknown>;
}

export interface ContextsResponse { total: number; contexts: RemoteContext[]; }

export interface CapabilityAuditEvent {
  id: number; timestamp: number; capability_id: string; principal_id?: string | null;
  context_id?: string | null; outcome: 'allowed' | 'denied' | 'error' | string;
  reason?: string | null; duration_ms?: number | null; profile?: string | null;
}

export interface CapabilityAuditResponse { total: number; events: CapabilityAuditEvent[]; }

export interface SettingsResponse {
  version: number; default_profile: string;
  auth: { mode: string; api_keys?: number; oauth_issuer?: string | null; };
  server_overrides: Record<string, { enabled?: boolean | null; env?: Record<string, string> }>;
  cors_origins: string[]; rate_limit_per_min: number; host: string; api_port: number;
  mcp_port: number; ws_port: number; storage_backend: string; db_path: string;
  body_size_limit: number; high_risk_default_disabled: boolean;
  proxy_failure_threshold: number; proxy_recovery_timeout: number;
  connector_invocation_mode: string; connector_pool_ttl_seconds: number;
}
