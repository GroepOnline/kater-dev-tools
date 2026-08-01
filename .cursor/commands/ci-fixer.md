---
name: ci-fixer
description: >-
  CI and local lint/test fixer for the current PR branch. Use when gh pr checks
  or GitHub Actions are red and you want isolated log digging plus a minimal fix
  without distracting the parent coordinator.
---

# /ci-fixer

Dispatch the **`ci-fixer`** subagent using `.cursor/agents/ci-fixer.md`.

Do not invent a parallel procedure. Prefer the agent SSOT under `.cursor/`.

## When to use

- `gh pr checks` or GitHub Actions are red
- Isolated log digging and minimal fix on the current PR branch
- Parent coordinator should stay focused on integration

## How to run

1. Read `.cursor/agents/ci-fixer.md` for the full contract and return format.
2. Launch the `ci-fixer` subagent with PR number (or infer from branch), allowed files, and head SHA if needed.
3. After fix, re-verify with `/local-verify` and `/pr-gate` when merge-ready matters.

## Related skills

| Skill | Path |
| --- | --- |
| Local reproduce | `.cursor/skills/local-verify/SKILL.md` |
| Merge-ready gate | `.cursor/skills/pr-gate/SKILL.md` |
| Gateway ordering | `.cursor/skills/kater-gateway/SKILL.md` |
