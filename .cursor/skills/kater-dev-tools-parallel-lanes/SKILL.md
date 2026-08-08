---
name: kater-dev-tools-parallel-lanes
role: satellite
ambient: true
description: |-
  kater-dev-tools-specifieke workflow-verification-feiten. Chains up to workflow-verification-meta voor procedure, invarianten en safety gates.
use:
- "/parallel-lanes"
extends: workflow-verification-meta
chains:
  skills:
  - workflow-verification-meta
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
domain: workflow-verification
risk: read-only
last_reviewed: '2026-08-08'
---

# kater-dev-tools — workflow-verification

- Fan-out met disjuncte scopes; lane-subagent `.cursor/agents/parallel-lane.md`; coordinator integreert.

Procedure, invarianten en gates: `workflow-verification-meta`.
