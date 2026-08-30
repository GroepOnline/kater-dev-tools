# Continual learning

Durable lessons for future sessions on `kater-dev-tools`. Newest first. Keep
entries short and actionable; if a lesson is about agent *behavior*, promote it
into the taste loop (see `.agents/README.md`) instead.

---

## Workflow YAML is guarded by plain-text regression tests

`tests/test_ci_workflow_changes.py` reads the workflow files as **text** and
asserts on exact substrings (pinned SHAs, `runs-on`, comment markers), not by
executing them.

Consequences for any future workflow edit:

- Bumping or SHA-pinning a `uses:` action can break a test even though the YAML
  is valid. Example: PR #49 pinned `actions/checkout` in
  `.github/workflows/release.yml` and broke
  `test_release_workflow_bumps_checkout_action`, which asserted the old mutable
  tag `actions/checkout@v7`.
- The shared SHAs live as constants at the top of
  `tests/test_ci_workflow_changes.py` (`KATER_CHECKOUT_SHA`,
  `GITHUB_SCRIPT_SHA`). Reuse them; every workflow uses the same pins.
- Some tests assert *marker strings* inside comments — e.g.
  `test_ci_runs_full_python_jobs_on_stacked_feature_base_prs` requires
  `GRO-1209`, `INTERIM`, and `production-safe isolation` to stay present in
  `.github/workflows/ci.yml`. Rewriting a comment is fine as long as those
  substrings survive.

**Rule of thumb:** after any `.github/workflows/*.yml` change, grep
`tests/test_ci_workflow_changes.py` for affected substrings and run
`uv run pytest tests/test_ci_workflow_changes.py`.

## Runner model

All public jobs run on `ubuntu-latest`. Older comments referenced self-hosted
`pr-isolated` / `heavy` chef-ci listeners and a "GitHub-hosted runners banned"
policy — that is historical (Actions spending was restored). Only lanes that
need private-fleet access should opt back into self-hosted labels.

## Docs/logs placement

`.agents/` is scoped to the agent-taste registry/eval loop only; `AGENTS.md`
declares `.cursor/` the SSOT for skills and forbids mirrored copies under
`.agents`. Put review notes / session logs under `.reviews/` (this folder), not
under `.agents/`.
