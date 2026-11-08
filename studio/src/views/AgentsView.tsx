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
import type { CapabilityAuditEvent, RemoteContext, SessionEvent, StatusResponse } from '../types';

function filterContexts(rows: RemoteContext[], queryText: string, activeOnly: boolean): RemoteContext[] {
  const query = queryText.trim().toLowerCase();
  return [...rows]
    .sort((left, right) => Number(right.active) - Number(left.active) || right.created_at - left.created_at)
    .filter(context => !activeOnly || context.active)
    .filter(context => !query || `${context.label ?? ''} ${context.context_id} ${context.repository ?? ''} ${context.profile} ${context.principal_id} ${context.environment ?? ''}`.toLowerCase().includes(query));
}

function filterAuditEvents(
  events: CapabilityAuditEvent[],
  queryText: string,
  outcomeFilter: AgentAuditOutcomeFilter,
  fallbackProfile?: string,
): CapabilityAuditEvent[] {
  const query = queryText.trim().toLowerCase();
  return events.filter(event => {
    const isOther = event.outcome !== 'allowed' && event.outcome !== 'denied';
    const outcomeMatches = outcomeFilter === 'all' || event.outcome === outcomeFilter || (outcomeFilter === 'other' && isOther);
    const haystack = `${event.capability_id} ${event.reason ?? ''} ${event.profile ?? fallbackProfile ?? ''} ${event.outcome}`.toLowerCase();
    return outcomeMatches && (!query || haystack.includes(query));
  });
}


function describeAuditTimelineStatus(
  auditStatus: 'loading' | 'available' | 'unavailable',
  visibleCount: number,
  totalCount: number,
): string {
  return auditStatus === 'loading' ? 'audit loading…' : auditStatus === 'available' ? `${visibleCount}/${totalCount} events · canonical Kater audit` : 'audit unavailable';
}

type SessionSidebarProps = {
  rows: RemoteContext[];
  visibleRows: RemoteContext[];
  selectedId: string | null;
  loading: boolean;
  error: string | null;
  query: string;
  activeOnly: boolean;
  onQueryChange: (value: string) => void;
  onActiveOnlyChange: (value: boolean) => void;
  onSelect: (value: string) => void;
};

function SessionSidebar(props: SessionSidebarProps) {
  const activeCount = props.rows.filter(context => context.active).length;
  const showEmpty = !props.loading && !props.error && props.visibleRows.length === 0;
  const emptyMessage = props.rows.length ? 'No sessions match the current filters.' : 'No remote contexts yet.';
  return <aside className="agent-context-list" aria-label="Remote agent contexts">
    <div className="subsection-title"><span>Sessions</span><small>{activeCount}/{props.rows.length} active</small></div>
    <AgentSessionFilters
      query={props.query}
      onQueryChange={props.onQueryChange}
      activeOnly={props.activeOnly}
      onActiveOnlyChange={props.onActiveOnlyChange}
      shown={props.visibleRows.length}
      total={props.rows.length}
    />
    {props.visibleRows.map(context => <AgentContextCard
      context={context}
      selected={context.context_id === props.selectedId}
      onSelect={() => props.onSelect(context.context_id)}
      key={context.context_id}
    />)}
    {showEmpty && <EmptyState>{emptyMessage}</EmptyState>}
  </aside>;
}

type SessionTimelineProps = {
  selected: boolean;
  events: SessionEvent[];
  loading: boolean;
  error: string | null;
};

function SessionTimeline({ selected, events, loading, error }: SessionTimelineProps) {
  const status = loading ? 'session events loading…' : `${events.length} events · Python Kater`;
  const showEmpty = selected && !loading && !error && events.length === 0;
  return <section className="agent-audit-section" aria-label="Session event timeline">
    <div className="agent-audit-heading"><div><span className="eyebrow">Transport</span><strong>Session events</strong></div><small>{status}</small></div>
    <div className="agent-console-body">
      {selected && events.map(event => <AgentSessionEventRow key={event.event_id} event={event} />)}
      {loading && <div className="agent-runtime-event"><span className="agent-runtime-dot" aria-hidden>•</span><span className="agent-runtime-copy"><strong>Reading session events…</strong><small>Kater</small></span></div>}
      {showEmpty && <EmptyState>No session events for this context.</EmptyState>}
    </div>
  </section>;
}

type AuditTimelineProps = {
  selected: RemoteContext | null;
  events: CapabilityAuditEvent[];
  visibleEvents: CapabilityAuditEvent[];
  loading: boolean;
  error: string | null;
  auditStatus: 'loading' | 'available' | 'unavailable';
  available: boolean;
  query: string;
  outcome: AgentAuditOutcomeFilter;
  onQueryChange: (value: string) => void;
  onOutcomeChange: (value: AgentAuditOutcomeFilter) => void;
  contextsLoading: boolean;
};

