import { useCallback, useEffect, useRef, useState } from 'react';
import { katerApi } from '../api/client';
import type { SessionEvent, SessionProjection } from '../types';

const POLL_WAIT_MS = 8000;

function isAbort(reason: unknown): boolean {
  return (reason instanceof DOMException && reason.name === 'AbortError')
    || (reason instanceof Error && reason.name === 'AbortError');
}

interface AgentSessionTransportState {
  contextId: string | null;
  session: SessionProjection | null;
  events: SessionEvent[];
  error: string | null;
  loading: boolean;
  mutating: boolean;
}

export function useAgentSessionTransport(contextId: string | null) {
  const requestedContextId = useRef(contextId);
  const requestGeneration = useRef(0);
  requestedContextId.current = contextId;
  const [epoch, setEpoch] = useState(0);
  const [state, setState] = useState<AgentSessionTransportState>({
    contextId: null, session: null, events: [], error: null, loading: false, mutating: false,
  });
  const refresh = useCallback(() => { setEpoch(value => value + 1); }, []);

  useEffect(() => {
    const requestedId = contextId;
    const generation = ++requestGeneration.current;
    const controller = new AbortController();
    if (!requestedId) {
      setState({ contextId: null, session: null, events: [], error: null, loading: false, mutating: false });
      return;
    }
    setState({ contextId: requestedId, session: null, events: [], error: null, loading: true, mutating: false });
    void (async () => {
      try {
        const session = await katerApi.session(requestedId, controller.signal);
        if (requestedContextId.current !== requestedId || requestGeneration.current !== generation) return;
        const first = await katerApi.sessionEvents(requestedId, { after_seq: 0, wait_ms: 0, signal: controller.signal });
        if (requestedContextId.current !== requestedId || requestGeneration.current !== generation) return;
        let afterSeq = first.next_seq;
        let events = first.events;
        setState({ contextId: requestedId, session, events, error: null, loading: false, mutating: false });
        while (!controller.signal.aborted && requestGeneration.current === generation) {
          const batch = await katerApi.sessionEvents(requestedId, {
            after_seq: afterSeq,
            wait_ms: POLL_WAIT_MS,
            signal: controller.signal,
          });
          if (requestedContextId.current !== requestedId || requestGeneration.current !== generation) return;
          if (batch.events.length) {
            afterSeq = batch.next_seq;
            events = events.concat(batch.events);
            setState(current => (
              current.contextId === requestedId && requestGeneration.current === generation
                ? { ...current, events }
                : current
            ));
          } else {
            afterSeq = batch.next_seq;
          }
        }
      } catch (reason: unknown) {
        if (controller.signal.aborted || isAbort(reason)) return;
        if (requestedContextId.current === requestedId && requestGeneration.current === generation) {
          setState({
            contextId: requestedId,
            session: null,
            events: [],
            error: reason instanceof Error ? reason.message : String(reason),
            loading: false,
            mutating: false,
          });
        }
      }
    })();
    return () => { controller.abort(); };
  }, [contextId, epoch]);

  const runMutation = useCallback(async (op: () => Promise<unknown>) => {
    if (!contextId) return;
    setState(current => ({ ...current, mutating: true, error: null }));
    try {
      await op();
      refresh();
    } catch (reason: unknown) {
      setState(current => ({
        ...current,
        mutating: false,
        error: reason instanceof Error ? reason.message : String(reason),
      }));
      throw reason;
    }
  }, [contextId, refresh]);

  const submit = useCallback((prompt: string) => {
    if (!contextId) return Promise.resolve();
    return runMutation(() => katerApi.sessionSubmit(contextId, prompt));
  }, [contextId, runMutation]);

  const continueSession = useCallback(() => {
    if (!contextId) return Promise.resolve();
    return runMutation(() => katerApi.sessionContinue(contextId));
  }, [contextId, runMutation]);

  const cancelActive = useCallback((reason = 'operator') => {
    const workId = state.session?.active_work?.work_id;
    if (!contextId || !workId) return Promise.resolve();
    return runMutation(() => katerApi.sessionCancel(contextId, workId, reason));
  }, [contextId, runMutation, state.session?.active_work?.work_id]);

  const matchesContext = state.contextId === contextId;
  return {
    contextId: matchesContext ? state.contextId : null,
    session: matchesContext ? state.session : null,
    events: matchesContext ? state.events : [],
    error: matchesContext ? state.error : null,
    loading: contextId !== null && (!matchesContext || state.loading),
    mutating: matchesContext ? state.mutating : false,
    submit,
    continueSession,
    cancelActive,
    refresh,
  };
}
