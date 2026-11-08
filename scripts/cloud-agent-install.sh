#!/usr/bin/env bash
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

chmod +x .cursor/hooks/fetch-cursor-artifacts.sh \
  scripts/check_cursor_artifacts.sh \
  scripts/sync-chefgroep-skills.sh \
  2>/dev/null || true

uv sync --dev
./scripts/sync-chefgroep-skills.sh
.cursor/hooks/fetch-cursor-artifacts.sh --write-cache
if [ -f scripts/generate_cursor_index.py ]; then
  uv run python scripts/generate_cursor_index.py
fi
