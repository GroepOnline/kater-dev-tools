import { Cable, Server, Shield } from 'lucide-react';
import type { StatusResponse } from '../types';
import { MetricCard } from '../components/MetricCard';
import { PageHeader } from '../components/PageHeader';
import { CodexMessage } from '../components/brainless/codex/codex-message';
import { ClaudeToolCall } from '../components/brainless/claude/claude-tool-call';

interface StatusFact {
  label: string;
  result: string;
  tone: 'success' | 'error' | 'pending';
}

/**
 * `/api/status` only exposes aggregate counts, so Studio must render those
 * aggregates as aggregates. Per-server facts live in `/api/catalog`.
 */
function statusFacts(status: StatusResponse | null): StatusFact[] {
  if (!status) return [];
  const servers = status.servers ?? {};
  const enabled = Number(servers.enabled ?? 0);
  const configured = Number(servers.configured ?? 0);
  const missingEnv = Number(servers.missing_env ?? 0);
  return [
    { label: 'gateway · enabled', result: `${enabled} servers enabled`, tone: 'success' },
    { label: 'gateway · configured', result: `${configured} servers configured`, tone: 'success' },
    {
      label: 'gateway · missing env',
      result: missingEnv ? `${missingEnv} servers need credentials` : 'no missing credentials',
      tone: missingEnv ? 'error' : 'success',
    },
  ];
}

export function ControlRoomView({ status }: { status: StatusResponse | null }) {
  const servers = status?.servers ?? {};
  const facts = statusFacts(status);
  const summary = status
    ? `Gateway health: ${servers.enabled ?? 0} enabled · ${servers.configured ?? 0} configured · ${servers.missing_env ?? 0} missing env · v${status.version ?? 'live'}`
    : 'Gateway health: awaiting status payload';
  return (
    <section className="view-stack">
      <PageHeader title="Gateway Control Room" description="Production facts from the Python control plane, not generated demo state." />
      <CodexMessage role="assistant">{summary}</CodexMessage>
      <div className="metrics-grid">
        <MetricCard icon={Server} label="Enabled" value={servers.enabled ?? '—'} />
        <MetricCard icon={Cable} label="Configured" value={servers.configured ?? '—'} />
        <MetricCard icon={Shield} label="Missing env" value={servers.missing_env ?? '—'} />
      </div>
      <div className="control-room-tool-calls">
        {facts.map(fact => (
          <ClaudeToolCall key={fact.label} tool={fact.label} result={fact.result} status={fact.tone} />
        ))}
      </div>
      <article className="truth-panel">
        <span className="eyebrow">Authority</span>
        <h2>Python Kater remains the runtime</h2>
        <p>Studio is a replaceable presentation client. MCP, REST, auth, policy, telemetry and mutations stay in the existing Kater runtime.</p>
      </article>
    </section>
  );
}
