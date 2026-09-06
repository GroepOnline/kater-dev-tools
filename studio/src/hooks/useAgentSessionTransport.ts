import { useCallback, useEffect, useRef, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
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

type StateSetter = Dispatch<SetStateAction<AgentSessionTransportState>>;

const EMPTY_STATE: AgentSessionTransportState = {
  contextId: null,
  session: null,
  events: [],
  error: null,
  loading: false,
  mutating: false,
};

function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : String(reason);
}

async function pollSession(
  requestedId: string,
  signal: AbortSignal,
  isCurrent: () => boolean,
  setState: StateSetter,
) {
  const session = await katerApi.session(requestedId, signal);
  if (!isCurrent()) return;

  const first = await katerApi.sessionEvents(requestedId, { after_seq: 0, wait_ms: 0, signal });
  if (!isCurrent()) return;

  let afterSeq = first.next_seq;
  let events = first.events;
  setState({ contextId: requestedId, session, events, error: null, loading: false, mutating: false });

  while (!signal.aborted && isCurrent()) {
    const batch = await katerApi.sessionEvents(requestedId, {
      after_seq: afterSeq,
      wait_ms: POLL_WAIT_MS,
      signal,
    });
    if (!isCurrent()) return;
    afterSeq = batch.next_seq;
    if (!batch.events.length) continue;
    events = events.concat(batch.events);
    setState(current => current.contextId === requestedId && isCurrent() ? { ...current, events } : current);
  }
}

async function runSessionTransport(
  requestedId: string,
  controller: AbortController,
  isCurrent: () => boolean,
  setState: StateSetter,
) {
  try {
    await pollSession(requestedId, controller.signal, isCurrent, setState);
  } catch (reason: unknown) {
    if (controller.signal.aborted || isAbort(reason) || !isCurrent()) return;
    setState({
      contextId: requestedId,
      session: null,
      events: [],
      error: errorMessage(reason),
      loading: false,
      mutating: false,
    });
  }
}

export function useAgentSessionTransport(contextId: string | null) {
  const requestedContextId = useRef(contextId);
  const requestGeneration = useRef(0);
  requestedContextId.current = contextId;
  const [epoch, setEpoch] = useState(0);
  const [state, setState] = useState<AgentSessionTransportState>(EMPTY_STATE);
  const refresh = useCallback(() => { setEpoch(value => value + 1); }, []);

  useEffect(() => {
    const requestedId = contextId;
    const generation = ++requestGeneration.current;
    const controller = new AbortController();
    if (!requestedId) {
      setState(EMPTY_STATE);
      return;
    }

    const isCurrent = () => requestedContextId.current === requestedId && requestGeneration.current === generation;
    setState({ contextId: requestedId, session: null, events: [], error: null, loading: true, mutating: false });
    void runSessionTransport(requestedId, controller, isCurrent, setState);
    return () => { controller.abort(); };
  }, [contextId, epoch]);

  const runMutation = useCallback(async (op: () => Promise<unknown>) => {
    if (!contextId) return;
    setState(current => ({ ...current, mutating: true, error: null }));
    try {
      await op();
      refresh();
    } catch (reason: unknown) {
      setState(current => ({ ...current, mutating: false, error: errorMessage(reason) }));
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
