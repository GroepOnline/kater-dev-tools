# Self-Managed Server Deploy

Run Kater on a machine you control. **Always enable auth before public exposure.**

For the ChefGroep always-on runtime target (`bc-scan-arm`), prefer the system
service packaging in `docs/ops/bc-scan-arm-runtime.md` and
`scripts/systemd/kater-system.service.example` (dedicated `kater` user, `/opt/kater`,
ChefVault fail-closed bootstrap). Keep this page for generic self-managed deploys.

## Quick start (Tailscale / private network)

```bash
mkdir -p ~/OrgChefgroep
git clone https://github.com/GroepOnline/kater-dev-tools.git ~/OrgChefgroep/kater-dev-tools
cd ~/OrgChefgroep/kater-dev-tools
cp .env.example .env
docker compose up -d --build
```

The compose file publishes ports with public-deploy defaults: OAuth auth,
rate-limit 60/min, and non-wildcard CORS. Set `KATER_CORS_ORIGINS` to the real
dashboard/API origin before exposing it outside localhost.

Cursor MCP snippet (private network):

```json
{
  "mcpServers": {
    "kater": {
      "type": "sse",
      "url": "http://<your-host>:9090/sse"
    }
  }
}
```

## Private extensions (optional)

Load org-specific profiles and native tools from a separate Python package:

```bash
export KATER_EXTENSIONS_MODULE=your_package.extensions
```

The module may export `TOOL_SOURCES`, `PRIVATE_PROFILES`, `NATIVE_TOOLS`, and
`CHAINS`. See `src/kater/extensions.py`.

## Secured public deploy (Cloudflare Tunnel)

Generic gateway deployment with its built-in OAuth authority. For the ChefGroep
ChatGPT integration, use the dedicated product transport described below:

```bash
cloudflared tunnel login   # once
cp .env.example .env
# Edit .env:
#   KATER_PUBLIC=1
#   KATER_AUTH_MODE=oauth
#   KATER_RATE_LIMIT=60
#   KATER_CORS_ORIGINS=https://kater.yourdomain.com
#   KATER_ADMIN_KEY=<operator key>
#   KATER_CONNECT_PUBLIC_BASE_URL=https://kater.yourdomain.com
# Catalog Connect persists dashboard saves to gitignored .kater/settings.json
# (docs/ops/catalog-connect.md).

./scripts/deploy-cloudflare.sh kater.yourdomain.com kater
```

This generic deployment serves private MCP clients at
`https://kater.yourdomain.com/sse`. It is separate from the ChefGroep product OAuth
contract at `/mcp`.

## API key auth (Cursor / agents over HTTPS)

```bash
export KATER_PUBLIC=1
export KATER_AUTH_MODE=apikey
export KATER_API_KEY="$(openssl rand -hex 24)"
export KATER_ADMIN_KEY="$(openssl rand -hex 24)"
export KATER_CORS_ORIGINS=https://kater.yourdomain.com
export KATER_RATE_LIMIT=60
uv run kater serve
```

Add to Cursor MCP config:

```json
{
  "mcpServers": {
    "kater": {
      "type": "sse",
      "url": "https://kater.yourdomain.com/sse",
      "headers": {
        "Authorization": "Bearer YOUR_KATER_API_KEY"
      }
    }
  }
}
```

## Ports

One `kater serve` process opens three core listeners plus an opt-in product
listener, each overridable via its own environment variable:

| Port | Env var | Role |
|------|---------|------|
| 9090 | `KATER_MCP_PORT` | MCP SSE (`/sse`) |
| 9091 | `KATER_API_PORT` | REST API + dashboard |
| 9092 | `KATER_WS_PORT` | WebSocket telemetry |
| 9093 | `KATER_PRODUCT_MCP_PORT` | Opt-in product Streamable HTTP (`/mcp`) |

Persist SQLite and secrets under `.kater/` (Docker/K8s: mount a volume at `/app/.kater`).

## Schema migrate and backups

Stop the server before write-heavy CLI against the same DB file:

