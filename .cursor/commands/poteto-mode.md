---
name: poteto-mode
description: Run ChefGroep poteto-mode in kater-dev-tools. Load the project satellite then the global playbooks. Use for /poteto-mode, poteto, or poteto-agent work in this repo.
---

# /poteto-mode

Load `.cursor/skills/kater-poteto-mode/SKILL.md`, then follow
`~/.agents/skills/poteto-mode/SKILL.md`.

Do not copy playbooks into this repo. Do not use Cursor's built-in babysit for PR status.

## When to use

- Joep invokes `/poteto-mode` or poteto style in this checkout
- A playbook match is required (bug fix, feature, babysit, shipping)

## Twin chain

| Artifact | Path | Role |
| --- | --- | --- |
| Satellite | `.cursor/skills/kater-poteto-mode/SKILL.md` | Kater ports, worktrees, pr-gate |
| Global skill | `~/.agents/skills/poteto-mode/SKILL.md` | Playbooks and ChefGroep bind |
| Worker standing | `.cursor/agents/poteto-agent.md` | Task `generalPurpose` standing |
