import { RefreshCw, SquareTerminal } from 'lucide-react';
import { CodexExec } from '../components/brainless/codex/codex-exec';
import { CodexHeader } from '../components/brainless/codex/codex-header';
import { CodexMessage } from '../components/brainless/codex/codex-message';
import { PageHeader } from '../components/PageHeader';
import { useTelemetryData } from '../hooks/useTelemetryData';
import type { StatusResponse } from '../types';

function eventLabel(event: { name?: string; type?: string }) {
  return event.name ?? event.type ?? 'runtime event';
}

export function AgentsView({ status }: { status: StatusResponse | null }) {
  const { data, error, loading, refresh } = useTelemetryData();
  const events = data?.events.slice(0, 16) ?? [];
  const profile = String(status?.profile ?? 'core');
  const version = status?.version ? `v${status.version}` : 'runtime';

  return <section className="view-stack">
    <PageHeader
      title="Agent Activity"
      description="Brainless agent UI primitives, bound to real Kater telemetry. No demo runs and no parallel execution runtime."
      aside={<button className="secondary-action" onClick={() => { void refresh(); }} disabled={loading}><RefreshCw size={13} aria-hidden />{loading ? 'Refreshing' : 'Refresh'}</button>}
    />
    {error && <div className="error-strip inline-error">Agent activity unavailable: {error}</div>}
    <article className="agent-console component-card" aria-label="Kater agent activity console">
      <div className="agent-console-toolbar">
        <span><SquareTerminal size={14} aria-hidden /> Brainless / Codex surface</span>
        <span>read-only telemetry adapter</span>
      </div>
      <div className="agent-console-body">
        <CodexHeader version={version} model={`runtime-managed · ${profile}`} directory="kater://control-plane" />
        <CodexMessage role="assistant">Recent Kater control-plane activity is rendered as Codex-native execution lines.</CodexMessage>
        <div className="space-y-1">
          {events.map(event => <CodexExec
            key={String(event.id)}
            command={eventLabel(event)}
            result={`${event.duration_ms}ms`}
            status={event.success ? 'ok' : 'error'}
          />)}
        </div>
        {loading && <CodexMessage>Reading Kater telemetry…</CodexMessage>}
        {!loading && events.length === 0 && <CodexMessage>No persisted runtime events.</CodexMessage>}
      </div>
    </article>
    <div className="agent-binding-note">
      Prompt execution is intentionally not wired yet: Kater exposes capability execution, not a generic natural-language agent-session contract. The UI will not pretend otherwise.
    </div>
  </section>;
}