```bash
uv run kater migrate apply
uv run kater backup create
```

## Optional native browser lane

Gateway, MCP proxy, and dashboard work without Playwright. For local browser sessions:

```bash
uv sync --extra browser
uv run playwright install chromium
```

Configure via `KATER_BROWSER_*` in `.env` (see `.env.example`). Containers that need the
browser extra must also provide Playwright's Linux system dependencies: either run
`uv run playwright install --with-deps chromium` in the image (installs the OS libraries
Chromium needs, not just the browser binary) or base the image on a pinned Playwright-matched
image. CDP/remote providers avoid shipping a browser.

## Pre-flight check

```bash
KATER_PUBLIC=1 KATER_AUTH_MODE=oauth uv run kater doctor
```

Doctor flags missing auth, open CORS, and disabled rate limits on public deployments.

Public dynamic OAuth registration is disabled by default. Enable it only for a
controlled bootstrap flow:

```bash
export KATER_ALLOW_DYNAMIC_REGISTRATION=1
export KATER_REGISTRATION_TOKEN="$(openssl rand -hex 24)"
```

See [SECURITY.md](../SECURITY.md) for the full threat model.

## Dedicated ChefGroep product transport

The opt-in product listener serves only the fixed ChefGroep product tool registry.
It does not import native or proxy tools, and leaves private MCP on port 9090.
Configure these variables on the **service process** (systemd EnvironmentFile,
GitHub Environment/secret authority, or the Compose `.env`):

```dotenv
KATER_RESOURCE_AUTH_ENABLED=1
KATER_RESOURCE_AUTH_ISSUER=https://auth.chefgroep.online
KATER_RESOURCE_AUTH_RESOURCE=https://kater.chefgroep.online/mcp
KATER_RESOURCE_AUTH_SCOPES=kater:read brain:read chefshare:read
KATER_RESOURCE_AUTH_SERVICE_KEY_ENV=KATER_RESOURCE_AUTH_SERVICE_KEY
KATER_PRODUCT_MCP_PORT=9093
```

Provision `KATER_RESOURCE_AUTH_SERVICE_KEY` through the secret authority. The
configured name is safe to persist; the key itself must never be committed. Env
contract values override persisted settings. Malformed contracts, missing keys
and port collisions fail startup. An unset enable flag keeps the listener off.

Route only these machine paths to port 9093, preserving the public Host header:

| Public path | Origin |
| --- | --- |
| `/mcp` | `http://127.0.0.1:9093/mcp` |
| `/.well-known/oauth-protected-resource/mcp` | `http://127.0.0.1:9093/.well-known/oauth-protected-resource/mcp` |

Those two paths must reach Kater without an interactive Cloudflare Access login;
the product listener validates OAuth bearer tokens itself. Keep existing Access
protection and routing on all other paths. The generic Cloudflare generator is
for the private gateway and does not install these product routes. Compose binds
its optional product port to host loopback so a local tunnel can reach it.

The exact resource/audience is `https://kater.chefgroep.online/mcp`, with issuer
`https://auth.chefgroep.online`. Auth owns ChatGPT client metadata, callbacks,
PKCE and consent. Kater neither registers clients nor issues tokens. Every MCP
request is remotely introspected; there is no positive token cache. Invalid or
revoked tokens return HTTP 401 with resource metadata, Auth failures return 503,
and a valid token missing a tool scope returns an MCP auth challenge. Tools/list
mirrors OAuth security schemes at top level and under `_meta` for ChatGPT.

`GET /health/ready` checks the enabled listener's exact discovery metadata,
unauthenticated bearer rejection and Auth introspection using a deliberately
invalid probe token. Failure returns 503. It does not validate a real user's
consent or a backend adapter. The deployment script checks this readiness before
disarming rollback; `/health/live` remains API process liveness. Production
release evidence must additionally prove the public HTTPS paths and a real
consent/call/revoke sequence. The product registry's unimplemented backend tools
continue returning explicit unavailable errors until their owning adapters land.
