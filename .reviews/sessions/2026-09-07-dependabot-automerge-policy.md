# Dependabot auto-merge repository policy repair

## Scope and observed cause

- Branch: `fix/dependabot-automerge-policy-20260907`.
- Base: `771985bb88361d50cc4a0647da565ad60fbbafa0` from freshly fetched `origin/main`.
- Failed run `34083094250`: `Auto merge is not allowed for this repository`.
- Read-only repository API confirmed `allow_auto_merge=false` on 2026-09-07.
- Main's untracked documentation and all existing worktrees were preserved.

## Change

The existing enable-auto-merge step reads repository metadata before GraphQL.
An explicit false setting produces a notice and returns without mutation.
An explicit true setting retains the existing squash auto-merge operation.
Missing/malformed metadata and API errors fail the step instead of being hidden
as policy skips. No new token permissions, repository settings, approvals,
merge behavior, action pins, runner routing, or deployment changes.

The separate approval step remains unchanged. The repair does not claim that
GitHub auto-merge or approvals satisfy any independent repository landing gate.

## Verification

- `uv run ruff check .`: passed.
- `uv run mypy`: passed, 114 source files.
- `uv run pytest --no-cov tests/test_automerge_repository_policy.py tests/test_ci_workflow_changes.py`:
  27 passed (11 executable policy regressions and 16 existing workflow tests).
- `git diff --check`: passed.
- Tests parse the real workflow and execute its JavaScript in Node with mocked
  GitHub APIs; no live mutation, backend, service, SQL, or migration is invoked.
- Full application suite not run: this is a workflow-only change; affected
  workflow tests plus repository lint/typecheck are the bounded verification.

## Handoff

Local commit only. Parent owns independent review, push, PR creation and fresh
exact-head CI. No push, PR helper, approval, merge, or deployment was performed
by this worker. `tests/test_ci_workflow_changes.py` remains unmodified.
