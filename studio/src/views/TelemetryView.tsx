import { Activity, CheckCircle2, RefreshCw, Timer } from 'lucide-react';
import { EmptyState } from '../components/EmptyState';
import { LatencyStrip } from '../components/LatencyStrip';
import { MetricCard } from '../components/MetricCard';
import { PageHeader } from '../components/PageHeader';
import { TelemetryEventRow } from '../components/TelemetryEventRow';
import { useTelemetryData } from '../hooks/useTelemetryData';

export function TelemetryView() {
  const { data, error, loading, refresh } = useTelemetryData();
  const events = data?.events ?? [];
  const success = events.filter(event => event.success).length;
  const avg = events.length ? Math.round(events.reduce((sum, event) => sum + event.duration_ms, 0) / events.length) : 0;
  const refreshButton = <button className="secondary-action" onClick={() => void refresh()} disabled={loading}><RefreshCw size={13} aria-hidden />{loading ? 'Refreshing' : 'Refresh'}</button>;
  return <section className="view-stack">
    <PageHeader title="Telemetry" description="Latest persisted Kater events, including actual duration and outcome." aside={refreshButton} />
    {error && <EmptyState>Telemetry unavailable: {error}</EmptyState>}
    {!error && <>
      <div className="metrics-grid"><MetricCard icon={Activity} label="Loaded events" value={events.length} /><MetricCard icon={CheckCircle2} label="Successful" value={success} /><MetricCard icon={Timer} label="Average latency" value={`${avg}ms`} /></div>
      <LatencyStrip events={events} />
      {events.length ? <div className="event-list">{events.map(event => <TelemetryEventRow event={event} key={String(event.id)} />)}</div> : <EmptyState>No persisted telemetry events.</EmptyState>}
    </>}
  </section>;
}
