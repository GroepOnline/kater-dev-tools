import { Clock3, Play, Power, Save, Workflow } from 'lucide-react';
import { useEffect, useState } from 'react';
import { studioConfig } from '../config';
import type { AutomationItem } from '../types';
import { StatusPill } from './StatusPill';

interface Props {
  automation: AutomationItem;
  pending: boolean;
  onRun: (id: string) => void;
  onToggle: (id: string, enabled: boolean) => void;
  onSaveSchedule: (id: string, seconds: number) => void;
}

export function AutomationCard({ automation, pending, onRun, onToggle, onSaveSchedule }: Props) {
  const [schedule, setSchedule] = useState(String(automation.schedule_seconds));
  useEffect(() => setSchedule(String(automation.schedule_seconds)), [automation.schedule_seconds]);
  const seconds = Number(schedule);
  const validSchedule = Number.isInteger(seconds) && seconds >= 10;
  const changed = validSchedule && seconds !== automation.schedule_seconds;
  const healthy = automation.last_status === 'ok';
  const canMutate = studioConfig.features.allowAutomationMutations;
  return <article className="automation-card component-card">
    <span className="integration-mark"><Workflow size={18} aria-hidden /></span>
    <div className="automation-copy"><strong>{automation.name}</strong><span>{automation.kind} · {automation.id}</span></div>
    <StatusPill state={!automation.enabled ? 'unknown' : healthy ? 'healthy' : automation.last_error ? 'offline' : 'degraded'} label={!automation.enabled ? 'disabled' : automation.last_status ?? 'waiting'} />
    <div className="automation-controls">
      <label className="schedule-field"><Clock3 size={12} aria-hidden /><input inputMode="numeric" value={schedule} onChange={event => setSchedule(event.target.value)} aria-label={`Schedule seconds for ${automation.name}`} /><span>s</span></label>
      <button className="icon-action" disabled={!canMutate || pending || !changed} onClick={() => onSaveSchedule(automation.id, seconds)} title="Save schedule"><Save size={13} aria-hidden /></button>
      <button className="secondary-action" disabled={!canMutate || pending} onClick={() => onRun(automation.id)}><Play size={13} aria-hidden />Run now</button>
      <button className="secondary-action" disabled={!canMutate || pending} onClick={() => onToggle(automation.id, !automation.enabled)}><Power size={13} aria-hidden />{automation.enabled ? 'Disable' : 'Enable'}</button>
    </div>
  </article>;
}
