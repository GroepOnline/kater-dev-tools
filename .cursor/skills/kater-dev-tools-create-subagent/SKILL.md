---
name: kater-dev-tools-create-subagent
role: satellite
ambient: true
description: kater-dev-tools-specifieke skill-authoring-feiten.
details: Chains up to skill-creator voor procedure, invarianten en safety gates.
use:
- "/create-subagent"
extends: skill-creator
chains:
  skills:
  - skill-creator
invocable-by:
- user
- agent
- subagent
disable-model-invocation: false
context:
  project_types: []
  file_patterns: []
  tools: []
  repos: ['/home/sofie/kater-dev-tools']
  signals: []
owner: chefgroep
domain: skill-authoring
risk: read-only
last_reviewed: '2026-08-08'
---

# kater-dev-tools — skill-authoring

- Project-endpoint: `.cursor/agents/<naam>.md` met YAML frontmatter.

Procedure, invarianten en gates: `skill-creator`.
