# Local Docker Deploy

```bash
cp .env.example .env
docker compose up --build
```

`kater serve` listens on three ports by default:

| Port | Role |
|------|------|
| 9090 | MCP SSE (`/sse`) |
| 9091 | REST API + dashboard |
| 9092 | WebSocket telemetry |

Health check: `curl -s http://127.0.0.1:9091/health`.

Cursor MCP snippet:

```json
{
  "mcpServers": {
    "kater": {
      "type": "sse",
      "url": "http://127.0.0.1:9090/sse"
    }
  }
}
```

Change `KATER_PROFILE` in `.env` when a task needs a broader profile.

## Schema migrate and backups (CLI)

With the server stopped (avoids SQLite concurrent-writer errors):

```bash
uv run kater migrate apply
uv run kater backup create
```

## Optional native browser lane

Not required for the gateway. To enable local Chromium sessions:

```bash
uv sync --extra browser
uv run playwright install chromium
```

See `.env.example` for `KATER_BROWSER_*` knobs (`provider`, domain allow/deny, session limits).
