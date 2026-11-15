import { Clock3 } from 'lucide-react';
import type { SessionEvent } from '../types';
import { AgentActivityLine, classifyAgentProvider } from './brainless/AgentEventLine';

export function AgentSessionEventRow({ event }: { event: SessionEvent }) {
  const surface = classifyAgentProvider(event.provider);
  const original = event.payload.original_type;
  const label = event.type === 'event.unknown' && typeof original === 'string'
    ? `event.unknown · ${original}`
    : event.type;
  const detail = event.provider ? `${event.type} · ${event.provider}` : `${event.type} · Kater`;
  const timestamp = new Date(event.created_at * 1000);
  const success = event.type !== 'work.cancelled' && event.type !== 'event.unknown';

  return <article className="agent-audit-row" data-surface={surface} data-event-type={event.type}>
    <div className="agent-audit-primary">
      <AgentActivityLine label={label} durationMs={0} success={success} surface={surface} detail={detail} />
    </div>
    <div className="agent-audit-detail">
      <span>{event.work_id ?? 'session'} · seq {event.seq}</span>
      <time dateTime={!Number.isNaN(timestamp.getTime()) ? timestamp.toISOString() : undefined}>
        <Clock3 size={11} aria-hidden />{!Number.isNaN(timestamp.getTime()) ? timestamp.toLocaleTimeString() : '—'}
      </time>
    </div>
  </article>;
}
