---
name: ci-fix-loop
role: meta
ambient: false
description: >-
  Indexable stub so kater-dev-tools-ci-fixer extends/chains resolve under
  .cursor/skills. Resolver target only — not a second CI procedure.
details: >-
  Artifact hook scans only .cursor/skills. This file is the resolvable target for
  extends/chains; do not treat it as a second poll/watch CI loop.
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

# ci-fix-loop (repo index stub)

Resolver-only stub so `kater-dev-tools-ci-fixer` `extends: ci-fix-loop` and
`chains.skills` resolve. The artifact hook only indexes `.cursor/skills`; this
file exists so those metadata links have a local target. Procedure and gates
come from the extending skill's `extends` / `chains` wiring — not from peer
enumeration in this file.

## Hard bans

- No `ci-watcher`, no `gh run watch`, no poll-until-green loops.
- One-shot `gh pr checks` / `gh run view --log-failed` only when authorized or after notify.
- Never merge, close, or force-push unless explicitly authorized.
- CI/lint/tests only — no feature scope creep.
