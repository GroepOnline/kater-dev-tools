import { ClaudeToolCall } from './claude/claude-tool-call';
import { CodexExec } from './codex/codex-exec';
import { GrokEvent } from './grok/grok-event';
import type { TelemetryEvent } from '../../types';

export type AgentSurface = 'claude' | 'codex' | 'grok' | 'kater';

function eventLabel(event: TelemetryEvent) {
  return event.name ?? event.type ?? 'runtime event';
}

export function classifyAgentSurface(event: TelemetryEvent): AgentSurface {
  const provider = typeof event.metadata?.provider === 'string'
    ? event.metadata.provider.toLowerCase()
    : '';
  if (provider.includes('anthropic') || provider.includes('claude')) return 'claude';
  if (provider.includes('xai') || provider.includes('grok')) return 'grok';
  if (provider.includes('openai') || provider.includes('codex')) return 'codex';
  return 'kater';
}

export function AgentEventLine({ event }: { event: TelemetryEvent }) {
  const surface = classifyAgentSurface(event);
  const label = eventLabel(event);
  const result = `${event.duration_ms}ms`;

  if (surface === 'claude') {
    return <ClaudeToolCall
      tool={label}
      result={result}
      status={event.success ? 'success' : 'error'}
    />;
  }
  if (surface === 'grok') {
    return <GrokEvent label={label} elapsed={result} />;
  }
  if (surface === 'codex') {
    return <CodexExec
      command={label}
      result={result}
      status={event.success ? 'ok' : 'error'}
    />;
  }

  return <div className="agent-runtime-event">
    <span className={`agent-runtime-dot ${event.success ? 'ok' : 'error'}`} aria-hidden>•</span>
    <span className="agent-runtime-copy"><strong>{label}</strong><small>{event.type ?? 'runtime'} · Kater</small></span>
    <code>{result}</code>
  </div>;
}
