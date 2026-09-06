# 2026-09-06 session-event-transport

## Done

- Python session/event transport keyed by `remote_contexts` (migration v10).
- REST `/api/contexts/{id}/session/*`, MCP `kater_session_*` (24 native tools), OpenAPI.
- Studio composer/poll bound after Python tests: no `/api/execute`, no `setInterval`.
- Dashboard: profile recovery + browser `aria-busy` labels.
- Branch lifecycle dry-run scanner with tombstones; protected refs (`main`/`origin`) never `would-delete`.
- Product PR: https://github.com/GroepOnline/kater-dev-tools/pull/75

## Verify

```bash
uv run ruff check . && uv run mypy && uv run pytest
# 1573 passed, 13 skipped
./scripts/e2e-mcp.sh  # server up; 24 MCP tools
uv run python -m kater.branch_lifecycle --dry-run
```

Live `:9091` continue → submit (`waiting`/`handoff`) → unknown event stays `event.unknown` → cancel.

## Follow-ups

- Unique remote patches stay; scanner does not auto-delete them.
- `docs/udo-full-use-runbook` remains parked.
- Cloud `environment.json` still does not install `uv` (install-user failed 127 in this VM).
