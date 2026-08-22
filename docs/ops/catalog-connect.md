# Catalog Connect storage and origin policy

Catalog Connect lets an operator link a provider account (Slack, Microsoft, …)
from the dashboard. This is **not** company-control production-ready token
storage.

## Secret sink

Dashboard-saved credentials and OAuth tokens persist to the gitignored
`cwd/.kater/settings.json`, written `0600` with a `0700` directory. Values are
masked in every API response.

| Mode | Persist to local settings.json | Notes |
| --- | --- | --- |
| Local development | Yes | File mode `0600`, gitignored. |
| Public / `KATER_PUBLIC=1` | Yes | Admin gate applies; file stays `0600`. |

Company-control teams that need a durable shared broker stay on ChefVault.
See [chefvault.md](chefvault.md). Do not put tokens in `mcp.json` or git.

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
