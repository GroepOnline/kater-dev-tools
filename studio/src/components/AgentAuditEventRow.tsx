import { Clock3 } from 'lucide-react';
import type { CapabilityAuditEvent } from '../types';
import { AgentActivityLine, type AgentSurface } from './brainless/AgentEventLine';
import { StatusPill } from './StatusPill';

export function AgentAuditEventRow({ event, fallbackProfile, surface }: { event: CapabilityAuditEvent; fallbackProfile: string; surface: AgentSurface }) {
  const timestamp = new Date(event.timestamp * 1000);
  const reason = event.reason?.trim();
  const state = event.outcome === 'allowed' ? 'healthy' : event.outcome === 'denied' ? 'degraded' : 'offline';
  const success = event.outcome === 'allowed';
  const profile = event.profile ?? fallbackProfile;

  return <article className={`agent-audit-row outcome-${event.outcome}`} data-surface={surface}>
    <div className="agent-audit-primary"><AgentActivityLine label={event.capability_id} durationMs={event.duration_ms} success={success} surface={surface} detail={`${event.outcome} · ${profile}`} /></div>
    <div className="agent-audit-detail"><span>{reason || 'No reason reported'}</span><div><StatusPill state={state} label={event.outcome} /><time dateTime={!Number.isNaN(timestamp.getTime()) ? timestamp.toISOString() : undefined}><Clock3 size={11} aria-hidden />{!Number.isNaN(timestamp.getTime()) ? timestamp.toLocaleTimeString() : '—'}</time></div></div>
  </article>;
}
