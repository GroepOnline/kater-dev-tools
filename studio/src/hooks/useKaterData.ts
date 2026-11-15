import { useEffect, useState } from 'react';
import { katerApi } from '../api/client';
import type { CatalogResponse, StatusResponse } from '../types';

function failureText(reason: unknown): string {
  return reason instanceof Error ? reason.message : String(reason);
}

export function useKaterData() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);

  const refresh = () => setTick(t => t + 1);

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([katerApi.status(), katerApi.catalog()])
      .then(([statusResult, catalogResult]) => {
        if (cancelled) return;
        const failures: string[] = [];
        if (statusResult.status === 'fulfilled') {
          setStatus(statusResult.value);
        } else {
          failures.push(`status: ${failureText(statusResult.reason)}`);
        }
        if (catalogResult.status === 'fulfilled') {
          setCatalog(catalogResult.value);
        } else {
          failures.push(`catalog: ${failureText(catalogResult.reason)}`);
        }
        setError(failures.length ? failures.join(' · ') : null);
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, [tick]);

  return { status, catalog, error, loading, refresh };
}
