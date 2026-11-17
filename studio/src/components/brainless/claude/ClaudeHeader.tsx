import * as React from "react";
import { cn } from "../../../lib/cn";

/**
 * ClaudeHeader — Claude Code's launch banner. The terminal shows a
 * `✻ Kater Studio (version) · dir` line followed by a profile row.
 *
 * Mirrors ClaudeToolCall's color discipline but routes through the
 * `--bn-*` design tokens so future palette tweaks stay centralized.
 */
export function ClaudeHeader({
  profile = "kater",
  version = "v1.0.0",
  directory,
  className,
}: {
  profile?: string;
  version?: string;
  directory?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-1 font-mono text-[13px] leading-[1.6]",
        className,
      )}
    >
      <span aria-hidden className="shrink-0 text-[var(--bn-purple)]">
        ✻
      </span>
      <span className="shrink-0 text-[var(--bn-fg)]">Kater Studio</span>
      <span className="shrink-0 text-[var(--bn-purple)]">{version}</span>
      {directory !== undefined ? (
        <span className="min-w-0 break-words text-[var(--bn-muted)]">
          · {directory}
        </span>
      ) : null}
      <span className="shrink-0 text-[var(--bn-muted)]">
        profile: <span className="text-[var(--bn-fg)]">{profile}</span>
      </span>
    </div>
  );
}
