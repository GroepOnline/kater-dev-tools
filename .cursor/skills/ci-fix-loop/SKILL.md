---
name: ci-fix-loop
role: meta
ambient: false
description: >-
  Indexable stub so kater-dev-tools-ci-fixer extends/chains resolve under
  .cursor/skills. Canonical CI fix procedure lives in portable skills, not here.
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

Thin satellite so `kater-dev-tools-ci-fixer` `extends: ci-fix-loop` and
`chains.skills` resolve. The artifact hook only indexes `.cursor/skills`.

## Canonical portable skills (load these — do not duplicate)

| Home | Path / name | Role |
| --- | --- | --- |
| Account portable | `~/.agents/skills/` skill named `ci-fix-loop` | Org-wide CI repair chain (when that lane is in scope) |
| Cursor team-kit | plugin skill `fix-ci` | Focused PR-check repair |

## Repo facts / twin

| Artifact | Path |
| --- | --- |
| Satellite (commands, paths) | `.cursor/skills/kater-dev-tools-ci-fixer/SKILL.md` |
| Twin subagent | `.cursor/agents/ci-fixer.md` |
| Post-fix local matrix | `.cursor/skills/kater-dev-tools-local-verify/SKILL.md` |
| Merge-ready gate | `.cursor/skills/pr-gate/SKILL.md` |

## Hard bans (org)

- No `ci-watcher`, no `gh run watch`, no poll-until-green loops.
- One-shot `gh pr checks` / `gh run view --log-failed` only when authorized or after notify.
- Never merge, close, or force-push unless explicitly authorized.
- CI/lint/tests only — no feature scope creep.
