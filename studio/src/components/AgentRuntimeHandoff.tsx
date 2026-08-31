import { Check, Copy, Link2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import type { RemoteContext } from '../types';

export function AgentRuntimeHandoff({ context }: { context: RemoteContext }) {
  const [copied, setCopied] = useState(false);
  const payload = useMemo(() => JSON.stringify({ katerContextId: context.context_id }), [context.context_id]);

  useEffect(() => { setCopied(false); }, [context.context_id]);

  const copyCorrelation = async () => {
    try {
      await navigator.clipboard.writeText(payload);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return <section className="agent-handoff" aria-label="Agent runtime correlation handoff">
    <div className="agent-handoff-heading">
      <span><Link2 size={13} aria-hidden /> agent-runtime handoff</span>
      <small>correlation only · not authority</small>
    </div>
    <div className="agent-handoff-payload">
      <code>{payload}</code>
      <button className="secondary-action compact-action" type="button" onClick={() => { void copyCorrelation(); }}>
        {copied ? <Check size={12} aria-hidden /> : <Copy size={12} aria-hidden />}
        {copied ? 'Copied' : 'Copy correlation'}
      </button>
    </div>
    <p>Pass this field to agent-runtime orchestration calls to join run telemetry back to this Kater context. Kater still owns context validation, policy, and capability authority.</p>
  </section>;
}
