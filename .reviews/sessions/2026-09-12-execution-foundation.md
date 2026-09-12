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

## Verify

```bash
uv run ruff check . && uv run mypy && uv run pytest
```

## Not this release

Linear → Cloudflare → Slack → … adapter breadth; SDK; auto-release.
