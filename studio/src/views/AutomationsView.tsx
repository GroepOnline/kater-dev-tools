import { Activity, RefreshCw, Workflow } from 'lucide-react';
import { CodexMessage } from '../components/brainless/codex/codex-message';
import { CodexToolCall } from '../components/brainless/codex/CodexToolCall';
import { ClaudeToolCall } from '../components/brainless/claude/claude-tool-call';
import { EmptyState } from '../components/EmptyState';
import { useAutomationsData } from '../hooks/useAutomationsData';

function formatSchedule(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
  return `${Math.round(seconds / 86400)}d`;
}

export function AutomationsView() {
  const { data, error, loading, pendingIds, refresh, runNow, setEnabled, saveSchedule } = useAutomationsData();
  const enabled = data?.automations.filter(item => item.enabled).length ?? 0;
  const healthy = data?.automations.filter(item => item.enabled && item.last_status === 'ok').length ?? 0;
  const refreshButton = <button className="secondary-action" onClick={() => void refresh()} disabled={loading}><RefreshCw size={13} aria-hidden />{loading ? 'Refreshing' : 'Refresh'}</button>;
  return <section className="view-stack">
    <div className="component-card" style={{ padding: '14px 18px', display: 'flex', alignItems: 'center', gap: '12px' }}>
      <strong style={{ fontSize: '15px' }}>Automations</strong>
      <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Policy-gated runtime controls: run, enable/disable and schedule changes use the existing Kater capability routes.</span>
      <div style={{ marginLeft: 'auto' }}>{refreshButton}</div>
    </div>
    {error && <div className="error-strip inline-error">Mutation/read error: {error}</div>}
    <div className="metrics-grid" style={{ display: 'flex', gap: '12px' }}>
      <CodexMessage role="assistant"><Workflow size={13} aria-hidden /> automations: {data?.total ?? '—'}</CodexMessage>
      <CodexMessage role="assistant"><Activity size={13} aria-hidden /> enabled: {enabled}</CodexMessage>
      <CodexMessage role="assistant"><Activity size={13} aria-hidden /> healthy: {healthy}</CodexMessage>
    </div>
    {data?.automations.length ? (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {data.automations.map(item => {
          const pending = pendingIds.has(item.id);
          const lastStatus = item.last_status ?? 'pending';
          const runStatus = lastStatus === 'ok' ? 'success' : lastStatus === 'error' ? 'error' : 'pending';
          return (
            <div key={item.id} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <CodexMessage role="user">
                {item.name} — {item.kind} — {formatSchedule(item.schedule_seconds)} — {item.enabled ? 'enabled' : 'disabled'}
              </CodexMessage>
              <CodexToolCall
                command="select"
                arg={item.id}
                result="open detail"
                status="ok"
              />
              <ClaudeToolCall
                tool="run"
                arg={item.id}
                result={pending ? 'pending' : lastStatus}
                status={pending ? 'pending' : runStatus}
              />
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  className="secondary-action"
                  disabled={pending}
                  onClick={() => void runNow(item.id)}
                  aria-label={`Run ${item.name}`}
                >
                  {pending ? 'Running…' : 'Run now'}
                </button>
                <button
                  type="button"
                  className="secondary-action"
                  disabled={pending}
                  onClick={() => void setEnabled(item.id, !item.enabled)}
                  aria-label={item.enabled ? `Disable ${item.name}` : `Enable ${item.name}`}
                >
                  {item.enabled ? 'Disable' : 'Enable'}
                </button>
                <button
                  type="button"
                  className="secondary-action"
                  disabled={pending}
                  onClick={() => {
                    const next = item.schedule_seconds === 60 ? 300 : item.schedule_seconds === 300 ? 900 : 60;
                    void saveSchedule(item.id, next);
                  }}
                  aria-label={`Reschedule ${item.name}`}
                >
                  Reschedule ({formatSchedule(item.schedule_seconds)})
                </button>
              </div>
              <CodexMessage role="assistant">
                last_run: {item.last_run_at ? new Date(item.last_run_at * 1000).toLocaleString() : 'never'} · last_status: {lastStatus}{item.last_error ? ` · error: ${item.last_error}` : ''}
              </CodexMessage>
            </div>
          );
        })}
      </div>
    ) : !loading && <EmptyState>No automations configured.</EmptyState>}
  </section>;
}