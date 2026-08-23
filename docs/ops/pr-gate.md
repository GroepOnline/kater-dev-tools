# PR-gate GitHub transport

Operator notes for `kater_pr_*` (MCP, REST `/api/pr/*`, and `kater pr`).

## Root cause

`gh pr view --json` is GraphQL. A single unbounded `subprocess.run` with no
timeout or retry turned `api.github.com/graphql` dial timeouts into raw MCP
errors. Protection lookup treated every `RuntimeError` as "unprotected".
Read-gate `expected_head_sha` mismatch was informational only.

## Behavior

| Path | Transport | Retry |
| --- | --- | --- |
| PR body / list when `KATER_PR_REPO` is set | REST `gh api` | Transient only |
| PR body / list without a pinned repo | `gh pr view` / `gh pr list` (GraphQL CLI) | Transient only |
| `reviewThreads` | GraphQL only | Transient only; fail-closed |
| `gh pr merge` | CLI write | **Never** |

GraphQL extras never infer `open_threads=0` on transport failure.

## Retry budget

Defaults (env-overridable, clamped):

- `KATER_GH_TIMEOUT_SEC=12` per subprocess
- `KATER_GH_RETRY_ATTEMPTS=2` extra read attempts (3 total)
- Backoff `0.2s`, `0.4s` plus jitter (`KATER_GH_BACKOFF_SEC`)
- `KATER_GH_RETRY_BUDGET_SEC=40` overall wall clock

Transient: dial/i/o timeout, TLS handshake timeout, reset/EOF, HTTP 429/5xx,
`subprocess.TimeoutExpired`. Permanent: 401/403/404, `Unknown JSON field`,
GraphQL `errors[]`, merge conflicts. Writes do not retry.

## Fail-closed guarantees

- No PASS cache. Audit trail stays append-only.
- Protection: only HTTP 404 means unprotected. Timeout/429/5xx become
  `REQUIRED_CHECK_LOOKUP` (BLOCK), never `base_protected=False`.
- Nonempty `expected_head_sha` mismatch BLOCKs the read gate (`HEAD_STALE`).
  Merge still pins `--match-head-commit` to that SHA.
- Merge timeout: bounded read. Success only if `merged=true` **and** the
  original pin is still the PR head. Otherwise fail closed.
- MCP/API/CLI errors are structured and redacted. Doctor may show token env
  precedence and `sha256[:12]` fingerprint — never the token.

## Live deploy (after merge; not this PR)

1. Merge this change to this repository's `main`.
2. Pull the exact SHA on the company-control host Kater checkout.
3. Restart the Kater shadow service unit.
4. Prove `/health` and one `kater_pr_gate` against a real PR in this repository.
5. Stamp inventory `desired_sha` / `deployed_sha`.
6. Confirm the control host can reach `api.github.com:443`. Retries do not fix a DROP.
