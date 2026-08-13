---
name: ci-fix-loop
role: meta
ambient: false
description: CI fix loop — reproduce, minimal fix, re-verify. Pointer to this repo's ci-fixer lane.
details: Shared procedure for turning red checks green without scope creep. Repo-specific facts live in kater-dev-tools-ci-fixer.
use:
- "/ci-fixer"
- "fix CI"
- "red checks"
invocable-by:
- user
- agent
- subagent
disable-model-invocation: false
owner: chefgroep
domain: ci-ops
risk: read-only
last_reviewed: '2026-08-14'
---

# CI fix loop

Thin meta skill for the fix loop contract. Repo-specific commands, paths, and
invariants: `.cursor/skills/kater-dev-tools-ci-fixer/SKILL.md` and twin subagent
`.cursor/agents/ci-fixer.md`.

## Loop (one PR branch)

1. **Snapshot** — `gh pr view` for head SHA, changed files, check rollup.
2. **Triage** — `gh pr checks`; for failures, `gh run view --log-failed`.
3. **Reproduce** — run the matching local command from `.github/workflows/ci.yml`
   (ruff, mypy, pytest, smoke, lock check, pre-commit).
4. **Fix** — minimal diff; stay within PR scope + CI-required artifacts.
5. **Re-verify** — repeat affected commands until local repro passes.
6. **Push** — only when authorized; one-shot check status after notify.

## Safety gates

- CI/lint/tests only — no feature scope creep or drive-by refactors.
- Never merge, close, or force-push unless explicitly authorized.
- Resolve org/repo at runtime via `gh repo view` — never hardcode slugs in fixes.
- `./scripts/smoke.sh` requires the gateway server **stopped** (no concurrent writer).
- Stop at merge-ready; delegate merge gate to `pr-gate` when checks and threads are clear.

## Satellites

| Skill | Role |
| --- | --- |
| `kater-dev-tools-ci-fixer` | kater-dev-tools CI commands and repo facts |
| `kater-dev-tools-local-verify` | post-fix local matrix verification |
| `pr-gate` | merge-ready contract after CI is green |
