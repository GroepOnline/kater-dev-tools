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
  const active = allServers.filter(server => server.enabled).length;
  const needs = allServers.filter(server => server.enabled && (server.env_configured ?? server.configured) === false).length;

  const hasQuery = query.trim().length > 0;
  const catalogAside = loading
    ? <span className="count-badge">loading</span>
    : catalog
      ? <span className="count-badge">{catalog.total} available</span>
      : <span className="count-badge">unavailable</span>;

  return <section className="view-stack">
    <PageHeader title="Integrations" description="Live MCP catalog from Kater. Search and inspect the real control-plane state without a parallel frontend runtime." aside={catalogAside} />
    <div className="metrics-grid"><MetricCard icon={Boxes} label="Catalog" value={catalog?.total ?? '—'} /><MetricCard icon={Activity} label="Enabled" value={catalog ? active : '—'} /><MetricCard icon={ShieldAlert} label="Needs config" value={catalog ? needs : '—'} /></div>
    {catalog && allServers.length > 0 && <IntegrationToolbar query={query} onQueryChange={setQuery} shown={servers.length} total={allServers.length} />}
    {loading ? <EmptyState>Loading catalog…</EmptyState>
      : !catalog ? <EmptyState>Catalog unavailable. Gateway status may still be available.</EmptyState>
      : allServers.length === 0 ? <EmptyState>No integrations are registered in the live catalog.</EmptyState>
      : servers.length ? <div className="integration-grid">{servers.map(server => <IntegrationCard server={server} key={server.name} />)}</div>
      : hasQuery ? <EmptyState><div className="empty-state-stack"><strong>No matching integrations</strong><span>Clear the search to return to the live catalog.</span><button className="secondary-action" type="button" onClick={() => setQuery('')}>Clear search</button></div></EmptyState>
      : <EmptyState>No integrations are available.</EmptyState>}
  </section>;
}
