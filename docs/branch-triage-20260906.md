# Branch triage — 2026-09-06

This record summarizes the read-only triage of 21 unmerged remote branches against the then-current `main`. The purpose was to recover still-useful public OSS changes while preserving superseded history without replaying stale implementation branches.

## Decision model

- **Land**: behavior is still missing from `main`, remains compatible with the current public contract, and has a bounded verification surface.
- **Archive**: behavior is already on `main`, superseded by later architecture, would regress dependency or CI policy, or is clearly a prototype/backup.
- Original remote branches are not force-pushed or deleted as part of triage.
- Archive tags preserve the original branch tips before later cleanup.

## Result

| Class | Count | Result |
| --- | ---: | --- |
| Land | 3 | One public operations runbook recovery and two dashboard recovery/feedback fixes |
| Archive | 18 | Preserved by archive tag; no code replayed |
| Total | 21 | Complete triage set |

The three land candidates were opened as PRs #76, #78, and #79. This triage note is PR #77.
An earlier closed documentation PR (#55) did not merge; its sanitized public runbook
recovery landed instead as #76.

## Land candidates

### Public private-overlay operations runbook

A previously closed documentation change contained a useful general pattern for loading a separately managed private domain extension through the public Kater gateway. Before landing, the document must stay generic and must not expose private repository names, internal tracking identifiers, credentials, or private data-plane details.

Verification: documentation-only plus the repository's leak guard and normal CI.

### Dashboard profile recovery

Empty Server Map, Catalog, and Fabric views gain an accessible action that returns an operator from a non-core profile to the core profile. Fabric also surfaces capability-load errors rather than presenting an unexplained empty state.

Verification: lint, type checking, and focused dashboard tests.

### Browser loading feedback

Browser Go, Reload, and Close actions expose loading state, Enter routes through the same navigation path, and overlapping navigations are dropped by an in-flight guard. Stale CI timeout changes from the source branch are intentionally excluded.

Verification: lint, type checking, and focused dashboard tests.

## Archive rationale

The original decision grouped 18 branches for archival preservation:

- Large historical feature dumps whose behavior already exists on `main`.
- Old dependency pins that would regress current dependency floors.
- Earlier variants that are strict subsets of one of the land candidates.
- Merge-gate fixes already present in the current implementation.
- Named prototypes, rescue branches, and backups.
- Superseded CI or integration experiments that no longer match the public repository boundary.

Archive tags retain exact tips. The triage deliberately does not copy private names, internal identifiers, operator infrastructure, or organization-specific integration details into this public report.

## Follow-up verification — 2026-09-06

The follow-up compared remote branches and 16 additional local-only branches
against `main` at `771985bb88361d50cc4a0647da565ad60fbbafa0`.

- The profile recovery and public operations documentation landed through #78
  and #76. Browser loading feedback, Enter routing and the navigation guard
  also reached `main` through #75 (`a712396`), including behavioral tests.
  PR #79 was closed as superseded, retaining its source branch. The newer
  profile-scoped Fabric request on `main` must not be overwritten with old code.
- All 16 inspected local-only branches were integrated or superseded; squash
  history explains why their original tips are not necessarily ancestors of
  `main`. This is content verification, not authorization to delete worktrees.
- Archival preservation is **not** proof that every change is obsolete. The
  `rescue/pr-159-backup` branch still contains a missing restore-safety fix:
  validate the staged database before swapping live state. This is being
  recovered separately with regression coverage; its unrelated CSP, timeout,
  and custom-database-path changes are not replayed wholesale.
- The old eval-output formatting-helper refactor is also absent, but is an
  optional refactor rather than missing runtime functionality. It remains
  preserved without reopening the old CLI snapshot.

The archive count above records the original disposition, not 18 proofs of
complete semantic equivalence. Recovery work still needs exact-head CI and
independent approval; this follow-up does not claim that recovery has landed.

## Status refresh — 2026-09-07

After merging current `main` (`771985bb88361d50cc4a0647da565ad60fbbafa0`) into
this branch, the land-PR disposition is:

| PR | Outcome | Notes |
| --- | --- | --- |
| #76 | Merged | Public private-overlay gateway operations runbook |
| #78 | Merged | Dashboard profile recovery |
| #79 | Closed (superseded) | Browser loading feedback already on `main` via #75 (`a712396`) |
| #55 | Closed (unmerged) | Superseded by the sanitized public runbook in #76 |
| #77 | Open | This documentation record |

Remaining open pull requests at this refresh (excluding dependency bots unless
listed): #82 (backup restore validation), #83 (capability catalog), #84 and #85
(dependency updates), #86 (auto-merge policy), and this #77.

The restore-safety recovery called out above is tracked separately as #82.

## Merge order

1. ~~Land the two independent dashboard fixes one at a time, rebasing the second if `main` moves.~~ Done: profile recovery via #78; browser loading was already on `main` via #75, so #79 closed as superseded.
2. ~~Land the sanitized public runbook once the leak guard and CI are green.~~ Done via #76 (superseding the earlier closed #55 attempt).
3. Land this documentation record after the resulting `main` state is stable.
4. Remote branch deletion, if desired later, is a separate cleanup action and should happen only after confirming the archive tags exist.

## Verification requirements

For each land PR:

- exact-head CI must be green;
- the public leak guard must be green;
- required independent review must apply to the exact head being merged;
- no unrelated scorecard or CI-timeout rebase noise is carried forward.

This record is descriptive only; it does not claim that an archived branch was deployed or that a land PR changed a runtime until its merge and deployment evidence exists.
