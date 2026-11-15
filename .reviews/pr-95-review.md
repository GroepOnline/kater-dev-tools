# PR #95 review — Execution Foundation (strict fix pass)

Lens: `docs/architecture/runtime-kronkel.md` +
`docs/architecture/execution-foundation.md`.
Head before this pass: `b464cd2`. Train: slot 3.

## Verdict

**MERGE after human APPROVE** once CI is green on the new head.
Foundation stays execute-plane. This pass closed the write-path and
catalog-visibility holes that blocked a strict merge.

## CI (pre-fix)

- `no-org-leak`: `docs/merge-train-20260912.md` had an org handle and
  `\bUDO\b` (private data-plane regex). Rewritten to PR numbers only.
- `unit (3.13)`: job `timeout 480s` (exit 124) at ~99%, not an assertion.
  Suite is slower on 3.13 than 3.11/3.12/3.14. Raised to `timeout 600s`.
- `gate`: failed because unit failed.

## Must-fix (landed)

1. **Hidden `:default` leak** — `get_connection_view` / manifests now
   honor `hidden_integration_ids()` before synthesizing a view.
   `GET /api/connections/{id}` for a private source is 404.
2. **Native `github.pr.*` binding** — owner comes from the toolkit
   manifest, not a hardcoded `"github"` fallback. Foreign connections
   cannot dispatch GitHub actions.
3. **GitHub mutation credentials** — `github.pr.merge` requires a
   configured GitHub connection (`source_is_configured` on the PAT env).
   Doctor still uses `AuthBindingKind.NONE`.
4. **Idempotency** — scoped by `principal_id`; pending reservation
   before dispatch; release on failure. Timeout is no longer retryable.
5. **Timeout** — daemon thread + `join`; caller returns at the deadline
   instead of waiting on `ThreadPoolExecutor.shutdown(wait=True)`.
6. **400 mapping** — bad `timeout_seconds` / malformed connection ids
   are 400, not 500.
7. **Plugin coerce** — invalid mappings return `None`.
8. **Catalog** — `profiles` populated; duplicate action ids skipped;
   `configured` derived from binding/source, not hardcoded `True`.
9. **`search_tools`** — skips hidden integrations in public mode.

## Acceptable v0 / out of scope

- Body `identity` remains the local/loopback actor label. REST without
  admin key is loopback-trusted. Not a second auth plane.
- `allow_dangerous` default True; only merge/delete/admin/drop tokens.
- MCP `kater_pr_merge` still uses actor `"mcp"` + `expected_head_sha`.
- No Redis/Rust rewrite. No Commander/Factory/OCX creep.
- Cloud `curl | sh` uv bootstrap left as-is (Cloud install path).

## Verify

```bash
uv run ruff check . && uv run mypy && uv run pytest --no-cov
python3 scripts/no_org_leak.py --base origin/main
```
