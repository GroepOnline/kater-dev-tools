import { useState } from 'react';
import type { RemoteContext, SessionProjection } from '../types';

const CANCELLABLE = new Set(['idle', 'waiting', 'working', 'blocked', 'review']);

export function AgentSessionComposer({
  context,
  session,
  mutating,
  error,
  onSubmitWork,
  onContinueSession,
  onCancelWork,
}: {
  context: RemoteContext;
  session: SessionProjection | null;
  mutating: boolean;
  error: string | null;
  onSubmitWork: (prompt: string) => Promise<void>;
  onContinueSession: () => Promise<void>;
  onCancelWork: () => Promise<void>;
}) {
  const [prompt, setPrompt] = useState('');
  const activeWork = session?.active_work ?? null;
  const canCancel = Boolean(activeWork && CANCELLABLE.has(String(activeWork.state)));
  const disabled = mutating || !context.active;
  const trimmed = prompt.trim();

  const submit = async () => {
    if (!trimmed || disabled) return;
    await onSubmitWork(trimmed);
    setPrompt('');
  };

  return <form className="agent-session-composer" aria-label="Session work composer" onSubmit={event => { event.preventDefault(); void submit(); }}>
    <label htmlFor="agent-session-prompt">Natural-language work</label>
    <textarea
      id="agent-session-prompt"
      name="prompt"
      rows={3}
      value={prompt}
      disabled={disabled}
      placeholder={context.active ? 'Submit work against this remote context…' : 'Inactive context — mutations denied'}
      onChange={event => setPrompt(event.target.value)}
    />
    <div className="agent-session-composer-actions">
      <button className="primary-action" type="submit" disabled={disabled || !trimmed}>{mutating ? 'Submitting…' : 'Submit work'}</button>
      <button className="secondary-action" type="button" disabled={disabled} onClick={() => { void onContinueSession(); }}>Continue session</button>
      {canCancel && <button className="secondary-action" type="button" disabled={disabled} onClick={() => { void onCancelWork(); }}>Cancel work</button>}
    </div>
    {activeWork && <small>Active work <code>{activeWork.work_id}</code> · {activeWork.state} · katerContextId {session?.correlation.katerContextId ?? context.context_id}</small>}
    {error && <div className="error-strip inline-error" role="alert">{error}</div>}
  </form>;
}
