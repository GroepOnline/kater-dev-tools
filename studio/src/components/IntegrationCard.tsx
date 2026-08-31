import { Cable, ShieldCheck } from 'lucide-react';
import type { CatalogServer } from '../types';
import { StatusPill } from './StatusPill';

export function IntegrationCard({ server }: { server: CatalogServer }) {
  const configured = server.env_configured ?? server.configured ?? true;
  const healthy = server.enabled && configured;
  return <article className="integration-card component-card">
    <header className="integration-head">
      <span className="integration-mark"><Cable size={18} aria-hidden /></span>
      <div className="integration-title"><strong>{server.name}</strong><span>{server.transport ?? 'unknown'} · {server.risk ?? 'unknown'} risk</span></div>
      <StatusPill state={healthy ? 'healthy' : server.enabled ? 'degraded' : 'unknown'} label={healthy ? 'active' : server.enabled ? 'needs config' : 'ready'} />
    </header>
    <p>{server.description || 'Kater integration.'}</p>
    <footer>
      <span className="tag"><ShieldCheck size={12} aria-hidden />cost {server.context_cost ?? '—'}</span>
      {(server.profiles ?? []).slice(0, 3).map(profile => <span className="tag" key={profile}>{profile}</span>)}
    </footer>
  </article>;
}
