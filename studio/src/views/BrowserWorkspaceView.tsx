import { Activity, Gauge, RefreshCw, Server } from 'lucide-react';
import { BrowserProviderCard } from '../components/BrowserProviderCard';
import { BrowserSessionCard } from '../components/BrowserSessionCard';
import { EmptyState } from '../components/EmptyState';
import { MetricCard } from '../components/MetricCard';
import { PageHeader } from '../components/PageHeader';
import { useBrowserData } from '../hooks/useBrowserData';

export function BrowserWorkspaceView() {
  const { providers, sessions, error, loading, refresh } = useBrowserData();
  const stats = sessions?.stats;
  const available = providers?.providers.filter(provider => provider.available).length ?? 0;
  const refreshButton = <button className="secondary-action" onClick={() => void refresh()} disabled={loading}><RefreshCw size={13} aria-hidden />{loading ? 'Refreshing' : 'Refresh'}</button>;
  return <section className="view-stack">
    <PageHeader title="Browser Workspace" description="Provider readiness and live session state from Kater browser routes." aside={refreshButton} />
    {error && <EmptyState>Browser state unavailable: {error}</EmptyState>}
    {!error && <>
      <div className="metrics-grid"><MetricCard icon={Server} label="Providers available" value={`${available}/${providers?.providers.length ?? '—'}`} /><MetricCard icon={Activity} label="Live sessions" value={stats?.live ?? '—'} /><MetricCard icon={Gauge} label="Total actions" value={stats?.total_actions ?? '—'} /></div>
      <div className="subsection"><div className="subsection-title"><span>Providers</span><small>readiness</small></div><div className="provider-grid">{providers?.providers.map(provider => <BrowserProviderCard provider={provider} key={provider.kind} />)}</div></div>
      <div className="subsection"><div className="subsection-title"><span>Sessions</span><small>{stats?.sessions ?? 0} current · max {stats?.max_sessions ?? '—'}</small></div>
        {sessions?.sessions.length ? <div className="session-list">{sessions.sessions.map((session, index) => <BrowserSessionCard session={session} key={String(session.id ?? session.session_id ?? index)} />)}</div> : <EmptyState>No live browser sessions. Studio does not invent demo sessions.</EmptyState>}
      </div>
    </>}
  </section>;
}
