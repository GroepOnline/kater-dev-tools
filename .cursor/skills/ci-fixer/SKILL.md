---
name: ci-fixer
description: >-
  Fix failing CI, lint, or tests on the current PR branch with minimal diffs.
  Use for /ci-fixer, red gh pr checks, GitHub Actions failures, or when the
  parent wants an isolated fix loop without scope creep. Delegate execution to
  the ci-fixer subagent.
---

# CI fixer

Skill for turning red checks green on the current PR branch.

## Twin chain

| Artifact | Path | Role |
| --- | --- | --- |
| Skill (this) | `.cursor/skills/ci-fixer/SKILL.md` | When/why, fix contract |
| Subagent | `.cursor/agents/ci-fixer.md` | Isolated CI fix lane |

## Pre-reads

1. `.github/workflows/ci.yml` — map failed job → local command
2. `AGENTS.md` — smoke vs serve ordering
3. Catalog from hooks

## Fix contract

- CI/lint/tests only — no feature scope creep
- Minimal diff on files already in the PR (plus lockfile/metadata CI requires)
- Reproduce locally before push; re-watch checks after push

## Steps

1. **Snapshot** — `gh pr view <n> --json number,title,headRefOid,statusCheckRollup,url`
2. **Triage** — `gh pr checks <n>` → `gh run view <id> --log-failed`
3. **Reproduce** — match CI command (`uv run ruff check .`, `uv run mypy`, `uv run pytest`, `./scripts/smoke.sh` with server stopped, `uv lock --check`)
4. **Fix loop** — minimal edit → rerun affected commands
5. **Delegate** — launch `ci-fixer` subagent with `pr`, `allowed_files`, `head_sha`, `failing_jobs`

Resolve repo at runtime — never hardcode org/repo in `.cursor/`:

```bash
gh repo view --json nameWithOwner -q .nameWithOwner
```

## Hard rules

- Never merge, close, or force-push without explicit parent approval
- `./scripts/smoke.sh` only when server is stopped
- Parallel agents: disjoint file scope (see `parallel-lanes`)

## Handoffs

- After fix: `kater-verify` or `local-verify` for full proof
- Merge-ready: `pr-gate` skill + subagent

## Return format

- Verdict: FIXED | PARTIAL | BLOCKED
- Root cause (one paragraph)
- Files touched + commands run
- CI summary (green/red checks)
