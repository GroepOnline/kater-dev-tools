import { Clock3, Workflow } from 'lucide-react';
import type { AutomationItem } from '../types';
import { StatusPill } from './StatusPill';

function cadence(seconds: number) {
  if (seconds % 3600 === 0) return `${seconds / 3600}h`;
  if (seconds % 60 === 0) return `${seconds / 60}m`;
  return `${seconds}s`;
}

export function AutomationCard({ automation }: { automation: AutomationItem }) {
  const healthy = automation.last_status === 'ok';
  return <article className="automation-card component-card">
    <span className="integration-mark"><Workflow size={18} aria-hidden /></span>
    <div className="automation-copy"><strong>{automation.name}</strong><span>{automation.kind} · {automation.id}</span></div>
    <div className="automation-meta"><span><Clock3 size={12} aria-hidden />every {cadence(automation.schedule_seconds)}</span><StatusPill state={!automation.enabled ? 'unknown' : healthy ? 'healthy' : automation.last_error ? 'offline' : 'degraded'} label={!automation.enabled ? 'disabled' : automation.last_status ?? 'waiting'} /></div>
  </article>;
}
