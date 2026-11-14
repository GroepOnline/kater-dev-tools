import { useEffect, useState } from 'react';
import { katerApi } from '../api/client';
import type { CatalogResponse, StatusResponse } from '../types';

export function useKaterData() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);

  const refresh = () => setTick(t => t + 1);

  useEffect(() => {
    let cancelled = false;
    Promise.all([katerApi.status(), katerApi.catalog()])
      .then(([nextStatus, nextCatalog]) => {
        if (cancelled) return;
        setStatus(nextStatus);
        setCatalog(nextCatalog);
        setError(null);
      })
      .catch((reason: unknown) => !cancelled && setError(reason instanceof Error ? reason.message : String(reason)))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [tick]);

  return { status, catalog, error, loading, refresh };
}
