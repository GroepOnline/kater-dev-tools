import * as React from "react";
import { cn } from "../../../lib/cn";

/**
 * GrokTurn — Grok's turn-end summary diamond.
 *
 * Captured example: `◆ Turn 4 done [hooks: 3/1] elapsed 12.4s`. Reuses
 * the same SILVER / MUTED / GREEN palette as GrokEvent for visual
 * consistency across the Grok transcript surface.
 */
const SILVER = "var(--bn-silver)"; // 38;5;7 — ◆ event diamonds
const FG = "var(--bn-fg)";
const MUTED = "var(--bn-muted)";
const DIM = "#6c6c6c";
const GREEN = "var(--bn-green)"; // 38;5;10 — successful hook counts

export function GrokTurn({
  turn,
  hooks,
  hooksOk,
  elapsed,
  className,
}: {
  turn: number;
  /** Total hooks fired in the turn. */
  hooks?: number;
  /** Successful hook count, shown as `3/1` when provided alongside `hooks`. */
  hooksOk?: number;
  /** Optional elapsed suffix, e.g. "12.4s". */
  elapsed?: string;
  className?: string;
}) {
  const showSplit = hooks !== undefined && hooksOk !== undefined;
  return (
    <div
      className={cn(
        "flex flex-wrap items-baseline gap-x-2 font-mono text-[13px] leading-[1.55]",
        className,
      )}
    >
      <span aria-hidden style={{ color: SILVER }}>
        ◆
      </span>
      <span style={{ color: FG }}>
        Turn {turn} done
        {elapsed ? (
          <>
            {" "}
            <span style={{ color: MUTED }}>elapsed {elapsed}</span>
          </>
        ) : null}
      </span>
      {showSplit ? (
        <span style={{ color: DIM }}>
          [hooks:{" "}
          <span style={{ color: GREEN }}>{hooks}</span>
          <span>/{hooksOk}</span>]
        </span>
      ) : hooks !== undefined ? (
        <span style={{ color: DIM }}>
          [hooks: <span style={{ color: GREEN }}>{hooks}</span>]
        </span>
      ) : null}
    </div>
  );
}
