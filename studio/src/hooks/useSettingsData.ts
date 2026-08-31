import { useCallback, useEffect, useState } from 'react';
import { katerApi } from '../api/client';
import type { SettingsResponse } from '../types';

export function useSettingsData() {
  const [data, setData] = useState<SettingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setData(await katerApi.settings());
      setError(null);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLoading(false);
    }
  }, []);

  const update = useCallback(async (patch: Record<string, unknown>) => {
    setSaving(true);
    try {
      setData(await katerApi.updateSettings(patch));
      setError(null);
      return true;
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason));
      return false;
    } finally {
      setSaving(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);
  return { data, error, loading, saving, refresh, update };
}
