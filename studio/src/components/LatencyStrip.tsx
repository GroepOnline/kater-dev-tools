import type { TelemetryEvent } from '../types';

export function LatencyStrip({ events }: { events: TelemetryEvent[] }) {
  const sample = events.slice(0, 24).reverse();
  const max = Math.max(1, ...sample.map(event => event.duration_ms));
  return <div className="latency-strip component-card" role="img" aria-label={`Latency history for ${sample.length} recent events`}>
    <div className="latency-bars">{sample.map(event => <span key={String(event.id)} className={event.success ? 'latency-ok' : 'latency-fail'} style={{ height: `${Math.max(4, Math.round((event.duration_ms / max) * 100))}%` }} title={`${event.name ?? event.type ?? 'event'} · ${event.duration_ms}ms`} />)}</div>
    <div className="latency-axis"><span>recent</span><span>max {max}ms</span></div>
  </div>;
}
