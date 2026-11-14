import { RefreshCw } from 'lucide-react';
import { CodexHeader } from '../components/brainless/codex/codex-header';
import { CodexMessage } from '../components/brainless/codex/codex-message';
import { ClaudeToolCall } from '../components/brainless/claude/claude-tool-call';
import { EmptyState } from '../components/EmptyState';
import { usePrGateData } from '../hooks/usePrGateData';

function verdictStyle(verdict: string): { color: string } {
  if (verdict === 'PASS') return { color: 'var(--bn-green)' };
  if (verdict === 'WARN') return { color: 'var(--bn-yellow)' };
  return { color: 'var(--bn-pink)' };
}

export function PrGateView() {
  const { data, error, loading, refresh } = usePrGateData();
  const blocked = data?.pulls.filter(pull => pull.gate?.verdict !== 'PASS').length ?? 0;
  return <section className="view-stack">
    <div className="component-card" style={{ padding: '14px 18px', display: 'flex', alignItems: 'center', gap: '12px' }}>
      <strong style={{ fontSize: '15px' }}>PR Gate &amp; CI</strong>
      <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Exact live Kater gate state. No sample PRs or generated verdicts.</span>
      <div style={{ marginLeft: 'auto' }} className="header-actions">
        <span className="count-badge">{data?.count ?? 0} open · {blocked} blocked</span>
        <button className="secondary-action" onClick={() => void refresh()} disabled={loading}>
          <RefreshCw size={13} aria-hidden />{loading ? 'Refreshing' : 'Refresh'}
        </button>
      </div>
    </div>
    {error && <EmptyState>PR state unavailable: {error}</EmptyState>}
    {!error && loading && !data && <EmptyState>Loading current PR gate state…</EmptyState>}
    {!error && data?.pulls.length === 0 && <EmptyState>No open pull requests.</EmptyState>}
    {!error && data && (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {data.pulls.map(pull => {
          const verdict = pull.gate?.verdict || 'UNKNOWN';
          const reasons = pull.gate?.reasons ?? [];
          const checks = [
            { name: 'required-checks', conclusion: (pull.required_failed ?? 0) === 0 ? 'success' : 'failure' },
            { name: 'pending-checks', conclusion: (pull.pending_checks ?? 0) === 0 ? 'success' : 'pending' },
            { name: 'failed-checks', conclusion: (pull.failed_checks ?? 0) === 0 ? 'success' : 'failure' },
            { name: 'required-success', conclusion: (pull.required_missing ?? 0) === 0 ? 'success' : 'pending' },
            { name: 'approvals', conclusion: (pull.independent_approvals ?? 0) > 0 ? 'success' : 'pending' },
          ];
          return (
            <div key={`${pull.repo}-${pull.number}`} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <CodexHeader
                version={`#${pull.number}`}
                model={pull.title}
                directory={pull.repo}
              />
              <CodexMessage role="assistant">
                <span style={verdictStyle(verdict)}>
                  verdict: {verdict} · {pull.author_login} · {pull.head_ref} → {pull.base_ref}
                </span>
              </CodexMessage>
              {reasons.length > 0 && (
                <CodexMessage role="assistant">
                  reasons: {reasons.join('; ')}
                </CodexMessage>
              )}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                {checks.map(check => {
                  const status = check.conclusion === 'success' ? 'success' : check.conclusion === 'failure' ? 'error' : 'pending';
                  return (
                    <ClaudeToolCall
                      key={check.name}
                      tool={check.name}
                      arg={pull.url}
                      result={check.conclusion}
                      status={status}
                    />
                  );
                })}
              </div>
              <CodexMessage role="assistant">
                approvals: {pull.independent_approvals} · pending: {pull.pending_checks} · failed: {pull.failed_checks} · open threads: {pull.open_threads}
              </CodexMessage>
            </div>
          );
        })}
      </div>
    )}
  </section>;
}