#!/usr/bin/env sh
set -eu

uv run kater --help >/dev/null
uv run kater version >/dev/null
uv run kater doctor --json >/dev/null
uv run kater profiles --json >/dev/null
uv run kater chains --json >/dev/null
uv run kater tools --json >/dev/null
uv run kater config --json >/dev/null
uv run kater adapters --json >/dev/null
uv run kater mcp list --json >/dev/null
uv run kater mcp status github --json >/dev/null
uv run kater chain run research_brief --profile research --json >/dev/null
uv run kater init --force --json >/dev/null
uv run kater enable github --json >/dev/null
uv run kater disable sentry --json >/dev/null
uv run kater deploy --json >/dev/null
uv run kater deploy render docker --json >/dev/null
uv run kater deploy render cloudflare --domain kater.test.com --json >/dev/null
uv run kater auth --json >/dev/null
uv run kater settings --json >/dev/null
uv run kater status --json >/dev/null
uv run kater telemetry --json >/dev/null
uv run kater evals --json >/dev/null
uv run kater telemetry-clear --json >/dev/null
uv run kater tunnel --json >/dev/null
uv run kater tunnel config --provider cloudflare --json >/dev/null

# cleanup
rm -rf .kater

echo "kater smoke ok"
