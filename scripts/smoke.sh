#!/usr/bin/env sh
set -eu

uv run kater --help >/dev/null
uv run kater doctor --json >/dev/null
uv run kater profiles --json >/dev/null

echo "kater smoke ok"
