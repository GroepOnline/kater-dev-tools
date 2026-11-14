import * as React from "react";
import { cn } from "../../../lib/cn";

/**
 * CodexToolCall — Codex-style action line with a status-colored `•` dot,
 * a `command` (optionally followed by `arg`) and a `result` count.
 *
 * Mirrors ClaudeToolCall's structure: a real <details> disclosure,
 * keyboard-operable, expandable via `children`, with a cyan focus ring.
 * The command text is rendered in `var(--bn-cyan)` to match Codex's
 * tool-call grammar.
 */
type Status = "ok" | "error" | "run";

const DOT: Record<Status, string> = {
  ok: "var(--bn-green)",
  error: "var(--bn-pink)",
  run: "var(--bn-yellow)",
};

export function CodexToolCall({
  command,
  arg,
  result,
  status = "ok",
  defaultOpen = false,
  className,
  children,
}: {
  command: string;
  arg?: string;
  result?: string;
  status?: Status;
  defaultOpen?: boolean;
  className?: string;
  children?: React.ReactNode;
}) {
  const expandable = Boolean(children);
  return (
    <details
      open={defaultOpen}
      className={cn(
        "group font-mono text-[13px] leading-[1.55] [&_summary::-webkit-details-marker]:hidden",
        className,
      )}
    >
      <summary
        className={cn(
          "flex min-w-0 list-none items-baseline gap-2 outline-none",
          expandable ? "cursor-pointer" : "cursor-default",
          "focus-visible:ring-1 focus-visible:ring-[var(--bn-cyan)]/60",
        )}
      >
        <span aria-hidden className="shrink-0" style={{ color: DOT[status] }}>
          •
        </span>
        <span className="min-w-0 break-words text-[var(--bn-cyan)]">
          {command}
        </span>
        {arg !== undefined ? (
          <>
            <span className="shrink-0 text-[var(--bn-muted)]">(</span>
            <span className="min-w-0 break-words text-[var(--bn-cyan)]">{arg}</span>
            <span className="shrink-0 text-[var(--bn-muted)]">)</span>
          </>
        ) : null}
        {result !== undefined ? (
          <span className="shrink-0 text-[var(--bn-muted)]">{result}</span>
        ) : null}
        {expandable ? (
          <span className="shrink-0 text-[var(--bn-muted)] group-open:hidden">
            ▸
          </span>
        ) : null}
      </summary>
      {expandable ? (
        <pre className="mt-1 overflow-x-auto whitespace-pre-wrap pl-4 text-[var(--bn-muted)]">
          {children}
        </pre>
      ) : null}
    </details>
  );
}
