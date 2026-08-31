import { useEffect, useState } from 'react';
import { katerApi } from '../api/client';
import type { SettingsResponse } from '../types';

export function useSettingsData() {
  const [data, setData] = useState<SettingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    katerApi.settings()
      .then(value => { if (!cancelled) { setData(value); setError(null); } })
      .catch((reason: unknown) => { if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  return { data, error, loading };
}
