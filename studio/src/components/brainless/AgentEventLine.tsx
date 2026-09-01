import { ClaudeToolCall } from './claude/claude-tool-call';
import { CodexExec } from './codex/codex-exec';
import { GrokEvent } from './grok/grok-event';
import type { TelemetryEvent } from '../../types';

export type AgentSurface = 'claude' | 'codex' | 'grok' | 'kater';

export function classifyAgentProvider(provider: unknown): AgentSurface {
  const value = typeof provider === 'string' ? provider.toLowerCase() : '';
  if (value.includes('anthropic') || value.includes('claude')) return 'claude';
  if (value.includes('xai') || value.includes('grok')) return 'grok';
  if (value.includes('openai') || value.includes('codex')) return 'codex';
  return 'kater';
}

export function classifyAgentSurface(event: TelemetryEvent): AgentSurface {
  return classifyAgentProvider(event.metadata?.provider);
}

export function AgentActivityLine({ label, durationMs, success, surface = 'kater', detail = 'Kater' }: { label: string; durationMs?: number | null; success: boolean; surface?: AgentSurface; detail?: string }) {
  const result = `${Math.round(Number(durationMs ?? 0) * 100) / 100}ms`;
  if (surface === 'claude') return <ClaudeToolCall tool={label} result={result} status={success ? 'success' : 'error'} />;
  if (surface === 'grok') return <GrokEvent label={label} elapsed={result} />;
  if (surface === 'codex') return <CodexExec command={label} result={result} status={success ? 'ok' : 'error'} />;
  return <div className="agent-runtime-event">
    <span className={`agent-runtime-dot ${success ? 'ok' : 'error'}`} aria-hidden>•</span>
    <span className="agent-runtime-copy"><strong>{label}</strong><small>{detail}</small></span>
    <code>{result}</code>
  </div>;
}

export function AgentEventLine({ event }: { event: TelemetryEvent }) {
  return <AgentActivityLine
    label={event.name ?? event.type ?? 'runtime event'}
    durationMs={event.duration_ms}
    success={event.success}
    surface={classifyAgentSurface(event)}
    detail={`${event.type ?? 'runtime'} · Kater`}
  />;
}
