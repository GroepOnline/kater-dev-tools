import { useCallback, useEffect, useState } from 'react';
import { katerApi } from '../api/client';
import type { ContextsResponse } from '../types';

export function useAgentContextsData() {
  const [data, setData] = useState<ContextsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    setLoading(true);
    try { setData(await katerApi.contexts()); setError(null); }
    catch (reason: unknown) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  return { data, error, loading, refresh };
}
