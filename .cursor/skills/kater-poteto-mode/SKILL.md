---
name: kater-poteto-mode
description: Kater facts for /poteto-mode. Ports 9090/9091/9092, pr-gate, isolated worktrees. Chains up to poteto-mode for playbooks. Use when poteto-mode runs inside kater-dev-tools.
ambient: false
chains:
  skills:
  - poteto-mode
  - pr-gate
  - kater-gateway
invocable-by:
- user
- agent
- subagent
disable-model-invocation: true
context:
  project_types: []
  file_patterns: []
  tools: []
  repos:
  - kater-dev-tools
  signals:
  - pattern: poteto-mode
    weight: 0.9
owner: chefgroep
domain: agent-runtime
risk: read-only
last_reviewed: '2026-08-30'
---

# kater-poteto-mode

Project layer for poteto-mode in kater-dev-tools. Playbooks and binds live in
`~/.agents/skills/poteto-mode`. Do not copy them here.

## Project facts

- Canonical git dir is this checkout. New work goes to `$HOME/worktrees/kater-dev-tools-<feature>`.
- Workspace folder `worktrees/` is historical. Do not add new lanes there.
- MCP SSE `:9090/sse`. REST/dashboard `:9091`. WebSocket `:9092`.
- Laptop live gateway is `kater-forward`, not `kater-local`.
- Merge proof is skill `pr-gate` plus `kater_pr_gate` on a nonempty head SHA.
- Verify ladder is `kater-gateway` then `local-verify`. Smoke needs serve stopped.
- Cursor artifacts stay under `.cursor/` only.

## Quirks

- Cloud-safe serve is `--profile core --no-proxy`.
- Do not commit `.kater/` or `.cursor/mcp.json`.
- Cursor Task has no poteto-agent type. Spawn `generalPurpose` with `.cursor/agents/poteto-agent.md` standing.

## Escalation

- Overview and playbooks. `~/.agents/skills/poteto-mode/SKILL.md`
- Bind. `~/.agents/skills/poteto-mode/references/chefgroep-bind.md`
