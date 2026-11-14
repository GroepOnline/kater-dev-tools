import * as React from "react";
import { cn } from "../../../lib/cn";

/**
 * ClaudeThinking — Claude's "✻ Thinking… 0.3s" single-line status.
 *
 * Accepts an optional `label` override (default "Thinking…") and an
 * optional `elapsed` suffix rendered in the muted token.
 */
export function ClaudeThinking({
  label = "Thinking…",
  elapsed,
  className,
}: {
  label?: string;
  /** Optional elapsed suffix, e.g. "0.3s". */
  elapsed?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex min-w-0 flex-wrap items-baseline gap-x-2 font-mono text-[13px] leading-[1.55]",
        className,
      )}
    >
      <span aria-hidden className="shrink-0 text-[var(--bn-purple)]">
        ✻
      </span>
      <span className="min-w-0 break-words text-[var(--bn-fg)]">{label}</span>
      {elapsed !== undefined ? (
        <span className="shrink-0 text-[var(--bn-muted)]">{elapsed}</span>
      ) : null}
    </div>
  );
}
