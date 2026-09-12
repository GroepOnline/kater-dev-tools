# Branch triage — 2026-09-12

Follow-up to `docs/branch-triage-20260906.md`. Consolidates all nine branches
that were still unmerged plus the two open PRs, against `main` at `af546b2`
(post-#94).

## Decision model

Same as 2026-09-06: land unique useful content through reviewed PRs with
exact-head CI; archive-tag superseded tips before remote delete; no force-push
to `main`; no merge of red-CI heads. New rule applied here: every
already-on-main verdict cites its `main`-side ref.

## Open PRs

| PR | Outcome | Evidence |
| --- | --- | --- |
| #94 `fix(product-mcp-deploy-gate-20260912)` | MERGED 2026-09-12T06:45:26Z | All repo checks green on head `b3d7486`; only third-party CodeFactor failed (advisory, no branch protection). Merged with `--merge`. |
| #95 `cursor/execution-foundation-dda0` | OPEN DRAFT, left unmerged | 29 files, 2251+ additions, new execution surface; `unit`, `lint-type`, `gate`, `coverage`, `security-pr` all failing. Needs-work; author has not undrafted. |

## Pre-triage branches (all superseded, tagged, deleted)

| Branch | Evidence | Tag |
| --- | --- | --- |
| `docs/udo-full-use-runbook` | Content sanitized and landed via #76 as `docs/ops/kater-private-overlay-runbook.md`. Branch tip still carries internal refs (workspace URL, internal tracking ids), so it must never land as-is. | `archive/20260912/udo-full-use-runbook` |
| `land/palette-browser-loading` | PR #79 closed as superseded; behavior on `main` via #75 (`a712396`). Branch tip is an older subset. | `archive/20260912/palette-browser-loading` |
| `palette-browser-loading-feedback-5480200343156298719` | Same behavior as above; branch additionally carries stale CI-timeout changes the 09-06 triage intentionally excluded. | `archive/20260912/palette-browser-loading-feedback` |
| `palette-profile-recovery-14826043716077132865` | Landed via #78; `main` has since moved further (profile-scoped Fabric work). | `archive/20260912/palette-profile-recovery` |

## Recovery snapshots

| Branch | Disposition | Evidence |
| --- | --- | --- |
| `recovery/20260911/connections-plugin-manifests-4e2a0802` | Landed in part | New `src/kater/connections.py`, `src/kater/plugins.py`, `tests/test_connections_plugins.py`, `/api/connections` + `/api/plugins/{id}` routes, integration aliases, CLI command → `land/recovery-connections-plugins-20260912` (`b83f55a`; ruff/mypy clean, 9 tests pass). Stale `fabric_catalog.py` rewrite discarded; `main` (435 lines, #83/#93) supersedes it. |
| `recovery/20260911/repo-971f231f` | Landed | `docs/architecture/dashboard-and-frontend.md` verified accurate against current three-listener architecture → `land/recovery-dashboard-frontend-doc-20260912` (`adac162`). |
| `recovery/20260911/kater-studio-salvage-20260831-6bde8d86` | Archived | Unique commits (asset-drift detection, auth-path rename, studio packaging) trace to #59 (`cf2f10a`) on `main`. |
| `recovery/20260911/pr59-truthful-ui-47f520-468cf03f` | Archived | Brainless renderers, activity surface, OpenAPI studio routes trace to #59 (`cf2f10a`). |
| `recovery/20260911/studio-postmerge-eval-20260901-c226ca19` | Archived | Material-shell refine superseded by #72 (`06b6da2`) and #74 (`7ec8da9`), which removed that code. |

All five tips tagged `archive/20260912/recovery-*` before delete.

## Work preservation

Uncommitted `main` state (`.agents/eval/scorecard.json`,
`.agents/registry/signals.yaml`) preserved on `chore/worktree-20260912`
(`dd230fb`); `main` left tracked-clean before merge work.

## Remaining open items (for the PR tail)

- `land/recovery-connections-plugins-20260912` and
  `land/recovery-dashboard-frontend-doc-20260912` need reviewed PRs with
  exact-head CI before merge.
- DRAFT #95 needs author action; re-triage after it leaves draft.
- `chore/worktree-20260912` needs a PR or cherry-pick decision.
