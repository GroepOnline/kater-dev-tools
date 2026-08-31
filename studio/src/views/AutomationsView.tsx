import { Activity, RefreshCw, Workflow } from 'lucide-react';
import { AutomationCard } from '../components/AutomationCard';
import { EmptyState } from '../components/EmptyState';
import { MetricCard } from '../components/MetricCard';
import { PageHeader } from '../components/PageHeader';
import { useAutomationsData } from '../hooks/useAutomationsData';

export function AutomationsView() {
  const { data, error, loading, pendingIds, refresh, runNow, setEnabled, saveSchedule } = useAutomationsData();
  const enabled = data?.automations.filter(item => item.enabled).length ?? 0;
  const healthy = data?.automations.filter(item => item.enabled && item.last_status === 'ok').length ?? 0;
  const refreshButton = <button className="secondary-action" onClick={() => void refresh()} disabled={loading}><RefreshCw size={13} aria-hidden />{loading ? 'Refreshing' : 'Refresh'}</button>;
  return <section className="view-stack">
    <PageHeader title="Automations" description="Policy-gated runtime controls: run, enable/disable and schedule changes use the existing Kater capability routes." aside={refreshButton} />
    {error && <div className="error-strip inline-error">Mutation/read error: {error}</div>}
    <div className="metrics-grid"><MetricCard icon={Workflow} label="Automations" value={data?.total ?? '—'} /><MetricCard icon={Activity} label="Enabled" value={enabled} /><MetricCard icon={Activity} label="Healthy" value={healthy} /></div>
    {data?.automations.length ? <div className="automation-list">{data.automations.map(item => <AutomationCard automation={item} pending={pendingIds.has(item.id)} onRun={id => void runNow(id)} onToggle={(id, value) => void setEnabled(id, value)} onSaveSchedule={(id, seconds) => void saveSchedule(id, seconds)} key={item.id} />)}</div> : !loading && <EmptyState>No automations configured.</EmptyState>}
  </section>;
}
