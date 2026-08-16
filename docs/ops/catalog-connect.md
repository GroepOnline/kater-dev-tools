# Catalog Connect storage and origin policy

Catalog Connect lets an operator link a provider account (Slack, Microsoft, …)
from the dashboard. This is **not** company-control production-ready token
storage.

## Secret sink (deny-default)

OAuth access and refresh tokens must not be treated as durable company-control
secrets in `cwd/.kater/settings.json`.

| Mode | Persist to local settings.json | Notes |
| --- | --- | --- |
| Local development | Only with `KATER_CONNECT_ALLOW_LOCAL_SETTINGS=1` | File mode `0600`, gitignored. Opt-in required. |
| Public / `KATER_PUBLIC=1` | Never | Even if the local opt-in env is set. |
| `KATER_CONNECT_SECRET_SINK=chefvault` | Never | Reference only. This gateway does **not** write Vault items. |

Company-control materialization stays on the ChefVault broker. See
[chefvault.md](chefvault.md). Do not put tokens in `mcp.json` or git.

The provider callback will not exchange or store tokens when the sink gate
fails. Pending PKCE/state files stay `0600` and are abandoned without a token
request.

## Admin gate

These mutations require `check_admin` (`KATER_ADMIN_KEY` when set; public mode
fails closed if the admin key is unset):

- `POST /api/mcp/servers/{name}/credentials`
- `POST /api/mcp/servers/{name}/oauth/start`
- `DELETE /api/mcp/servers/{name}/connections/{conn_id}`

`GET /api/mcp/servers/{name}/connections` stays authenticated and returns
masked metadata only (ids, labels, timestamps — never token values).

## Public origin

Public Connect redirect and callback destinations use
`KATER_CONNECT_PUBLIC_BASE_URL` (HTTPS, no userinfo). Request `Host` and
`X-Forwarded-Host` are not trusted in public mode.

Local/dev may use `http://127.0.0.1`, `http://localhost`, or `http://[::1]`
(with optional port). Any other Host is rejected.
