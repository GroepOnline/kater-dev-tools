import { RefreshCw, SquareTerminal } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { AgentContextCard } from '../components/AgentContextCard';
import { AgentActivityLine } from '../components/brainless/AgentEventLine';
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
        <div className="subsection-title"><span>Sessions</span><small>{rows.length} contexts</small></div>
        {rows.map(context => <AgentContextCard context={context} selected={context.context_id === selectedId} onSelect={() => setSelectedId(context.context_id)} key={context.context_id} />)}
        {!contexts.loading && !contexts.error && rows.length === 0 && <EmptyState>No remote contexts yet.</EmptyState>}
      </aside>
      <article className="agent-console component-card" aria-label="Selected agent context activity">
        <div className="agent-console-toolbar">
          <span><SquareTerminal size={14} aria-hidden /> {selected?.label ?? selected?.context_id ?? 'No session selected'}</span>
          <span>{selected ? `${selected.profile} · Kater context` : String(status?.profile ?? 'core')}</span>
        </div>
        {selected && <div className="agent-context-meta">
          <span><strong>context</strong>{selected.context_id}</span>
          <span><strong>repository</strong>{selected.repository ?? '—'}</span>
          <span><strong>principal</strong>{selected.principal_id}</span>
          <span><strong>capabilities</strong>{selected.allowed_capabilities.length || 'unrestricted'}</span>
        </div>}
        <div className="agent-console-body">
          {activity.error && <div className="error-strip inline-error">Session audit unavailable: {activity.error}</div>}
          {events.map(event => <AgentActivityLine
            key={event.id}
            label={event.capability_id}
            durationMs={event.duration_ms}
            success={event.outcome === 'allowed'}
            surface="kater"
            detail={`${event.outcome} · ${event.profile ?? selected?.profile ?? 'core'}`}
          />)}
          {activity.loading && <div className="agent-runtime-event"><span className="agent-runtime-dot" aria-hidden>•</span><span className="agent-runtime-copy"><strong>Reading context audit…</strong><small>Kater</small></span></div>}
          {selected && !activity.loading && !activity.error && events.length === 0 && <div className="agent-runtime-event"><span className="agent-runtime-dot" aria-hidden>•</span><span className="agent-runtime-copy"><strong>No capability activity for this context.</strong><small>Kater</small></span></div>}
          {!selected && !contexts.loading && <div className="agent-runtime-event"><span className="agent-runtime-dot" aria-hidden>•</span><span className="agent-runtime-copy"><strong>Select or create a remote context to establish an agent session.</strong><small>Kater contexts</small></span></div>}
        </div>
      </article>
    </div>
    <div className="agent-binding-note">This is a read-only projection over `/api/contexts` and `/api/audit/capabilities`. Prompt input stays disabled until Kater has an explicit natural-language execution transport; no second session store is introduced.</div>
  </section>;
}
