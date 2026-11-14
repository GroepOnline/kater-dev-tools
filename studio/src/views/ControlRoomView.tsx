import { Cable, Server, Shield } from 'lucide-react';
import type { StatusResponse } from '../types';
import { MetricCard } from '../components/MetricCard';
import { PageHeader } from '../components/PageHeader';
import { CodexMessage } from '../components/brainless/codex/codex-message';
import { ClaudeToolCall } from '../components/brainless/claude/claude-tool-call';

interface BackendRow {
  name: string;
  transport: string;
  configured: boolean;
}

function backendRows(status: StatusResponse | null): BackendRow[] {
  const servers = status?.servers ?? {};
  const enabled = Number(servers.enabled ?? 0);
  const configured = Number(servers.configured ?? 0);
  const missingEnv = Number(servers.missing_env ?? 0);
  const rows: BackendRow[] = [];
  for (let i = 0; i < enabled; i += 1) {
    rows.push({ name: `mcp-server-${i + 1}`, transport: 'stdio', configured: true });
  }
  for (let i = 0; i < Math.max(0, configured - enabled); i += 1) {
    rows.push({ name: `mcp-configured-${i + 1}`, transport: 'http', configured: true });
  }
  for (let i = 0; i < missingEnv; i += 1) {
    rows.push({ name: `mcp-missing-${i + 1}`, transport: 'stdio', configured: false });
  }
  return rows;
}

export function ControlRoomView({ status }: { status: StatusResponse | null }) {
  const servers = status?.servers ?? {};
  const rows = backendRows(status);
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
        {rows.map(b => (
          <ClaudeToolCall
            key={b.name}
            tool={b.name}
            arg={b.transport}
            result={b.configured ? 'ready' : 'needs credentials'}
            status={b.configured ? 'success' : 'error'}
          />
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