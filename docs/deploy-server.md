# Self-Managed Server Deploy

Run Kater on a machine you control, preferably reachable over Tailscale.

```bash
git clone <repo-url> kater-dev-tools
cd kater-dev-tools
cp .env.example .env
docker compose up -d --build
```

Cursor clients connect to:

```json
{
  "mcpServers": {
    "kater": {
      "type": "sse",
      "url": "http://<tailscale-ip>:9090/sse"
    }
  }
}
```

Do not expose the port publicly unless you add authentication and a threat model.
