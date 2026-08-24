---
name: pr-gate
description: Evaluate and fix one PR until merge-ready using Kater PR gate rules and gh.
details: Use for /pr-gate, "pr gate", merge-ready checks, or when CI/review threads block merge. Delegate lane work to the pr-gate subagent.
---

# PR gate

Skill for merge-ready PR evaluation on the current git repository.

## Twin chain

| Artifact | Path | Role |
| --- | --- | --- |
| Skill (this) | `.cursor/skills/pr-gate/SKILL.md` | When/why, gate contract |
| Subagent | `.cursor/agents/pr-gate.md` | One-PR gate lane execution |

## Pre-reads

1. `AGENTS.md`
2. `src/kater/pr_control.py` (verdicts, reason codes)
3. Catalog from hooks

## Gate contract

Verdicts: `PASS`, `WARN`, `BLOCK`. Write actions (merge) require `PASS` on a
**nonempty** pinned `expected_head_sha`. Empty SHA is always a hard reject on
the write path. A nonempty pin that does not match the live head BLOCKs the
read gate (`HEAD_STALE`) as well; merge still uses `--match-head-commit`.

Common block reasons: `HEAD_STALE`, `UNRESOLVED_THREAD`, `PENDING_CHECKS`,
`FAILED_CHECKS`, `P1_LATCH`, `DRAFT`, `MERGE_CONFLICT`, `OVERLAPPING_PR`,
`REPO_DENIED`.

Merge-ready also requires:

- Required checks **SUCCESS on the exact head SHA** (`FAILED_CHECKS` otherwise)
- No open P1 in the same change-scope (`P1_LATCH`; default labels `P1` / `p1-latch`)
- Independent approval: bot, PR author, and fixer logins do not count
  (policy allowlist/denylist). When `expected_head_sha` is nonempty, only
  APPROVE covering that commit OID counts; empty review lists do not fall
  back to GitHub `reviewDecision`.
- Explicit company-control repository; private-data-plane names are denied

## Steps

1. **Snapshot** — `gh pr view <n> --json number,title,headRefOid,mergeable,statusCheckRollup,url`
2. **Checks** — notify-first: at most one `gh pr checks <n>` (no `--watch`, no poll
   loop). Incomplete or unknown → treat as not merge-ready and stop.
3. **Threads** — resolve or reply only when the fix is obvious; do not merge without independent approval
4. **Re-gate** — after push, wait for CI notify; then one-shot re-gate with the
   new head SHA. Merge tools must receive that nonempty SHA.
5. **Delegate** — for isolated one-PR work, launch `pr-gate` subagent with `pr`, `head_sha`, `goal`

Resolve the repository at runtime — never hardcode an org/repo slug in `.cursor/`:

```bash
gh repo view --json nameWithOwner -q .nameWithOwner
```

Pin `KATER_PR_REPO` and `KATER_PR_PLANE=company-control` for write/merge.

## Hard rules

- Never force-push or merge without explicit operator approval.
- Never poll CI (`gh pr checks --watch`, `gh run watch`, ci-watcher). Notify-first only.
- Never skip `./scripts/smoke.sh` validation when the change touches CLI/serve paths (server stopped first).
- Parallel agents: disjoint file scope per agent (see `AGENTS.md`).

## Return format

- Verdict + reason codes
- PR URL + head SHA
- CI status summary
- Next action (if not PASS)
