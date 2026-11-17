import { RefreshCw } from 'lucide-react';
import { CodexMessage } from '../components/brainless/codex/codex-message';
import { GrokEvent } from '../components/brainless/grok/grok-event';
import { EmptyState } from '../components/EmptyState';
import { useTelemetryData } from '../hooks/useTelemetryData';

export function TelemetryView() {
  const { data, error, loading, refresh } = useTelemetryData();
  const events = data?.events ?? [];
  const success = events.filter(event => event.success).length;
  const avg = events.length ? Math.round(events.reduce((sum, event) => sum + event.duration_ms, 0) / events.length) : 0;
  const refreshButton = <button className="secondary-action" onClick={() => void refresh()} disabled={loading}><RefreshCw size={13} aria-hidden />{loading ? 'Refreshing' : 'Refresh'}</button>;
  return <section className="view-stack">
    <div className="component-card" style={{ padding: '14px 18px', display: 'flex', alignItems: 'center', gap: '12px' }}>
      <strong style={{ fontSize: '15px' }}>Telemetry</strong>
      <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Latest persisted Kater events, including actual duration and outcome.</span>
      <div style={{ marginLeft: 'auto' }}>{refreshButton}</div>
    </div>
    {error && <EmptyState>Telemetry unavailable: {error}</EmptyState>}
    {!error && <>
      <CodexMessage role="assistant">events: {events.length} · ok: {success} · avg {avg}ms</CodexMessage>
      {events.length ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <CodexMessage role="assistant">{events.length} events · last {avg}ms avg</CodexMessage>
          {events.map(event => (
            <GrokEvent
              key={String(event.id)}
              label={event.name ?? event.type ?? 'event'}
              hooks={event.success ? 1 : 0}
              hooksOk={event.success ? 1 : 0}
              elapsed={`${event.duration_ms}ms`}
            />
          ))}
        </div>
      ) : <EmptyState>No persisted telemetry events.</EmptyState>}
    </>}
  </section>;
}