import { Cable, Database, Server, Shield } from 'lucide-react';
import type { StatusResponse } from '../types';
import { MetricCard } from '../components/MetricCard';
import { PageHeader } from '../components/PageHeader';

export function ControlRoomView({ status }: { status: StatusResponse | null }) {
  const servers = status?.servers ?? {};
  return <section className="view-stack"><PageHeader title="Gateway Control Room" description="Production facts from the Python control plane, not generated demo state." /><div className="metrics-grid"><MetricCard icon={Server} label="Enabled" value={servers.enabled ?? '—'} /><MetricCard icon={Cable} label="Configured" value={servers.configured ?? '—'} /><MetricCard icon={Shield} label="Missing env" value={servers.missing_env ?? '—'} /><MetricCard icon={Database} label="Version" value={status?.version ?? 'live'} /></div><article className="truth-panel"><span className="eyebrow">Authority</span><h2>Python Kater remains the runtime</h2><p>Studio is a replaceable presentation client. MCP, REST, auth, policy, telemetry and mutations stay in the existing Kater runtime.</p></article></section>;
}
