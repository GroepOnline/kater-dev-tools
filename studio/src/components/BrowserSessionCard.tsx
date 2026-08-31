import { Globe2 } from 'lucide-react';
import type { BrowserSession } from '../types';
import { StatusPill } from './StatusPill';

export function BrowserSessionCard({ session }: { session: BrowserSession }) {
  const id = String(session.id ?? session.session_id ?? 'unknown');
  const state = String(session.state ?? 'unknown');
  const live = state === 'ready' || state === 'busy';
  return <article className="session-card component-card">
    <span className="integration-mark"><Globe2 size={18} aria-hidden /></span>
    <div><strong>{id}</strong><span>{String(session.url ?? session.provider ?? 'browser session')}</span></div>
    <StatusPill state={live ? 'healthy' : state === 'failed' ? 'offline' : 'unknown'} label={state} />
  </article>;
}