function AuditTimeline(props: AuditTimelineProps) {
  const auditStatus = describeAuditTimelineStatus(props.auditStatus, props.visibleEvents.length, props.events.length);
  const noEvents = Boolean(props.selected && !props.loading && !props.error && props.events.length === 0);
  const noMatches = Boolean(props.selected && !props.loading && !props.error && props.events.length > 0 && props.visibleEvents.length === 0);
  const noSelection = !props.selected && !props.contextsLoading;
  const fallbackProfile = props.selected?.profile ?? '';
  return <section className="agent-audit-section" aria-label="Capability activity timeline">
    <div className="agent-audit-heading"><div><span className="eyebrow">Activity</span><strong>Capability audit</strong></div><small>{auditStatus}</small></div>
    {props.selected && props.available && <AgentAuditFilters
      query={props.query}
      onQueryChange={props.onQueryChange}
      outcome={props.outcome}
      onOutcomeChange={props.onOutcomeChange}
      shown={props.visibleEvents.length}
      total={props.events.length}
    />}
    <div className="agent-console-body">
      {props.error && <div className="error-strip inline-error">Session audit unavailable: {props.error}</div>}
      {props.selected && props.visibleEvents.map(event => <AgentAuditEventRow key={event.id} event={event} fallbackProfile={fallbackProfile} surface="kater" />)}
      {props.loading && <div className="agent-runtime-event"><span className="agent-runtime-dot" aria-hidden>•</span><span className="agent-runtime-copy"><strong>Reading context audit…</strong><small>Kater</small></span></div>}
      {noEvents && <EmptyState>No capability activity for this context.</EmptyState>}
      {noMatches && <EmptyState>No audit events match the current filters.</EmptyState>}
      {noSelection && <EmptyState>Select a matching remote context to inspect its session projection.</EmptyState>}
    </div>
  </section>;
}

export function AgentsView({ status }: { status: StatusResponse | null }) {
  void status;
  const contexts = useAgentContextsData();
  const rows = useMemo(() => contexts.data?.contexts ?? [], [contexts.data]);
  const [sessionQuery, setSessionQuery] = useState('');
  const [activeOnly, setActiveOnly] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [auditQuery, setAuditQuery] = useState('');
  const [outcomeFilter, setOutcomeFilter] = useState<AgentAuditOutcomeFilter>('all');

  const visibleRows = useMemo(() => filterContexts(rows, sessionQuery, activeOnly), [rows, sessionQuery, activeOnly]);
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
  const visibleEvents = useMemo(
    () => filterAuditEvents(events, auditQuery, outcomeFilter, selected?.profile),
    [events, auditQuery, outcomeFilter, selected?.profile],
  );
  const refreshing = contexts.loading || activity.loading || transport.loading;
  const refresh = async () => { await Promise.all([contexts.refresh(), activity.refresh(), transport.refresh()]); };

  return <section className="view-stack">
    <PageHeader title="Agent Activity" description="Session-centered view of real Kater contexts. Natural-language work uses the Python session transport; capability audit stays a separate projection." aside={<button className="secondary-action" onClick={() => { void refresh(); }} disabled={refreshing}><RefreshCw size={13} aria-hidden />{refreshing ? 'Refreshing' : 'Refresh'}</button>} />
    {contexts.error && <div className="error-strip inline-error">Agent contexts unavailable: {contexts.error}</div>}
    <div className="agent-session-layout">
      <SessionSidebar
        rows={rows}
        visibleRows={visibleRows}
        selectedId={selectedId}
        loading={contexts.loading}
        error={contexts.error}
        query={sessionQuery}
        activeOnly={activeOnly}
        onQueryChange={setSessionQuery}
        onActiveOnlyChange={setActiveOnly}
        onSelect={setSelectedId}
      />
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
        <SessionTimeline selected={Boolean(selected)} events={transport.events} loading={transport.loading} error={transport.error} />
        <AuditTimeline
          selected={selected}
          events={events}
          visibleEvents={visibleEvents}
          loading={activity.loading}
          error={activity.error}
          auditStatus={auditStatus}
          available={auditAvailable}
          query={auditQuery}
          outcome={outcomeFilter}
          onQueryChange={setAuditQuery}
          onOutcomeChange={setOutcomeFilter}
          contextsLoading={contexts.loading}
        />
      </article>
    </div>
    <div className="agent-binding-note">Replaceable Studio client: session identity is the remote context. Submit/continue/cancel/poll hit Python /api/contexts/:id/session. Unknown events stay Kater-neutral unless provider is explicit.</div>
  </section>;
}
