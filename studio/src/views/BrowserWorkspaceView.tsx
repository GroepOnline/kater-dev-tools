import { Activity, Gauge, RefreshCw, Server } from 'lucide-react';
import { CodexExec } from '../components/brainless/codex/codex-exec';
import { CodexMessage } from '../components/brainless/codex/codex-message';
import { CodexToolCall } from '../components/brainless/codex/CodexToolCall';
import { ClaudeToolCall } from '../components/brainless/claude/claude-tool-call';
import { EmptyState } from '../components/EmptyState';
import { useBrowserData } from '../hooks/useBrowserData';

export function BrowserWorkspaceView() {
  const { providers, sessions, error, loading, refresh } = useBrowserData();
  const stats = sessions?.stats;
  const available = providers?.providers.filter(provider => provider.available).length ?? 0;
  const refreshButton = <button className="secondary-action" onClick={() => void refresh()} disabled={loading}><RefreshCw size={13} aria-hidden />{loading ? 'Refreshing' : 'Refresh'}</button>;
  return <section className="view-stack">
    <div className="component-card" style={{ padding: '14px 18px', display: 'flex', alignItems: 'center', gap: '12px' }}>
      <strong style={{ fontSize: '15px' }}>Browser Workspace</strong>
      <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Provider readiness and live session state from Kater browser routes.</span>
      <div style={{ marginLeft: 'auto' }}>{refreshButton}</div>
    </div>
    {error && <EmptyState>Browser state unavailable: {error}</EmptyState>}
    {!error && <>
      <div className="metrics-grid" style={{ display: 'flex', gap: '12px' }}>
        <CodexMessage role="assistant"><Server size={13} aria-hidden /> providers: {available}/{providers?.providers.length ?? '—'}</CodexMessage>
        <CodexMessage role="assistant"><Activity size={13} aria-hidden /> live sessions: {stats?.live ?? '—'}</CodexMessage>
        <CodexMessage role="assistant"><Gauge size={13} aria-hidden /> total actions: {stats?.total_actions ?? '—'}</CodexMessage>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <CodexMessage role="assistant">providers · {providers?.providers.length ?? 0} total · {available} available</CodexMessage>
        {providers?.providers.map(provider => (
          <ClaudeToolCall
            key={provider.kind}
            tool="provider"
            arg={provider.kind}
            result={provider.available ? 'ready' : (provider.detail ?? 'unavailable')}
            status={provider.available ? 'success' : 'error'}
          />
        ))}
        {!providers?.providers.length && <EmptyState>No browser providers reported.</EmptyState>}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <CodexMessage role="assistant">sessions · {stats?.sessions ?? 0} current · max {stats?.max_sessions ?? '—'} · persisted {stats?.persisted_actions ?? '—'}</CodexMessage>
        {sessions?.sessions.length ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {sessions.sessions.map((session, index) => {
              const id = String(session.id ?? session.session_id ?? index);
              const status = String(session.state ?? 'unknown');
              const provider = String(session.provider ?? 'unknown');
              const live = status === 'live' || status === 'ready';
              const execStatus = live ? 'ok' : status === 'closed' || status === 'error' ? 'error' : 'run';
              return (
                <CodexExec
                  key={id}
                  command={`open session · ${provider}`}
                  result={status}
                  status={execStatus}
                >
                  <CodexMessage role="user">session</CodexMessage>
                  <CodexMessage role="assistant">{id}</CodexMessage>
                  <CodexMessage role="assistant">provider: {provider} · state: {status}</CodexMessage>
                  {session.url ? <CodexMessage role="assistant">url: {String(session.url)}</CodexMessage> : null}
                  <CodexToolCall
                    command="probe"
                    arg={id}
                    result={status}
                    status={execStatus}
                  />
                </CodexExec>
              );
            })}
          </div>
        ) : <EmptyState>No live browser sessions. Studio does not invent demo sessions.</EmptyState>}
      </div>
    </>}
  </section>;
}