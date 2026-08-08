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

Verdicts: `PASS`, `WARN`, `BLOCK`. Write actions (merge) require `PASS` on the
recorded head SHA.

Common block reasons: `HEAD_STALE`, `UNRESOLVED_THREAD`, `PENDING_CHECKS`,
`DRAFT`, `MERGE_CONFLICT`, `OVERLAPPING_PR`.

## Steps

1. **Snapshot** — `gh pr view <n> --json number,title,headRefOid,mergeable,statusCheckRollup,url`
2. **Checks** — `gh pr checks <n> --watch` when fixing CI
3. **Threads** — resolve or reply only when the fix is obvious; do not merge without explicit approval
4. **Re-gate** — re-run checks after push; head SHA must match before merge tools act
5. **Delegate** — for isolated one-PR work, launch `pr-gate` subagent with `pr`, `head_sha`, `goal`

Resolve the repository at runtime — never hardcode an org/repo slug in `.cursor/`:

```bash
gh repo view --json nameWithOwner -q .nameWithOwner
```

## Hard rules

- Never force-push or merge without explicit operator approval.
- Never skip `./scripts/smoke.sh` validation when the change touches CLI/serve paths (server stopped first).
- Parallel agents: disjoint file scope per agent (see `AGENTS.md`).

## Return format

- Verdict + reason codes
- PR URL + head SHA
- CI status summary
- Next action (if not PASS)
