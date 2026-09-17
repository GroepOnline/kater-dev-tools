# Local development (one path)

## Quick boot

```bash
cp .env.example .env          # skipped when you use ./scripts/dev-boot.sh
./scripts/dev-boot.sh         # docker compose dev stack (default)
./scripts/dev-health.sh       # /health, /health/live, /health/ready
```

Native loopback (no Docker): `./scripts/dev-boot.sh native` (runs `uv sync` + `kater serve`).

VS Code / Cursor **Dev Containers**: open `.devcontainer/devcontainer.json` (uses
`docker-compose.yml` + `docker-compose.dev.yml`).

ChefGroep Auth (mesh `:9000` vs Cloudflare Access): [ops/auth-mesh-vs-cf-access.md](ops/auth-mesh-vs-cf-access.md).
OIDC client placeholders (no secrets): [../config/oidc/README.md](../config/oidc/README.md).

## Local Docker Deploy (public-shaped compose)

The default `docker-compose.yml` mirrors a public deploy (`KATER_PUBLIC=1`,
`KATER_AUTH_MODE=oauth`). For everyday local work, prefer the dev override:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

`kater serve` listens on three ports by default:

| Port | Role |
|------|------|
| 9090 | MCP SSE (`/sse`) |
| 9091 | REST API + dashboard |
| 9092 | WebSocket telemetry |

Health checks:

```bash
curl -fsS http://127.0.0.1:9091/health
curl -fsS http://127.0.0.1:9091/health/ready
# or: ./scripts/dev-health.sh
```

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
