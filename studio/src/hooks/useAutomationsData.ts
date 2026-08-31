import { useCallback, useEffect, useState } from 'react';
import { katerApi } from '../api/client';
import type { AutomationsResponse } from '../types';

export function useAutomationsData() {
  const [data, setData] = useState<AutomationsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingIds, setPendingIds] = useState<Set<string>>(() => new Set());

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setData(await katerApi.automations());
      setError(null);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLoading(false);
    }
  }, []);

  const mutate = useCallback(async (id: string, action: () => Promise<unknown>) => {
    setPendingIds(current => { const next = new Set(current); next.add(id); return next; });
    try {
      await action();
      await refresh();
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setPendingIds(current => { const next = new Set(current); next.delete(id); return next; });
    }
  }, [refresh]);

  const runNow = useCallback((id: string) => mutate(id, () => katerApi.automationRun(id)), [mutate]);
  const setEnabled = useCallback((id: string, enabled: boolean) => mutate(id, () => katerApi.automationSetEnabled(id, enabled)), [mutate]);
  const saveSchedule = useCallback((id: string, scheduleSeconds: number) => mutate(id, () => katerApi.automationPatch(id, { schedule_seconds: scheduleSeconds })), [mutate]);

  useEffect(() => { void refresh(); }, [refresh]);
  return { data, error, loading, pendingIds, refresh, runNow, setEnabled, saveSchedule };
}
