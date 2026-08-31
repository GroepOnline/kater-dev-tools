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

