import { useCallback, useEffect, useRef, useState } from 'react';
import { katerApi } from '../api/client';
import type { CapabilityAuditResponse } from '../types';

interface AgentContextEventsState {
  contextId: string | null;
  data: CapabilityAuditResponse | null;
  error: string | null;
  loading: boolean;
}

export function useAgentContextEvents(contextId: string | null) {
  const requestedContextId = useRef(contextId);
  const requestGeneration = useRef(0);
  requestedContextId.current = contextId;
  const [state, setState] = useState<AgentContextEventsState>({ contextId: null, data: null, error: null, loading: false });
  const refresh = useCallback(async () => {
    const requestedId = contextId;
    const generation = ++requestGeneration.current;
    if (!requestedId) {
      setState({ contextId: null, data: null, error: null, loading: false });
      return;
    }
    setState({ contextId: requestedId, data: null, error: null, loading: true });
    try {
      const data = await katerApi.capabilityAudit(requestedId);
      if (requestedContextId.current === requestedId && requestGeneration.current === generation) setState({ contextId: requestedId, data, error: null, loading: false });
    } catch (reason: unknown) {
      if (requestedContextId.current === requestedId && requestGeneration.current === generation) setState({ contextId: requestedId, data: null, error: reason instanceof Error ? reason.message : String(reason), loading: false });
    }
  }, [contextId]);
  useEffect(() => { void refresh(); }, [refresh]);
  const matchesContext = state.contextId === contextId;
  return {
    contextId: matchesContext ? state.contextId : null,
    data: matchesContext ? state.data : null,
    error: matchesContext ? state.error : null,
    loading: contextId !== null && (!matchesContext || state.loading),
    refresh,
  };
}
