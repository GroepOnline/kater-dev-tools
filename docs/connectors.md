# Connectors vs native Kater tools

A new vendor integration normally does not require a new native Kater MCP tool.

The Cursor / ChatGPT / agent session talks to the **Kater gateway**. That
gateway exposes a **stable native tool surface** (today: 17 `kater_*` tools).
GitHub, Linear, Sentry, Cloudflare, ClickHouse, a downstream MCP server, or
any future API sit **behind** that surface as connectors.

```text
Cursor / ChatGPT / Agent
        |
        v
Kater MCP
17 stable native gateway tools
        |
        +--> profiles / policy
        +--> adapter inventory (`kater_adapters`)
        +--> connector registry
        +--> auth bindings (references only)
        +--> capability discovery
        +--> health / doctor
        +--> chains
                 |
                 +--> REST/API connector
                 +--> downstream MCP
                 +--> remote bridge
                 +--> internal adapter
```

`--no-proxy` company-control deploys keep the native count at 17. Downstream
MCP tools are invoked through the connector control plane. They are **not**
registered as extra Cursor MCP servers and **not** added to
`build_native_tools()`.

## Native tools vs connectors

| Surface | What it is | How agents see it |
|---|---|---|
| Native gateway tools | `kater_profiles`, `kater_doctor`, `kater_chains`, `kater_adapters`, `kater_config`, `kater_pr_*`, `kater_browser_*` | First-class MCP tools |
| Connectors | GitHub, Linear, Sentry, Cloudflare, ClickHouse, imported MCP, generic HTTP APIs | Catalog + health via `kater_adapters`; invoke in-process |
| Capability fabric | `kater.capabilities` manifests / Computer guest | Unchanged; not the connector catalog |
| Catalog Connect | OAuth account linking into gitignored settings | Auth *values* for a server; connectors store only refs |

Do not add `kater_github`, `kater_linear`, or `kater_clickhouse` native tools.

## Connector types

| Type | Transport | Example |
|---|---|---|
| `api` | HTTP REST | ClickHouse HTTP, vendor JSON APIs |
| `mcp` | stdio / SSE / streamable HTTP | Official GitHub / Linear / Sentry MCP |
| `bridge` | remote HTTP to an internal bridge | Org-specific MCP bridges |
| `internal` | native Kater handlers | Gateway itself, Computer guest |

Vendor-specific behaviour belongs in endpoint config, auth scheme, capability
lists, transforms, and safety rules. Lifecycle, health, policy, and registry
behaviour stay generic.

## How to add a connector

Preferred lifecycle (register and grant-write are separate actions):

```text
register  →  disabled (default)
          →  validate
          →  bind-auth (reference only)
          →  probe
          →  explicit profile permission (read / write / admin)
          →  enable
```

1. Describe id, display name, type, version, transport, capabilities.
2. Point `auth_binding` at env / settings / ChefVault **names**, never values.
3. Leave status `disabled`. Do not grant `write` or `admin` by default.
4. Validate transport and metadata (no literal secrets in templates).
5. Probe health. Persist catalog metadata; recompute health on every doctor run.
6. Bind the profile (`ops` write, `analysis` read, …) then enable.

Builtin GitHub / Linear / Sentry / Cloudflare rows are **seeded** from
`ToolSource` with `origin=seed`. They keep working. Out-of-scope catalog
entries (GitLab, Upstash, Slack, Postgres, Notion on company-control ops)
seed as `disabled` with `metadata.scope=out_of_scope` and are not doctor
failures.

## Auth references

Connectors store:

- `auth_binding.kind`: `env` | `settings` | `chefvault` | `none`
- `auth_binding.ref`: env var names, settings keys, or vault item names
- `credential_provider`: who materializes the secret (`env`, ChefVault, …)

They do **not** store tokens, passwords, or Authorization header values.
Header/env templates must use `${ENV_NAME}` placeholders.

Existing sinks stay:

- process environment / systemd `EnvironmentFile` (company-control)
- gitignored `.kater/settings.json` via Catalog Connect (`docs/ops/catalog-connect.md`)
- ChefVault materialization into env (`docs/ops/chefvault.md`)

Rotation: change the secret behind the same ref. Do not recreate the connector.

Doctor, logs, and `as_dict()` redact Bearer tokens and keys whose names look
like secrets. Missing required auth **fails closed**.

## Profile permissions

Connector existence is not access.

| Level | Meaning |
|---|---|
| `disabled` | Invisible for invoke; doctor may report `policy_blocked` or `disabled` |
| `read` | Non-mutating capabilities |
| `write` | Mutating capabilities (`*.write`, `*.create`, …) |
| `admin` | Destructive / admin capabilities |

Enforcement is server-side in `kater.connectors.policy`. Example:

```text
ops:       github=write  sentry=read  cloudflare=write
analysis:  github=read   sentry=read  cloudflare=read
```

## Capabilities

Prefer machine-readable ids over labels:

```text
github.repo.read
github.issues.read
github.issues.write
github.pull_requests.read
github.pull_requests.write
sentry.issues.read
sentry.events.read
clickhouse.ping
clickhouse.query
```

Downstream MCP capabilities are discovered from `tools/list` and stored as
`{connector_id}.{tool_name}` with `discovered=true`. Use them for policy,
chain validation, doctor, routing, and agent discovery.

## Health states

`kater_doctor` evaluates connectors generically. Health is **recomputed**, never
blindly persisted.

| State | Meaning |
|---|---|
| `healthy` | Enabled, auth present, probe ok |
| `degraded` | Partial (some capabilities down) |
| `unavailable` | Enabled but unreachable |
| `disabled` | Intentionally off / out of scope — not broken |
| `unsupported` | Runtime cannot host this connector (no Playwright extra, no ClickHouse) |
| `auth_missing` | Enabled but required auth ref unsatisfied |
| `policy_blocked` | Profile permission denies the requested action |

Intentionally disabled adapters must not show as `missing_env` warnings.

### Browser lane

Native `kater_browser_*` tools stay in the 17-tool surface. Provider health is
separate:

- `browser_lane_ready` — at least one provider (Playwright / CDP / Steel) works
- `browser_lane_unsupported` — this runtime is not expected to host a browser
  (no extra, no CDP/Steel, company-control uses the ChefGroep browser MCP)
- `browser_lane_unavailable` — a browser was expected and failed

See `docs/browser.md`.

## Chains

Chains may name a connector capability id (`github.pull_requests.read`) or a
legacy alias (`github_pr_status`). `pr_health` keeps its public chain id.

Validation runs **before** execution and fails closed when:

- the connector is unavailable or disabled
- the capability is missing
- the profile lacks permission
- required authentication is missing

## Downstream MCP import

Discover → register (disabled) → validate → bind-auth → probe → enable (read)
→ invoke via the connector facade. Persistence is SQLite `.kater/kater.db`
(connector rows). Restart reloads the catalog and **recomputes** health.

Do not call `register_proxy_tools()` for imported servers on company-control
`--no-proxy` deploys; that would leak vendor tools into the Cursor session.

## Disable / remove

- `disable` keeps the row, health becomes `disabled`, invoke fails closed
- `remove` deletes the catalog row; auth refs in env/settings/Vault stay put
  (secrets are not owned by the connector record)

## Security assumptions

- No credentials in git, MCP tool dumps, doctor findings, or normal logs
- Templates with literal secrets are rejected at validate time
- New connectors default to disabled / no write
- Untrusted connector metadata is fail-closed
- `auth_binding_ref` rotation does not require dropping the connector
