import { Chrome, Cloud, RadioTower } from 'lucide-react';
import type { BrowserProvider } from '../types';
import { StatusPill } from './StatusPill';

const icons = { local: Chrome, cdp: RadioTower, remote: Cloud };

export function BrowserProviderCard({ provider }: { provider: BrowserProvider }) {
  const Icon = icons[provider.kind as keyof typeof icons] ?? Chrome;
  return <article className="provider-card component-card">
    <header>
      <span className="integration-mark"><Icon size={18} aria-hidden /></span>
      <div><strong>{provider.kind}</strong><span>{provider.version ? `v${provider.version}` : 'provider'}</span></div>
      <StatusPill state={provider.available ? 'healthy' : 'degraded'} label={provider.available ? 'available' : 'unavailable'} />
    </header>
    <p>{provider.detail || 'No provider detail reported.'}</p>
  </article>;
}
