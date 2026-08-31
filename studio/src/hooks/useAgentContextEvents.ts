import { useCallback, useEffect, useState } from 'react';
import { katerApi } from '../api/client';
import type { CapabilityAuditResponse } from '../types';

export function useAgentContextEvents(contextId: string | null) {
  const [data, setData] = useState<CapabilityAuditResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const refresh = useCallback(async () => {
    if (!contextId) { setData(null); setError(null); setLoading(false); return; }
    setLoading(true);
    try { setData(await katerApi.capabilityAudit(contextId)); setError(null); }
    catch (reason: unknown) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setLoading(false); }
  }, [contextId]);
  useEffect(() => { void refresh(); }, [refresh]);
  return { data, error, loading, refresh };
}
