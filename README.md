# Kater Dev Tools

Kater is a developer-only MCP gateway for code agents. It keeps agent context small
by exposing one curated MCP endpoint and turning broad dev MCPs on only through
explicit profiles.

This is not an end-user product runtime. Run it locally or on a self-managed server
over Tailscale/SSH.

## Quick Start

```bash
uv sync
uv run kater doctor --json
uv run kater profiles --json
uv run kater mcp serve
```

Docker:

```bash
docker compose up --build
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

## Profiles

- `core`: Kater-native diagnostics, profile listing, doctor, and fix-plan tools.
- `code`: source-control and local code workflow adapters.
- `ops`: GitHub, Linear, Sentry, and infrastructure tools.
- `research`: Exa, Firecrawl, and Hugging Face.
- `web`: browser automation and scraping.
- `content`: Sanity and publishing-related tools.
- `email`: Resend.
- `image`: Quiver and image-generation tools.
- `utrecht`: optional Utrecht Data OS adapter.

Default profile is intentionally small. Add profiles only for the task at hand.
