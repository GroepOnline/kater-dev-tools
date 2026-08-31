import { Activity, Boxes, Search, ShieldAlert } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { CatalogResponse } from '../types';
import { IntegrationCard } from '../components/IntegrationCard';
import { MetricCard } from '../components/MetricCard';
import { PageHeader } from '../components/PageHeader';

export function IntegrationsView({ catalog, loading }: { catalog: CatalogResponse | null; loading: boolean }) {
  const [query, setQuery] = useState('');
  const servers = useMemo(() => (catalog?.servers ?? []).filter(server => `${server.name} ${server.description ?? ''}`.toLowerCase().includes(query.toLowerCase())), [catalog, query]);
  const active = (catalog?.servers ?? []).filter(server => server.enabled).length;
  const needs = (catalog?.servers ?? []).filter(server => server.enabled && (server.env_configured ?? server.configured) === false).length;
  return <section className="view-stack">
    <PageHeader title="Integrations" description="Real Kater catalog. No Studio mock telemetry or replacement backend." aside={<span className="count-badge">{catalog?.total ?? 0} available</span>} />
    <div className="metrics-grid"><MetricCard icon={Boxes} label="Catalog" value={catalog?.total ?? '—'} /><MetricCard icon={Activity} label="Enabled" value={active} /><MetricCard icon={ShieldAlert} label="Needs config" value={needs} /></div>
    <label className="search-field"><Search size={15} aria-hidden /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search MCP servers and tools" /></label>
    {loading ? <div className="empty-state">Loading catalog…</div> : <div className="integration-grid">{servers.map(server => <IntegrationCard server={server} key={server.name} />)}</div>}
  </section>;
}
