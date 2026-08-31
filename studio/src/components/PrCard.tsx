import { CheckCircle2, CircleSlash2, GitCommitHorizontal, GitPullRequest, ShieldAlert } from 'lucide-react';
import type { PullRequestItem } from '../types';
import { StatusPill } from './StatusPill';

function verdictState(verdict: string) {
  if (verdict === 'PASS') return 'healthy' as const;
  if (verdict === 'WARN') return 'degraded' as const;
  return 'offline' as const;
}

export function PrCard({ pull }: { pull: PullRequestItem }) {
  const verdict = pull.gate?.verdict || 'UNKNOWN';
  const reasons = pull.gate?.reasons ?? [];
  return <article className="pr-card component-card">
    <header className="pr-card-head">
      <span className="integration-mark"><GitPullRequest size={18} aria-hidden /></span>
      <div className="pr-title"><a href={pull.url} target="_blank" rel="noreferrer">#{pull.number} {pull.title}</a><span>{pull.repo} · {pull.author_login}</span></div>
      <StatusPill state={verdictState(verdict)} label={verdict.toLowerCase()} />
    </header>
    <div className="pr-route"><span><GitCommitHorizontal size={13} aria-hidden />{pull.head_ref}</span><span>→</span><span>{pull.base_ref}</span><code>{pull.head_sha.slice(0, 8)}</code></div>
    <div className="pr-checks">
      <span><CheckCircle2 size={13} aria-hidden />{pull.required_success ?? 0} required green</span>
      <span><ShieldAlert size={13} aria-hidden />{pull.pending_checks} pending</span>
      <span><CircleSlash2 size={13} aria-hidden />{pull.failed_checks} failed</span>
      <span>{pull.independent_approvals} approvals</span>
    </div>
    {reasons.length > 0 && <footer className="reason-row">{reasons.map(reason => <span className="reason-chip" key={reason}>{reason}</span>)}</footer>}
  </article>;
}
