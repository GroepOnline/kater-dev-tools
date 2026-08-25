# Review Guidelines — Kater Dev Tools

Guidance for reviewing PRs in this repo. Kater is a single `uv`-managed Python
package (3.11–3.14). Standard checks: `uv run ruff check .`, `uv run mypy`,
`uv run pytest`. Line length is 100.

## Critical areas

- **Native tool surface is fixed at 17.** `build_native_tools()`
  (`src/kater/registry.py`) is the only Cursor-facing MCP surface. A new vendor
  integration must **not** add a `kater_<vendor>` native tool. Flag any change
  that grows or shrinks the native count, or registers proxy/vendor tools into
  the Cursor session (especially on `--no-proxy` / company-control deploys).
- **Connectors live behind the 17 tools.** The connector catalog
  (`src/kater/connectors/`) is reached via `kater_adapters`, chains, the
  `kater connector` CLI, and `POST /api/connectors/...` — never as extra native
  tools. Health is **recomputed**, never persisted.
- **Fail closed.** Connector invoke, chain validation
  (`src/kater/connectors/chain_guard.py`), and policy checks
  (`src/kater/connectors/policy.py`) must deny by default: unknown connector,
  missing capability, missing auth, or insufficient profile permission all
  block execution before any side effect.
- **Stateless invocation invariant.** `src/kater/connectors/dispatch.py`
  governs outbound MCP backends. `stateless` (fresh backend per call) is the
  default; `pooled` is an outbound-only optimization that must stay **forced
  off** on public / company-control deploys (`is_public_mode()`), so the surface
  keeps no warm state between calls. Flag any pooling that leaks across the
  native surface or ignores the public-mode override.

## Security

- **No secrets anywhere they can leak.** Connector records store auth *refs*
  (env var / settings key / vault item names), never values. Verify
  `as_dict()`, doctor findings, logs, and HTTP/CLI error output stay redacted
  (`redact_text` / `redact_mapping` in `src/kater/connectors/auth.py`).
- **Templates with literal secrets are rejected at validate time**
  (`src/kater/connectors/models.py`); header/env templates must be `${ENV}`
  placeholders. Unresolved `${VAR}` must never be sent on the wire.
- **Catalog mutations are admin-gated.** `POST /api/connectors/...` routes must
  go through `_catalog_admin_denied` (`src/kater/api/routes.py`). New connectors
  default to `disabled` with no write/admin permission.
- **ClickHouse / SQL mutation gating** must fail closed: only positively
  identified read-only statements bypass the WRITE permission requirement
  (`clickhouse_query_is_mutation` in `src/kater/connectors/api.py`).

## Conventions

- Public Python functions and connector models should carry type hints; keep
  `mypy` clean on `src/kater/connectors/`.
- New connector behaviour belongs in endpoint config, auth scheme, capability
  lists, and safety rules — lifecycle, health, policy, and registry logic stay
  generic per connector *type*, not per vendor.
- Add or update tests under `tests/test_connector_*.py` for any connector
  change; migrations bump `latest_version` and update `tests/test_migrations.py`.

## Ignore

- `.kater/` runtime state (SQLite `kater.db`, `.env`) is never committed.
- Auto-generated `.cursor/INDEX.md` and catalog caches do not need review.
