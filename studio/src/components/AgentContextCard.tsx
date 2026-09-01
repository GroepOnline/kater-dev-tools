import { Bot } from 'lucide-react';
import type { RemoteContext } from '../types';
import { StatusPill } from './StatusPill';

export function AgentContextCard({ context, selected, onSelect }: { context: RemoteContext; selected: boolean; onSelect: () => void }) {
  const label = context.label?.trim() || context.context_id;
  return <button type="button" className={`agent-context-card component-card ${selected ? 'selected' : ''}`} onClick={onSelect} aria-pressed={selected}>
    <span className="integration-mark"><Bot size={17} aria-hidden /></span>
    <span className="agent-context-copy"><strong>{label}</strong><small>{context.profile} · {context.repository ?? 'no repository'}</small></span>
    <StatusPill state={context.active ? 'healthy' : 'offline'} label={context.active ? 'active' : 'inactive'} />
  </button>;
}
