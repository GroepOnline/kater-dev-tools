import { Activity, Boxes, ShieldAlert } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { CatalogResponse } from '../types';
import { EmptyState } from '../components/EmptyState';
import { IntegrationCard } from '../components/IntegrationCard';
import { IntegrationToolbar } from '../components/IntegrationToolbar';
import { MetricCard } from '../components/MetricCard';
import { PageHeader } from '../components/PageHeader';

export function IntegrationsView({ catalog, loading }: { catalog: CatalogResponse | null; loading: boolean }) {
  const [query, setQuery] = useState('');
  const allServers = catalog?.servers ?? [];
  const servers = useMemo(() => {
    const needle = query.toLowerCase().trim();
    if (!needle) return allServers;
    return allServers.filter(server => `${server.name} ${server.description ?? ''} ${server.transport ?? ''} ${(server.profiles ?? []).join(' ')}`.toLowerCase().includes(needle));
  }, [allServers, query]);
  const hasQuery = query.trim().length > 0;
  const active = allServers.filter(server => server.enabled).length;
  const needs = allServers.filter(server => server.enabled && (server.env_configured ?? server.configured) === false).length;

  return <section className="view-stack">
    <PageHeader title="Integrations" description="Live MCP catalog from Kater. Search and inspect the real control-plane state without a parallel frontend runtime." aside={<span className="count-badge">{loading && !catalog ? 'loading' : catalog ? `${catalog.total} available` : 'unavailable'}</span>} />
    <div className="metrics-grid"><MetricCard icon={Boxes} label="Catalog" value={catalog?.total ?? '—'} /><MetricCard icon={Activity} label="Enabled" value={catalog ? active : '—'} /><MetricCard icon={ShieldAlert} label="Needs config" value={catalog ? needs : '—'} /></div>
    {catalog && <IntegrationToolbar query={query} onQueryChange={setQuery} shown={servers.length} total={allServers.length} />}
    {loading && !catalog ? <EmptyState>Loading catalog…</EmptyState> : !catalog ? <EmptyState><div className="empty-state-stack"><strong>Catalog unavailable</strong><span>Kater did not return an integration catalog.</span></div></EmptyState> : allServers.length === 0 ? <EmptyState><div className="empty-state-stack"><strong>No integrations configured</strong><span>The live catalog is available but currently empty.</span></div></EmptyState> : servers.length ? <div className="integration-grid">{servers.map(server => <IntegrationCard server={server} key={server.name} />)}</div> : hasQuery ? <EmptyState><div className="empty-state-stack"><strong>No matching integrations</strong><span>Clear the search to return to the live catalog.</span><button className="secondary-action" type="button" onClick={() => setQuery('')}>Clear search</button></div></EmptyState> : <EmptyState>No integrations available.</EmptyState>}
  </section>;
}
