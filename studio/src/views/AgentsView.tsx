import { RefreshCw } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { AgentContextCard } from '../components/AgentContextCard';
import { AgentRuntimeHandoff } from '../components/AgentRuntimeHandoff';
import { AgentAuditEventRow } from '../components/AgentAuditEventRow';
import { AgentSessionSummary } from '../components/AgentSessionSummary';
import { EmptyState } from '../components/EmptyState';
import { PageHeader } from '../components/PageHeader';
import { useAgentContextEvents } from '../hooks/useAgentContextEvents';
import { useAgentContextsData } from '../hooks/useAgentContextsData';
import type { RemoteContext, StatusResponse } from '../types';

export function AgentsView({ status }: { status: StatusResponse | null }) {
  const contexts = useAgentContextsData();
  const rows = useMemo(() => contexts.data?.contexts ?? [], [contexts.data]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  useEffect(() => {
    if (selectedId && rows.some(item => item.context_id === selectedId)) return;
    setSelectedId(rows[0]?.context_id ?? null);
  }, [rows, selectedId]);
  const selected = useMemo(() => rows.find(item => item.context_id === selectedId) ?? null, [rows, selectedId]);
  const activity = useAgentContextEvents(selectedId);
  const events = activity.data?.events ?? [];
  const refreshing = contexts.loading || activity.loading;
  const refresh = async () => { await Promise.all([contexts.refresh(), activity.refresh()]); };

  return <section className="view-stack">
    <PageHeader
      title="Agent Activity"
      description="Remote contexts are the session authority. The selected context's real capability audit stays Kater-neutral because context metadata is caller-supplied, not provider evidence."
      aside={<button className="secondary-action" onClick={() => { void refresh(); }} disabled={refreshing}><RefreshCw size={13} aria-hidden />{refreshing ? 'Refreshing' : 'Refresh'}</button>}
    />
    {contexts.error && <div className="error-strip inline-error">Agent contexts unavailable: {contexts.error}</div>}
    <div className="agent-session-layout">
      <aside className="agent-context-list" aria-label="Remote agent contexts">
        <div className="subsection-title"><span>Sessions</span><small>{rows.filter(context => context.active).length}/{rows.length} active</small></div>
        {rows.map(context => <AgentContextCard context={context} selected={context.context_id === selectedId} onSelect={() => setSelectedId(context.context_id)} key={context.context_id} />)}
        {!contexts.loading && !contexts.error && rows.length === 0 && <EmptyState>No remote contexts yet.</EmptyState>}
      </aside>
      <article className="agent-console component-card" aria-label="Selected agent context activity">
        {selected && <AgentSessionSummary context={selected} events={events} />}
        {selected && <AgentRuntimeHandoff context={selected} />}
        <section className="agent-audit-section" aria-label="Capability activity timeline">
          <div className="agent-audit-heading"><div><span className="eyebrow">Activity</span><strong>Capability audit</strong></div><small>{events.length} events · canonical Kater audit</small></div>
          <div className="agent-console-body">
            {activity.error && <div className="error-strip inline-error">Session audit unavailable: {activity.error}</div>}
            {selected && events.map(event => <AgentAuditEventRow key={event.id} event={event} fallbackProfile={selected.profile} surface="kater" />)}
            {activity.loading && <div className="agent-runtime-event"><span className="agent-runtime-dot" aria-hidden>•</span><span className="agent-runtime-copy"><strong>Reading context audit…</strong><small>Kater</small></span></div>}
            {selected && !activity.loading && !activity.error && events.length === 0 && <div className="agent-runtime-event"><span className="agent-runtime-dot" aria-hidden>•</span><span className="agent-runtime-copy"><strong>No capability activity for this context.</strong><small>Kater</small></span></div>}
            {!selected && !contexts.loading && <div className="agent-runtime-event"><span className="agent-runtime-dot" aria-hidden>•</span><span className="agent-runtime-copy"><strong>Select a remote context to inspect its session projection.</strong><small>Kater contexts</small></span></div>}
          </div>
        </section>
      </article>
    </div>
    <div className="agent-binding-note">This remains a read-only Kater projection. Session selection and capability activity come from current Kater context/audit state; write controls remain deferred to the canonical session transport contract.</div>
  </section>;
}
