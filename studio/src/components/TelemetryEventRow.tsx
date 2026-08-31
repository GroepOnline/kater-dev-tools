import { Activity, Timer } from 'lucide-react';
import type { TelemetryEvent } from '../types';
import { StatusPill } from './StatusPill';

export function TelemetryEventRow({ event }: { event: TelemetryEvent }) {
  const timestamp = typeof event.timestamp === 'number' ? new Date(event.timestamp * 1000) : event.timestamp ? new Date(event.timestamp) : null;
  return <article className="event-row component-card">
    <span className="integration-mark"><Activity size={17} aria-hidden /></span>
    <div className="event-copy"><strong>{event.name ?? event.type ?? 'event'}</strong><span>{event.type ?? 'unknown'} · {event.profile ?? 'no profile'}</span></div>
    <span className="event-duration"><Timer size={12} aria-hidden />{event.duration_ms}ms</span>
    <StatusPill state={event.success ? 'healthy' : 'offline'} label={event.success ? 'ok' : 'failed'} />
    <time>{timestamp && !Number.isNaN(timestamp.getTime()) ? timestamp.toLocaleTimeString() : '—'}</time>
  </article>;
}
