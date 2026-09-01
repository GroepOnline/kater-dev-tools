import { Activity, LockKeyhole } from 'lucide-react';
import type { CapabilityAuditEvent, RemoteContext } from '../types';
import { StatusPill } from './StatusPill';

export function AgentSessionSummary({ context, events }: { context: RemoteContext; events: CapabilityAuditEvent[] }) {
  const label = context.label?.trim() || context.context_id;
  const allowed = events.filter(event => event.outcome === 'allowed').length;
  const denied = events.filter(event => event.outcome === 'denied').length;
  const errors = events.length - allowed - denied;
  const capabilityScope = context.allowed_capabilities.length ? `${context.allowed_capabilities.length} allowed` : 'unrestricted';

  return <section className="agent-session-summary" aria-label="Selected session summary">
    <div className="agent-session-summary-head">
      <div className="agent-session-title"><span className="eyebrow">Session focus</span><strong>{label}</strong><code>{context.context_id}</code></div>
      <StatusPill state={context.active ? 'healthy' : 'offline'} label={context.active ? 'active' : 'inactive'} />
    </div>
    <div className="agent-session-facts">
      <span><strong>Profile</strong>{context.profile}</span><span><strong>Repository</strong>{context.repository ?? '—'}</span>
      <span><strong>Principal</strong>{context.principal_id}</span><span><strong>Environment</strong>{context.environment ?? '—'}</span>
      <span><strong>Capability scope</strong>{capabilityScope}</span><span><strong>Audit events</strong>{events.length}</span>
    </div>
    <div className="agent-session-outcomes" aria-label="Capability audit outcomes">
      <span><Activity size={12} aria-hidden /><strong>{allowed}</strong> allowed</span>
      <span><strong>{denied}</strong> denied</span><span><strong>{errors}</strong> other/error</span>
    </div>
    <div className="agent-transport-boundary"><LockKeyhole size={13} aria-hidden /><div><strong>Read-only projection</strong><span>Write transport not bound. Session commands stay outside Studio until the canonical transport contract exists.</span></div></div>
  </section>;
}
