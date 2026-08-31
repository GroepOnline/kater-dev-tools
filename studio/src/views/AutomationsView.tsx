import { Activity, RefreshCw, Workflow } from 'lucide-react';
import { AutomationCard } from '../components/AutomationCard';
import { EmptyState } from '../components/EmptyState';
import { MetricCard } from '../components/MetricCard';
import { PageHeader } from '../components/PageHeader';
import { useAutomationsData } from '../hooks/useAutomationsData';

export function AutomationsView() {
  const { data, error, loading, refresh } = useAutomationsData();
  const enabled = data?.automations.filter(item => item.enabled).length ?? 0;
  const healthy = data?.automations.filter(item => item.enabled && item.last_status === 'ok').length ?? 0;
  const refreshButton = <button className="secondary-action" onClick={() => void refresh()} disabled={loading}><RefreshCw size={13} aria-hidden />{loading ? 'Refreshing' : 'Refresh'}</button>;
  return <section className="view-stack">
    <PageHeader title="Automations" description="Real automation state from Kater. Mutations stay disabled until the Studio write path is policy-gated." aside={refreshButton} />
    {error && <EmptyState>Automation state unavailable: {error}</EmptyState>}
    {!error && <>
      <div className="metrics-grid"><MetricCard icon={Workflow} label="Automations" value={data?.total ?? '—'} /><MetricCard icon={Activity} label="Enabled" value={enabled} /><MetricCard icon={Activity} label="Healthy" value={healthy} /></div>
      {data?.automations.length ? <div className="automation-list">{data.automations.map(item => <AutomationCard automation={item} key={item.id} />)}</div> : <EmptyState>No automations configured.</EmptyState>}
    </>}
  </section>;
}
