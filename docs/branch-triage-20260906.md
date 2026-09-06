# Branch triage — 2026-09-06

Unmerged remote branches vs `origin/main` (`7ec8da9`). Zero open PRs at
triage time. Counts are `git rev-list --left-right --count origin/main...origin/<branch>`
(behind / ahead). “Already on main” means the unique behavior exists on
`origin/main` even when `git cherry` still shows `+` (rewritten commits).

Closed PRs (one `chef-gh pr list --state all --head <branch>` per branch):
only `#55` (`docs/udo-full-use-runbook`, closed, content not on main) and
`#58` (`feat/scaffold-project-core-integration-types`, closed).

Classes:

- **A** — still valuable, small conflict → land
- **B** — valuable, heavy conflict/large → land with rebase
- **C** — superseded / already on main / empty / prototype / backup → archive tag, do not delete the branch
- **D** — dependency bump → land if tests pass (none this round; the two dep branches would regress)

Land PRs use new `land/<short>` branches. Original remotes are never force-pushed.

## Summary table

| Branch | behind/ahead | last commit | author | files (three-dot) | cherry +/- | class | outcome |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `autoresearch/kater-mcp-85pct-20260828` | 27/4 | 2026-08-29 | chefadmin-netizen | 5 (`.auto/*`, `.gitignore`) | 4/0 | C | discarded experiment; archive `archive/autoresearch/kater-mcp-85pct-20260828-5f3b004-20260906` |
| `chore/pin-mcp-lt-2` | 125/1 | 2026-07-30 | Chef Admin | 3 | 1/0 | C | main is `mcp>=2.1.1`; pin `<2` would regress; archive `archive/chore/pin-mcp-lt-2-d0322a3-20260906` |
| `codesmith/pr180-lint-fix` | 118/66 | 2026-07-30 | OnlineChef | 86 (~18k ins) | 64/0 | C | browser/control-plane dump already on main; archive `archive/codesmith/pr180-lint-fix-7d23212-20260906` |
| `cursor/kater-browser-lane-ui-overhaul-1100` | 127/45 | 2026-07-27 | OnlineChef | 80 (~15k ins) | 45/0 | C | same superseded dump; archive `archive/cursor/kater-browser-lane-ui-overhaul-1100-0a953a4-20260906` |
| `dependabot/uv/python-minor-patch-f7e4b35877` | 75/1 | 2026-08-03 | dependabot[bot] | 2 | 1/0 | C | branch `ruff>=0.16.1`, main `ruff>=0.16.5`; archive `archive/dependabot/uv/python-minor-patch-f7e4b35877-e73a41a-20260906` |
| `devin/fork-gate-and-control-plane-upgrade` | 118/63 | 2026-07-30 | OnlineChef | 86 (~18k ins) | 61/0 | C | same superseded dump; archive `archive/devin/fork-gate-and-control-plane-upgrade-2027816-20260906` |
| `docs/udo-full-use-runbook` | 20/1 | 2026-08-29 | Joep | 1 | 1/0 | A | unique ops doc (CHE-649); closed PR #55 never merged; [PR #76](https://github.com/GroepOnline/kater-dev-tools/pull/76) |
| `feat/chefvault-integration` | 127/12 | 2026-07-27 | OnlineChef | 7 | 11/1 | C | `chefvault_extension.py`, docs, wrapper, tests already on main; archive `archive/feat/chefvault-integration-759d13c-20260906` |
| `feat/scaffold-project-core-integration-types` | 15/2 | 2026-08-31 | chefadmin-netizen | 272 (−63k Python) | 2/0 | C | closed PR #58; would delete the Python gateway; archive `archive/feat/scaffold-project-core-integration-types-c70699d-20260906` |
| `fix/browser-cgnat-egress` | 117/9 | 2026-07-30 | OnlineChef | 2 | 9/0 | C | `100.64.0.0/10` + `tests/test_browser_cgnat_policy.py` on main; archive `archive/fix/browser-cgnat-egress-2f4b311-20260906` |
| `fix/dependabot-private-acceptance` | 131/4 | 2026-07-26 | OnlineChef | 2 | 4/0 | C | policy tests on main; old CI asserted a UDO deploy-key checkout we do not re-land; archive `archive/fix/dependabot-private-acceptance-0dea6e5-20260906` |
| `fix/pr-gate-gh-json-fields` | 131/2 | 2026-07-26 | Chef Admin | 2 | 2/0 | C | fail-closed `hasNextPage` without `endCursor` is already in `src/kater/pr_control.py` on main; archive `archive/fix/pr-gate-gh-json-fields-332dc48-20260906` |
| `fix/pr-gate-gh-reviewthreads` | 132/4 | 2026-07-25 | OnlineChef | 2 | 3/0 | C | GraphQL extras, pagination, fail-closed null connection already on main; archive `archive/fix/pr-gate-gh-reviewthreads-84c37e8-20260906` |
| `jules-15172571045138015352-c5bfdfd3` | 158/4 | 2026-07-21 | Chef Admin | 1 | 4/0 | C | sidebar `role=tablist` + roving tabindex already in `dashboard.py`; archive `archive/jules-15172571045138015352-c5bfdfd3-e7743e0-20260906` |
| `jules-15640634542643590975-b271e696` | 132/2 | 2026-07-25 | Chef Admin | 3 | 2/0 | C | `credInputId()` unique label pairing already on main; archive `archive/jules-15640634542643590975-b271e696-312926c-20260906` |
| `jules-4802806421746281431-c2509d83` | 75/4 | 2026-08-02 | google-labs-jules[bot] | 3 | 4/0 | C | subset of palette profile-recovery (“Switch profile to core”); land that sibling instead; archive `archive/jules-4802806421746281431-c2509d83-457e8e0-20260906` |
| `palette-browser-loading-feedback-5480200343156298719` | 99/9 | 2026-08-01 | Chef Admin | 6 | 9/0 | A/B | unique browser Go/Reload/Close `aria-busy` + in-flight guard; dropped stale unit-timeout CI hunks (preserve main); [PR #79](https://github.com/GroepOnline/kater-dev-tools/pull/79) |
| `palette-profile-recovery-14826043716077132865` | 75/3 | 2026-08-03 | Chef Admin | 4 | 3/0 | A | unique empty-view “Switch profile to core” + Fabric error empty state; scorecard conflict kept main; [PR #78](https://github.com/GroepOnline/kater-dev-tools/pull/78) |
| `prototype/pr-159-control-room` | 127/25 | 2026-07-27 | OnlineChef | 66 | 24/0 | C | named prototype + superseded feature dump; archive `archive/prototype/pr-159-control-room-8fce061-20260906` |
| `refactor-evals-command-5192974902319060233` | 230/3 | 2026-07-21 | google-labs-jules[bot] | 2 | 1/2 | C | `evals` command already on main; cherry says two patches equivalent; archive `archive/refactor-evals-command-5192974902319060233-0a06ce3-20260906` |
| `rescue/pr-159-backup` | 110/8 | 2026-07-30 | Cursor Agent | 7 | 6/0 | C | named backup of PR 159; archive `archive/rescue/pr-159-backup-8d8b9de-20260906` |

## Priority note — `fix/pr-gate-*`

These were the highest-priority live merge-gate fixes. They are **already on
main** (`GitHubPRClient._graphql_extras`, pagination, fail-closed missing
`reviewThreads`, fail-closed `hasNextPage` without `endCursor`). Rebasing the
July tips would only fight 130+ later commits that already contain the
behavior. Archived, not re-landed.

## What landed

| Land branch | Origin | PR | Local verify |
| --- | --- | --- | --- |
| `land/udo-full-use-runbook` | `docs/udo-full-use-runbook` | [#76](https://github.com/GroepOnline/kater-dev-tools/pull/76) | `uv run ruff check . && uv run mypy && uv run pytest` — 1520 passed, 6 skipped |
| `land/palette-profile-recovery` | `palette-profile-recovery-14826043716077132865` | [#78](https://github.com/GroepOnline/kater-dev-tools/pull/78) | ruff + mypy + `pytest tests/test_dashboard.py` — 56 passed |
| `land/palette-browser-loading` | `palette-browser-loading-feedback-5480200343156298719` | [#79](https://github.com/GroepOnline/kater-dev-tools/pull/79) | ruff + mypy + `pytest tests/test_dashboard.py` — 60 passed |
| `docs/branch-triage-20260906` | (new from `origin/main`) | [#77](https://github.com/GroepOnline/kater-dev-tools/pull/77) | docs-only |

Incidental rebase noise dropped (main wins): `.agents/eval/scorecard.json`,
unit-job timeout raises in `.github/workflows/ci.yml`, and the matching
`tests/test_ci_workflow_changes.py` timeout assertions.

## Archive tags (push `refs/tags/archive/…`; do not delete branches yet)

Joep can delete the original remotes after the land PRs merge.

```
archive/autoresearch/kater-mcp-85pct-20260828-5f3b004-20260906
archive/chore/pin-mcp-lt-2-d0322a3-20260906
archive/codesmith/pr180-lint-fix-7d23212-20260906
archive/cursor/kater-browser-lane-ui-overhaul-1100-0a953a4-20260906
archive/dependabot/uv/python-minor-patch-f7e4b35877-e73a41a-20260906
archive/devin/fork-gate-and-control-plane-upgrade-2027816-20260906
archive/feat/chefvault-integration-759d13c-20260906
archive/feat/scaffold-project-core-integration-types-c70699d-20260906
archive/fix/browser-cgnat-egress-2f4b311-20260906
archive/fix/dependabot-private-acceptance-0dea6e5-20260906
archive/fix/pr-gate-gh-json-fields-332dc48-20260906
archive/fix/pr-gate-gh-reviewthreads-84c37e8-20260906
archive/jules-15172571045138015352-c5bfdfd3-e7743e0-20260906
archive/jules-15640634542643590975-b271e696-312926c-20260906
archive/jules-4802806421746281431-c2509d83-457e8e0-20260906
archive/prototype/pr-159-control-room-8fce061-20260906
archive/refactor-evals-command-5192974902319060233-0a06ce3-20260906
archive/rescue/pr-159-backup-8d8b9de-20260906
```

## Counts

- Triaged: 21
- Land (A/B/D): 3 (+ this docs PR)
- Archive (C): 18
- Dependency bumps worth landing (D): 0
- PRs opened: 4 (`#76` `#77` `#78` `#79`)
