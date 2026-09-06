import { Activity, Clock3 } from 'lucide-react';
import type { CapabilityAuditEvent, RemoteContext, SessionProjection } from '../types';
import { AgentSessionComposer } from './AgentSessionComposer';
import { StatusPill } from './StatusPill';

function formatTimestamp(value?: number | null) {
  if (!value) return '—';
  const date = new Date(value * 1000);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
}

type AuditStatus = 'loading' | 'available' | 'unavailable';

export function AgentSessionSummary({
  context,
  events,
  auditStatus,
  session,
  transportError,
  mutating,
  onSubmitWork,
  onContinueSession,
  onCancelWork,
}: {
  context: RemoteContext;
  events: CapabilityAuditEvent[];
  auditStatus: AuditStatus;
  session: SessionProjection | null;
  transportError: string | null;
  mutating: boolean;
  onSubmitWork: (prompt: string) => Promise<void>;
  onContinueSession: () => Promise<void>;
  onCancelWork: () => Promise<void>;
}) {
  const label = context.label?.trim() || context.context_id;
  const allowed = events.filter(event => event.outcome === 'allowed').length;
  const denied = events.filter(event => event.outcome === 'denied').length;
  const errors = events.length - allowed - denied;
  const capabilityScope = context.allowed_capabilities.length ? `${context.allowed_capabilities.length} allowed` : 'unrestricted';
  const lifecycle = context.revoked_at ? `revoked · ${formatTimestamp(context.revoked_at)}` : context.expires_at ? `expires · ${formatTimestamp(context.expires_at)}` : 'no expiry reported';
  const lastEvent = auditStatus === 'loading' ? 'loading…' : auditStatus === 'available' ? (events[0]?.timestamp ? formatTimestamp(events[0].timestamp) : 'no audit activity') : 'unavailable';
  const agentState = session?.agent_state ?? 'idle';

  return <section className="agent-session-summary" aria-label="Selected session summary">
    <div className="agent-session-summary-head">
      <div className="agent-session-title"><span className="eyebrow">Session focus</span><strong>{label}</strong><code>{context.context_id}</code></div>
      <StatusPill state={context.active ? 'healthy' : 'offline'} label={context.active ? 'active' : 'inactive'} />
    </div>
    <div className="agent-session-facts">
      <span><strong>Profile</strong>{context.profile}</span><span><strong>Repository</strong>{context.repository ?? '—'}</span>
      <span><strong>Principal</strong>{context.principal_id}</span><span><strong>Environment</strong>{context.environment ?? '—'}</span>
      <span><strong>Capability scope</strong>{capabilityScope}</span><span><strong>Scopes</strong>{context.scopes.length || 'none reported'}</span>
      <span><strong>Created</strong>{formatTimestamp(context.created_at)}</span><span><strong>Lifecycle</strong>{lifecycle}</span>
      <span><strong>Last audit</strong>{lastEvent}</span>
      <span><strong>Agent state</strong>{agentState}</span>
      <span><strong>Work items</strong>{session?.work_total ?? 0}</span>
    </div>
    <div className="agent-session-outcomes" aria-label="Capability audit outcomes">
      {auditStatus === 'loading' ? <span><Activity size={12} aria-hidden /><strong>Audit loading…</strong></span> : auditStatus === 'available' ? <>
        <span><Activity size={12} aria-hidden /><strong>{allowed}</strong> allowed</span>
        <span><strong>{denied}</strong> denied</span><span><strong>{errors}</strong> other/error</span>
        <span><Clock3 size={11} aria-hidden /><strong>{events.length}</strong> loaded</span>
      </> : <span><Activity size={12} aria-hidden /><strong>Audit unavailable</strong></span>}
    </div>
    <div className="agent-transport-boundary">
      <div>
        <strong>Python session transport</strong>
        <span>Studio submits, continues, cancels and polls /api/contexts/:id/session. Remote contexts remain the session authority; unknown events stay Kater-neutral unless provider is explicit.</span>
      </div>
    </div>
    <AgentSessionComposer
      context={context}
      session={session}
      mutating={mutating}
      error={transportError}
      onSubmitWork={onSubmitWork}
      onContinueSession={onContinueSession}
      onCancelWork={onCancelWork}
    />
  </section>;
}
