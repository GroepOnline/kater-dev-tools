# Review — PR #49: ci: use current GitHub-hosted runtime baseline

- **Branch:** `joep12/ci-opt` → `main`
- **Author:** ChefGroep
- **Scope:** move nightly `agent-taste-eval` + `release` jobs to `ubuntu-latest`;
  SHA-pin `actions/checkout` and `astral-sh/setup-uv` in the release workflow.

## What the PR changed

- `.github/workflows/agent-taste-eval.yml` — `runs-on` → `ubuntu-latest`.
- `.github/workflows/release.yml` — `runs-on` → `ubuntu-latest`; pinned
  `actions/checkout` and `astral-sh/setup-uv` to commit SHAs (tag kept as `# v7`
  comment).

## Findings

### 1. CI-breaking regression test (the real bug) — fixed

`test_release_workflow_bumps_checkout_action` in
`tests/test_ci_workflow_changes.py` asserted the mutable tag
`actions/checkout@v7` was present in `.github/workflows/release.yml`. The PR
SHA-pinned that action, so the substring disappeared and the test failed,
turning `unit (3.11/3.12/3.13/3.14)`, `coverage`, and the aggregating `gate`
red.

**Fix:** updated the test to assert the pinned SHA (`KATER_CHECKOUT_SHA # v7`)
and the *absence* of the mutable tag, matching the existing pattern in
`test_no_org_leak_workflow_matches_shared_checkout_sha` and
`test_automerge_uses_github_script_v9` in the same file.

### 2. Stale runner policy comment — fixed

`.github/workflows/ci.yml` still carried a policy comment saying
"GitHub-hosted runners stay banned until Actions spending is restored", while
every job already ran on `ubuntu-latest`. Rewrote it as a HISTORY note that
matches reality, keeping the three strings asserted by
`test_ci_runs_full_python_jobs_on_stacked_feature_base_prs`
(`GRO-1209`, `INTERIM`, `production-safe isolation`).

### 3. Misleading per-job comments — fixed

Removed all `# PR → pr-isolated; else → heavy.` comments above
`runs-on: ubuntu-latest` across `.github/workflows/ci.yml` (11 jobs),
`.github/workflows/no-org-leak.yml`, and `.github/workflows/automerge.yml`.

## Not changed / out of scope

- The runner-policy *decision* itself (CodeRabbit's concern about the
  hosted-runner ban) is a repo-owner call, not a bug — `.github/workflows/ci.yml`
  already used `ubuntu-latest` before this PR, so this only aligns the two
  remaining nightly workflows.
- SHA correctness vs the real upstream `v7` tags of `actions/checkout` /
  `astral-sh/setup-uv` was not verified against the marketplace; only internal
  consistency (same SHA everywhere) was confirmed.

## Verification suggested

```bash
uv run pytest tests/test_ci_workflow_changes.py
```
