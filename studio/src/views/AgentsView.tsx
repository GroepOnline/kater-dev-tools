import { RefreshCw, SquareTerminal } from 'lucide-react';
import { AgentEventLine, classifyAgentSurface, type AgentSurface } from '../components/brainless/AgentEventLine';
import { PageHeader } from '../components/PageHeader';
import { useTelemetryData } from '../hooks/useTelemetryData';
import type { StatusResponse } from '../types';

const SURFACE_LABEL: Record<AgentSurface, string> = {
  claude: 'Claude',
  codex: 'Codex',
  grok: 'Grok',
  kater: 'Kater',
};

export function AgentsView({ status }: { status: StatusResponse | null }) {
  const { data, error, loading, refresh } = useTelemetryData();
  const events = data?.events.slice(0, 24) ?? [];
  const counts = events.reduce<Record<AgentSurface, number>>((acc, event) => {
    acc[classifyAgentSurface(event)] += 1;
    return acc;
  }, { claude: 0, codex: 0, grok: 0, kater: 0 });
  const profile = String(status?.profile ?? 'core');

  return <section className="view-stack">
    <PageHeader
      title="Agent Activity"
      description="Brainless renderers over real Kater telemetry. Claude, Codex or Grok styling is selected only when metadata.provider proves that route; everything else stays Kater-neutral."
      aside={<button className="secondary-action" onClick={() => { void refresh(); }} disabled={loading}><RefreshCw size={13} aria-hidden />{loading ? 'Refreshing' : 'Refresh'}</button>}
    />
    {error && <div className="error-strip inline-error">Agent activity unavailable: {error}</div>}
    <article className="agent-console component-card" aria-label="Kater agent activity console">
      <div className="agent-console-toolbar">
        <span><SquareTerminal size={14} aria-hidden /> Brainless event renderers</span>
        <span>profile {profile} · read-only</span>
      </div>
      <div className="agent-surface-summary" aria-label="Detected renderer surfaces">
        {(Object.keys(SURFACE_LABEL) as AgentSurface[]).map(surface => <span key={surface} className={`agent-surface-chip surface-${surface}`}><strong>{counts[surface]}</strong>{SURFACE_LABEL[surface]}</span>)}
      </div>
      <div className="agent-console-body">
        {events.map(event => <AgentEventLine key={String(event.id)} event={event} />)}
        {loading && <div className="agent-runtime-event"><span className="agent-runtime-dot" aria-hidden>•</span><span className="agent-runtime-copy"><strong>Reading Kater telemetry…</strong><small>runtime</small></span></div>}
        {!loading && !error && events.length === 0 && <div className="agent-runtime-event"><span className="agent-runtime-dot" aria-hidden>•</span><span className="agent-runtime-copy"><strong>No persisted runtime events.</strong><small>Kater</small></span></div>}
      </div>
    </article>
    <div className="agent-binding-note">
      Provider styling is evidence-based display only. Prompt execution remains unwired until Kater exposes a real natural-language agent-session contract.
    </div>
  </section>;
}
