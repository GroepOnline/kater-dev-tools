import { studioConfig } from '../config';
import type {
  AutomationsResponse, BrowserProvidersResponse, BrowserSessionsResponse,
  CapabilityAuditResponse, CatalogResponse, ContextsResponse, EventsResponse, PrListResponse,
  SessionCancelResponse, SessionEventsResponse, SessionProjection, SessionSubmitResponse,
  SettingsResponse, StatusResponse,
} from '../types';

export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${studioConfig.api.baseUrl}${path}`, init);
  const payload = await response.json().catch(() => ({})) as Record<string, unknown>;
  if (!response.ok) {
    throw new ApiError(response.status, String(payload.error ?? `${response.status} ${response.statusText}`), typeof payload.code === 'string' ? payload.code : undefined);
  }
  return payload as T;
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const katerApi = {
  status: () => request<StatusResponse>('/api/status'),
  catalog: (query = '') => request<CatalogResponse>(`/api/catalog${query ? `?q=${encodeURIComponent(query)}` : ''}`),
  profiles: () => request<{ profiles?: string[]; active?: string; default_profile?: string }>('/api/profiles'),
  pullRequests: (limit = 30) => request<PrListResponse>(`/api/pr/list?state=open&limit=${limit}`),
  browserProviders: () => request<BrowserProvidersResponse>('/api/browser/providers'),
  browserSessions: () => request<BrowserSessionsResponse>('/api/browser/sessions'),
  automations: () => request<AutomationsResponse>('/api/automations'),
  automationRun: (id: string) => request(`/api/automations/${encodeURIComponent(id)}/run`, json('POST')),
  automationSetEnabled: (id: string, enabled: boolean) => request(`/api/automations/${encodeURIComponent(id)}/${enabled ? 'enable' : 'disable'}`, json('POST')),
  automationPatch: (id: string, patch: Record<string, unknown>) => request(`/api/automations/${encodeURIComponent(id)}`, json('PATCH', patch)),
  events: (limit = 40) => request<EventsResponse>(`/api/events?limit=${limit}`),
  contexts: () => request<ContextsResponse>('/api/contexts'),
  capabilityAudit: (contextId: string, limit = 100) => request<CapabilityAuditResponse>(`/api/audit/capabilities?context_id=${encodeURIComponent(contextId)}&limit=${limit}`),
  settings: () => request<SettingsResponse>('/api/settings'),
  updateSettings: (patch: Record<string, unknown>) => request<SettingsResponse>('/api/settings', json('POST', patch)),
  session: (contextId: string, signal?: AbortSignal) => request<SessionProjection>(
    `/api/contexts/${encodeURIComponent(contextId)}/session`,
    signal ? { signal } : undefined,
  ),
  sessionContinue: (contextId: string) => request<SessionProjection>(
    `/api/contexts/${encodeURIComponent(contextId)}/session/continue`,
    json('POST'),
  ),
  sessionSubmit: (contextId: string, prompt: string) => request<SessionSubmitResponse>(
    `/api/contexts/${encodeURIComponent(contextId)}/session/work`,
    json('POST', { prompt, correlation: { katerContextId: contextId } }),
  ),
  sessionCancel: (contextId: string, workId: string, reason = 'operator') => request<SessionCancelResponse>(
    `/api/contexts/${encodeURIComponent(contextId)}/session/work/${encodeURIComponent(workId)}/cancel`,
    json('POST', { reason }),
  ),
  sessionEvents: (
    contextId: string,
    opts?: { after_seq?: number; limit?: number; wait_ms?: number; signal?: AbortSignal },
  ) => {
    const params = new URLSearchParams();
    params.set('after_seq', String(opts?.after_seq ?? 0));
    params.set('limit', String(opts?.limit ?? 100));
    if (opts?.wait_ms) params.set('wait_ms', String(opts.wait_ms));
    return request<SessionEventsResponse>(
      `/api/contexts/${encodeURIComponent(contextId)}/session/events?${params.toString()}`,
      opts?.signal ? { signal: opts.signal } : undefined,
    );
  },
};
