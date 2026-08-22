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

Recommended for ChatGPT Remote MCP (OAuth + PKCE built in):

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

ChatGPT → Settings → MCP → `https://kater.yourdomain.com/sse`

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

One `kater serve` process opens three listeners, each overridable via its own
environment variable:

| Port | Env var | Role |
|------|---------|------|
| 9090 | `KATER_MCP_PORT` | MCP SSE (`/sse`) |
| 9091 | `KATER_API_PORT` | REST API + dashboard |
| 9092 | `KATER_WS_PORT` | WebSocket telemetry |

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
