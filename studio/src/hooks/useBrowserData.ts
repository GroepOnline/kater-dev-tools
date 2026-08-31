import { useCallback, useEffect, useState } from 'react';
import { katerApi } from '../api/client';
import type { BrowserProvidersResponse, BrowserSessionsResponse } from '../types';

export function useBrowserData() {
  const [providers, setProviders] = useState<BrowserProvidersResponse | null>(null);
  const [sessions, setSessions] = useState<BrowserSessionsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [nextProviders, nextSessions] = await Promise.all([
        katerApi.browserProviders(),
        katerApi.browserSessions(),
      ]);
      setProviders(nextProviders);
      setSessions(nextSessions);
      setError(null);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);
  return { providers, sessions, error, loading, refresh };
}
