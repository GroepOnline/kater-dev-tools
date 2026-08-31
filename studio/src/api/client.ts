import { studioConfig } from '../config';
import type { AutomationsResponse, BrowserProvidersResponse, BrowserSessionsResponse, CatalogResponse, PrListResponse, StatusResponse } from '../types';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${studioConfig.api.baseUrl}${path}`, init);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json() as Promise<T>;
}

export const katerApi = {
  status: () => request<StatusResponse>('/api/status'),
  catalog: (query = '') => request<CatalogResponse>(`/api/catalog${query ? `?q=${encodeURIComponent(query)}` : ''}`),
  profiles: () => request<{ profiles?: string[]; active?: string; default_profile?: string }>('/api/profiles'),
  pullRequests: (limit = 30) => request<PrListResponse>(`/api/pr/list?state=open&limit=${limit}`),
  browserProviders: () => request<BrowserProvidersResponse>('/api/browser/providers'),
  browserSessions: () => request<BrowserSessionsResponse>('/api/browser/sessions'),
  automations: () => request<AutomationsResponse>('/api/automations'),
};
