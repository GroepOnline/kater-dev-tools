import * as React from "react";
import { cn } from "../../../lib/cn";

/**
 * ClaudeMessage — a single Claude Code turn. User prompts use a bold `>`
 * marker in the muted token; assistant replies render as plain text in
 * the foreground token. Both inherit the existing monospace scale.
 */
export function ClaudeMessage({
  role = "user",
  className,
  children,
}: {
  role?: "user" | "assistant";
  className?: string;
  children: React.ReactNode;
}) {
  if (role === "user") {
    return (
      <div
        className={cn(
          "flex min-w-0 gap-2 font-mono text-[13px] leading-[1.6] text-[var(--bn-fg)]",
          className,
        )}
      >
        <span aria-hidden className="shrink-0 font-bold text-[var(--bn-muted)]">
          &gt;
        </span>
        <span className="min-w-0 flex-1 break-words">{children}</span>
      </div>
    );
  }
  return (
    <div
      className={cn(
        "min-w-0 font-mono text-[13px] leading-[1.6] text-[var(--bn-fg)]",
        className,
      )}
    >
      {children}
    </div>
  );
}
