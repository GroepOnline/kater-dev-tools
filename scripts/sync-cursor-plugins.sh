#!/usr/bin/env bash
# Bootstrap Cursor agent CLI plugins from committed marketplace SSOT.
#
# SSOT: .cursor/settings.json (extraKnownMarketplaces + enabledPlugins)
#
# Usage:
#   scripts/sync-cursor-plugins.sh            # install / update
#   scripts/sync-cursor-plugins.sh --check    # validate SSOT only
#   scripts/sync-cursor-plugins.sh --dry-run    # planned actions
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_DIR}"

if ! command -v git >/dev/null 2>&1; then
  printf '[sync-cursor-plugins] ERROR: git is required\n' >&2
  exit 1
fi

python3 scripts/sync_cursor_plugins.py "$@"