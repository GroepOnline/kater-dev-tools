# Merge train — 2026-09-12

Current plan for the five open PRs on `GroepOnline/kater-dev-tools`.
Supersedes the “Remaining open items” in `docs/branch-triage-20260912.md`
(#104, morning snapshot). Kronkel-lens:
[`architecture/runtime-kronkel.md`](architecture/runtime-kronkel.md).

`main` at plan time: `af546b2` (post-#94). Do **not** merge without a
human APPROVE on the exact head SHA. This file is the plan, not a merge.

## Train

| Slot | PR | Head | Actie |
| --- | --- | --- | --- |
| 1 | [#103](https://github.com/GroepOnline/kater-dev-tools/pull/103) | `adac162` | **MERGE** — docs-only dashboard/frontend. Known erratum: Studio exists. |
| 2 | [#105](https://github.com/GroepOnline/kater-dev-tools/pull/105) | `dd230fb` | **MERGE** — taste scorecard + signal ack. Generated state; low risk. |
| 3 | [#95](https://github.com/GroepOnline/kater-dev-tools/pull/95) | `eda7bb2` | **MERGE** — Execution Foundation. Supersedes #102. |
| 4 | [#102](https://github.com/GroepOnline/kater-dev-tools/pull/102) | `3d1dccc` | **CLOSE** after #95. Do not merge. Cherry-pick leftovers later. |
| 5 | [#104](https://github.com/GroepOnline/kater-dev-tools/pull/104) | `326c9cc` | **MERGE** as historical morning triage. Do not rewrite; this file is the evening plan. |

Recovery / palette / UDO branches: already archive-tagged `archive/20260912/*`
and deleted from `origin`. Not in the train.

## Why this order

#103 and #105 do not touch `src/kater`. They can land first without
rebasing #95.

#95 is the catalog + execute contract (`toolkit → integration →
connection → action`, `execute(...)`, GitHub toolkit). #102 is a
recovery subset of the same files (`connections.py`, `plugins.py`,
`fabric_routes.py`, `routes.py`, `cli.py`, `README.md`) with a
divergent model. Simulated merge #95 ↔ #102 conflicts on all six.
Merging #102 first would install the weaker catalog and then fight #95.

#104 is a 07:00 snapshot that still calls #95 a draft with red CI. Keep
it as a record; do not treat its tail as the live order.

## Gate snapshot (one-shot `gh pr checks`, no poll)

All five: required CI green (`validate`, `lint-type`, unit 3.11–3.14,
`e2e`, `gate`, `no-org-leak`). `mergeable: MERGEABLE`, `CLEAN`.

None have an independent human APPROVE. `pr-gate` write path stays
**BLOCK** until that exists on the pinned head.

#95 extra: 17 unresolved bot threads (CodeRabbit / Sentry). v0 follow-up,
not kronkel-fails. Accept in the review note, or resolve as “won’t fix
in this PR”, before merge if policy treats `UNRESOLVED_THREAD` as hard.

## #102 leftovers (after close)

Do **not** bring `connections.py` / `plugins.py` from #102. Take only:

- `GET /api/plugins/{plugin_id}` (list route already in #95)
- `/api/integrations/{name}/{credentials,oauth/start,connections}` aliases
  that wrap existing MCP-server handlers
- Tests from `tests/test_connections_plugins.py` that do not assume the
  ToolSource-only connection model

Skip: publisher/homepage org-handle fields (already stripped in #102
head; do not reintroduce).

## Operator steps

1. Approve + merge #103 (`--match-head-commit adac162`).
2. Approve + merge #105 (`dd230fb`).
3. Approve #95 at `eda7bb2` (or newer pin). Merge with exact-head.
4. Close #102 with comment: superseded by #95; leftovers listed above.
5. Merge #104 as-is (historical).
6. Optional: one follow-up PR for plugin-detail + integration aliases.

No force-push. No merge of a stale SHA. Smoke only with server stopped.

## Kronkel (all five)

None of #102–#105 implement a Redis/Rust/Zig execute-bus or a second
Commander. #95 is the foundation *inside* the lens. Fail the next PR
that puts a queue between caller and provider without measured fan-out.
