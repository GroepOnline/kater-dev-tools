# PR #102 review — connections / plugin manifest land

Lens: `docs/architecture/runtime-kronkel.md` +
`docs/merge-train-20260912.md`.
Head: `3d1dccc` (`land/recovery-connections-plugins-20260912`).

## Verdict

**SUPERSEDED-BY-95 / CLOSE.** Recovery subset of the same catalog
surface. Kronkel-pass, but the model loses to #95.

## Diff facts

Adds `src/kater/connections.py` (142), `src/kater/plugins.py` (153),
`GET /api/connections`, `GET /api/plugins/{plugin_id}`, integration
route aliases, `kater connections`, `tests/test_connections_plugins.py`.
No `execute()`.

Overlap with #95 (6 files): `README.md`, `fabric_routes.py`,
`routes.py`, `cli.py`, `connections.py`, `plugins.py`. Both add the last
two; #95’s versions are the foundation model (`ConnectorRecord`,
`IntegrationManifest`, `GET /api/connections/{id}`, `/api/actions`,
`POST /api/execute`).

Unique vs #95 (cherry-pick later, not this merge):

- `GET /api/plugins/{plugin_id}`
- `/api/integrations/{name}/*` aliases
- inventory tests that survive the #95 types

## Kronkel

Plane / secrets / no-bus / no-rewrite / no-Commander / MCP-as-transport:
pass. No new dangerous writes. No second execute-pad.

## Gate

CI green (one-shot). 9 inline bot threads (auth on new handlers,
stored-vs-runtime, plugin-id normalizer). Org-leak in artifact/plugins
fixed on head.

## Out of scope

Do not merge after #95. Do not rebase the whole branch onto #95.
