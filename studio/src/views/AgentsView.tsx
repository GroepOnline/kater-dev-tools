import { RefreshCw } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { AgentAuditEventRow } from '../components/AgentAuditEventRow';
import { AgentAuditFilters, type AgentAuditOutcomeFilter } from '../components/AgentAuditFilters';
import { AgentContextCard } from '../components/AgentContextCard';
import { AgentRuntimeHandoff } from '../components/AgentRuntimeHandoff';
import { AgentSessionEventRow } from '../components/AgentSessionEventRow';
import { AgentSessionFilters } from '../components/AgentSessionFilters';
import { AgentSessionSummary } from '../components/AgentSessionSummary';
import { EmptyState } from '../components/EmptyState';
import { PageHeader } from '../components/PageHeader';
import { useAgentContextEvents } from '../hooks/useAgentContextEvents';
import { useAgentContextsData } from '../hooks/useAgentContextsData';
import { useAgentSessionTransport } from '../hooks/useAgentSessionTransport';
import type { StatusResponse } from '../types';

export function AgentsView({ status }: { status: StatusResponse | null }) {
  const contexts = useAgentContextsData();
  const rows = useMemo(() => contexts.data?.contexts ?? [], [contexts.data]);
  const [sessionQuery, setSessionQuery] = useState('');
  const [activeOnly, setActiveOnly] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [auditQuery, setAuditQuery] = useState('');
  const [outcomeFilter, setOutcomeFilter] = useState<AgentAuditOutcomeFilter>('all');

  const visibleRows = useMemo(() => {
    const query = sessionQuery.trim().toLowerCase();
    return [...rows]
      .sort((left, right) => Number(right.active) - Number(left.active) || right.created_at - left.created_at)
      .filter(context => !activeOnly || context.active)
      .filter(context => !query || `${context.label ?? ''} ${context.context_id} ${context.repository ?? ''} ${context.profile} ${context.principal_id} ${context.environment ?? ''}`.toLowerCase().includes(query));
  }, [rows, sessionQuery, activeOnly]);

  useEffect(() => {
    if (selectedId && visibleRows.some(item => item.context_id === selectedId)) return;
    setSelectedId(visibleRows[0]?.context_id ?? null);
  }, [visibleRows, selectedId]);
  useEffect(() => { setAuditQuery(''); setOutcomeFilter('all'); }, [selectedId]);

  const selected = useMemo(() => visibleRows.find(item => item.context_id === selectedId) ?? null, [visibleRows, selectedId]);
  const activity = useAgentContextEvents(selectedId);
  const transport = useAgentSessionTransport(selectedId);
  const auditAvailable = Boolean(selectedId && activity.contextId === selectedId && activity.data && !activity.loading && !activity.error);
  const auditStatus = activity.loading ? 'loading' : auditAvailable ? 'available' : 'unavailable';
  const events = auditAvailable ? activity.data?.events ?? [] : [];
  const visibleEvents = useMemo(() => {
    const query = auditQuery.trim().toLowerCase();
    return events.filter(event => {
      const outcomeMatches = outcomeFilter === 'all' || event.outcome === outcomeFilter || (outcomeFilter === 'other' && event.outcome !== 'allowed' && event.outcome !== 'denied');
      const textMatches = !query || `${event.capability_id} ${event.reason ?? ''} ${event.profile ?? selected?.profile ?? ''} ${event.outcome}`.toLowerCase().includes(query);
      return outcomeMatches && textMatches;
    });
  }, [events, auditQuery, outcomeFilter, selected?.profile]);
  const refreshing = contexts.loading || activity.loading || transport.loading;
  const refresh = async () => { await Promise.all([contexts.refresh(), activity.refresh(), transport.refresh()]); };

  return <section className="view-stack">
    <PageHeader title="Agent Activity" description="Session-centered view of real Kater contexts. Natural-language work uses the Python session transport; capability audit stays a separate projection." aside={<button className="secondary-action" onClick={() => { void refresh(); }} disabled={refreshing}><RefreshCw size={13} aria-hidden />{refreshing ? 'Refreshing' : 'Refresh'}</button>} />
    {contexts.error && <div className="error-strip inline-error">Agent contexts unavailable: {contexts.error}</div>}
    <div className="agent-session-layout">
      <aside className="agent-context-list" aria-label="Remote agent contexts">
        <div className="subsection-title"><span>Sessions</span><small>{rows.filter(context => context.active).length}/{rows.length} active</small></div>
        <AgentSessionFilters query={sessionQuery} onQueryChange={setSessionQuery} activeOnly={activeOnly} onActiveOnlyChange={setActiveOnly} shown={visibleRows.length} total={rows.length} />
        {visibleRows.map(context => <AgentContextCard context={context} selected={context.context_id === selectedId} onSelect={() => setSelectedId(context.context_id)} key={context.context_id} />)}
        {!contexts.loading && !contexts.error && visibleRows.length === 0 && <EmptyState>{rows.length ? 'No sessions match the current filters.' : 'No remote contexts yet.'}</EmptyState>}
      </aside>
      <article className="agent-console component-card" aria-label="Selected agent context activity">
        {selected && <AgentSessionSummary
          context={selected}
          events={events}
          auditStatus={auditStatus}
          session={transport.session}
          transportError={transport.error}
          mutating={transport.mutating}
          onSubmitWork={prompt => transport.submit(prompt)}
          onContinueSession={() => transport.continueSession()}
          onCancelWork={() => transport.cancelActive()}
        />}
        {selected && <AgentRuntimeHandoff context={selected} />}
        <section className="agent-audit-section" aria-label="Session event timeline">
          <div className="agent-audit-heading"><div><span className="eyebrow">Transport</span><strong>Session events</strong></div><small>{transport.loading ? 'session events loading…' : `${transport.events.length} events · Python Kater`}</small></div>
          <div className="agent-console-body">
            {selected && transport.events.map(event => <AgentSessionEventRow key={event.event_id} event={event} />)}
            {transport.loading && <div className="agent-runtime-event"><span className="agent-runtime-dot" aria-hidden>•</span><span className="agent-runtime-copy"><strong>Reading session events…</strong><small>Kater</small></span></div>}
            {selected && !transport.loading && !transport.error && transport.events.length === 0 && <EmptyState>No session events for this context.</EmptyState>}
          </div>
        </section>
        <section className="agent-audit-section" aria-label="Capability activity timeline">
          <div className="agent-audit-heading"><div><span className="eyebrow">Activity</span><strong>Capability audit</strong></div><small>{auditStatus === 'loading' ? 'audit loading…' : auditAvailable ? `${visibleEvents.length}/${events.length} events · canonical Kater audit` : 'audit unavailable'}</small></div>
          {selected && auditAvailable && <AgentAuditFilters query={auditQuery} onQueryChange={setAuditQuery} outcome={outcomeFilter} onOutcomeChange={setOutcomeFilter} shown={visibleEvents.length} total={events.length} />}
          <div className="agent-console-body">
            {activity.error && <div className="error-strip inline-error">Session audit unavailable: {activity.error}</div>}
            {selected && visibleEvents.map(event => <AgentAuditEventRow key={event.id} event={event} fallbackProfile={selected.profile} surface="kater" />)}
            {activity.loading && <div className="agent-runtime-event"><span className="agent-runtime-dot" aria-hidden>•</span><span className="agent-runtime-copy"><strong>Reading context audit…</strong><small>Kater</small></span></div>}
            {selected && !activity.loading && !activity.error && events.length === 0 && <EmptyState>No capability activity for this context.</EmptyState>}
            {selected && !activity.loading && !activity.error && events.length > 0 && visibleEvents.length === 0 && <EmptyState>No audit events match the current filters.</EmptyState>}
            {!selected && !contexts.loading && <EmptyState>Select a matching remote context to inspect its session projection.</EmptyState>}
          </div>
        </section>
      </article>
    </div>
    <div className="agent-binding-note">Replaceable Studio client: session identity is the remote context. Submit/continue/cancel/poll hit Python /api/contexts/:id/session. Unknown events stay Kater-neutral unless provider is explicit.</div>
  </section>;
}
