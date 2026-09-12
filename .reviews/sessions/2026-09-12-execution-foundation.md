# 2026-09-12 — Execution Foundation

## Goal

Kater as ChefGroep execution/integration gateway: catalog + connections,
generic `execute`, hardening, plane-split docs, GitHub first toolkit.

## Done

- Canonical model: `ToolkitManifest` → `IntegrationManifest` → `ConnectionView` → action
- `PluginManifest` in catalog plugins; secret-free `/api/connections`
- `execute(connection, action, input, identity, policy_context)` with compat
- Hardening: schema, timeout, retries, idempotency, identity, audit, dangerous-write policy
- `kater_pr_*` wrappers over `github.pr.*`
- Docs: `docs/architecture/execution-foundation.md`

## Verify (2026-09-12)

```bash
uv run ruff check . && uv run mypy && uv run pytest --no-cov
```

- ruff: All checks passed
- mypy: Success, 123 source files
- pytest: 1976 passed, 13 skipped in 242s
- `tests/test_execution_foundation.py`: 14 passed (catalog, OAuth ConnectionView, MCP schema, GitHub wrappers, audit/identity, retries, timeout, policy)

## Not this release

Linear → Cloudflare → Slack → … adapter breadth; SDK; auto-release.
