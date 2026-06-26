# Self-Managed Server Deploy

Run Kater on a machine you control. **Always enable auth before public exposure.**

## Quick start (Tailscale / private network)

```bash
git clone https://github.com/OnlineChefGroep/kater-dev-tools.git
cd kater-dev-tools
cp .env.example .env
docker compose up -d --build
```

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

## Secured public deploy (Cloudflare Tunnel)

Recommended for ChatGPT Remote MCP (OAuth + PKCE built in):

```bash
cloudflared tunnel login   # once
cp .env.example .env
# Edit .env:
#   KATER_PUBLIC=1
#   KATER_AUTH_MODE=oauth
#   KATER_RATE_LIMIT=60

./scripts/deploy-cloudflare.sh kater.yourdomain.com kater
```

ChatGPT → Settings → MCP → `https://kater.yourdomain.com/sse`

## API key auth (Cursor / agents over HTTPS)

```bash
export KATER_PUBLIC=1
export KATER_AUTH_MODE=apikey
export KATER_API_KEY="$(openssl rand -hex 24)"
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

## Pre-flight check

```bash
KATER_PUBLIC=1 KATER_AUTH_MODE=oauth uv run kater doctor
```

Doctor flags missing auth, open CORS, and disabled rate limits on public deployments.

See [SECURITY.md](../SECURITY.md) for the full threat model.
