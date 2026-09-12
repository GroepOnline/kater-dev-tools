# Continual learning

Durable lessons for future sessions on `kater-dev-tools`. Newest first. Keep
entries short and actionable; if a lesson is about agent *behavior*, promote it
into the taste loop (see `.agents/README.md`) instead.

---

## Execute catalog leaks hide behind list filters

`list_*` can hide private integrations while `get_*(id)` / `:default`
synthesis / `search_tools` still return them. Public-mode tests must
cover detail routes and execute, not only list payloads. Native toolkit
actions need an owner integration; a hardcoded provider fallback lets
any WRITE connection dispatch that toolkit.

## Merge-train docs trip no-org-leak

Do not put the GitHub org slug or `\bUDO\b` in unallowlisted docs.
Link PRs as `#95`, not `github.com/<org>/…`. Unit job inner `timeout`
must stay above the slowest matrix interpreter; 3.13 can hit 480s at
~99% with a growing suite.

## Merge train: #95 supersedes #102; docs/state first

Open PRs op 2026-09-12: merge #103 → #105 → #95, close #102, keep #104
as morning snapshot. #102 and #95 both add `connections.py`/`plugins.py`;
#95 is the foundation model. Do not merge overlapping catalog recoveries
before the execute contract. Plan: `docs/merge-train-20260912.md`.

## Runtime kronkel: Python blijft; geen Redis-MCP-systeem

Kater is execute-plane (catalog, connections, policy, audit), niet een
connection-bus. PRs reviewen tegen `docs/architecture/runtime-kronkel.md`.
Fail: Redis/NATS in het execute-pad, Rust/Zig rewrite zonder gemeten p99,
MCP-als-architectuur, of run-graphs (Commander). Later mag een Rust
execute-worker *naast* Python, contract ongewijzigd.

## Branch lifecycle must never classify `main`/`origin` as would-delete

`git for-each-ref refs/remotes/origin` with `%(refname:short)` yields `origin/main` (normalizes to `main`) and sometimes a bare `origin` remote ref. Unique-count vs `main` is 0, so a naive stale scanner emits `would-delete main`. Skip protected refs (`main`, `master`, `origin`, `HEAD`) in parse/scan/`git_delete_ref`.

## Session Studio contract tests flip when the Python transport lands

`tests/test_studio_frontend_contract.py` asserted “Write transport not bound”. Binding Studio to `/api/contexts/{id}/session` requires updating those assertions (keep `/api/execute`, `Send message`, `setInterval`, `Math.random` forbidden).

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
