import { RefreshCw } from 'lucide-react';
import { EmptyState } from '../components/EmptyState';
import { PageHeader } from '../components/PageHeader';
import { PrCard } from '../components/PrCard';
import { usePrGateData } from '../hooks/usePrGateData';

export function PrGateView() {
  const { data, error, loading, refresh } = usePrGateData();
  const blocked = data?.pulls.filter(pull => pull.gate?.verdict !== 'PASS').length ?? 0;
  return <section className="view-stack">
    <PageHeader title="PR Gate & CI" description="Exact live Kater gate state. No sample PRs or generated verdicts." aside={<div className="header-actions"><span className="count-badge">{data?.count ?? 0} open · {blocked} blocked</span><button className="secondary-action" onClick={() => void refresh()} disabled={loading}><RefreshCw size={13} aria-hidden />{loading ? 'Refreshing' : 'Refresh'}</button></div>} />
    {error && <EmptyState>PR state unavailable: {error}</EmptyState>}
    {!error && loading && !data && <EmptyState>Loading current PR gate state…</EmptyState>}
    {!error && data?.pulls.length === 0 && <EmptyState>No open pull requests.</EmptyState>}
    {!error && data && <div className="pr-list">{data.pulls.map(pull => <PrCard pull={pull} key={`${pull.repo}-${pull.number}`} />)}</div>}
  </section>;
}
