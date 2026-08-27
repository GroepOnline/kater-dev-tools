#!/usr/bin/env bash
# Pre-commit / CI guard: refresh Cursor artifact cache, optional INDEX check,
# and fail if org handle or production domain appears under .cursor/.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

FETCH="${ROOT}/.cursor/hooks/fetch-cursor-artifacts.sh"

if [[ ! -f "${FETCH}" ]]; then
  echo "check_cursor_artifacts: missing ${FETCH}" >&2
  exit 1
fi

chmod +x "${FETCH}"
"${FETCH}" --write-cache

CACHE="${ROOT}/.cursor/hooks/.state/catalog.md"
HASH="${ROOT}/.cursor/hooks/.state/catalog.sha256"
if [[ ! -s "${CACHE}" || ! -s "${HASH}" ]]; then
  echo "check_cursor_artifacts: catalog cache missing after fetch" >&2
  exit 1
fi

GEN="${ROOT}/scripts/generate_cursor_index.py"
if [[ -f "${GEN}" ]]; then
  # Prefer uv so PyYAML from the project env is available.
  if command -v uv >/dev/null 2>&1; then
    uv run python "${GEN}" --check
  else
    python3 "${GEN}" --check
  fi
fi

SOURCE_SKILL="${ROOT}/.cursor/skills/pr-review-log/SKILL.md"
MIRROR_SKILL="${ROOT}/.reviews/skills/pr-review-log/SKILL.md"
if [[ -f "${SOURCE_SKILL}" || -f "${MIRROR_SKILL}" ]]; then
  if [[ ! -f "${SOURCE_SKILL}" || ! -f "${MIRROR_SKILL}" ]] || ! cmp -s "${SOURCE_SKILL}" "${MIRROR_SKILL}"; then
    echo "check_cursor_artifacts: pr-review-log mirror drift; .cursor/skills is authoritative" >&2
    exit 1
  fi
fi

scan_cursor_org_leak() {
  # 'online''chefgroep' splits the literal so this guard's own source does not
  # trip the repo-wide org-leak scanner (mirrors scripts/no_org_leak.py).
  local pattern='online''chefgroep|chefgroep\.(nl|online)'
  local found=0

  if command -v rg >/dev/null 2>&1; then
    if rg -i -n "${pattern}" .cursor/ \
      --glob '!.cursor/hooks/.state/**' \
      --glob '!.cursor/hooks/.gitignore' 2>/dev/null; then
      found=1
    fi
  elif grep -rniE "${pattern}" .cursor/ \
    --exclude-dir=.state 2>/dev/null; then
    found=1
  fi

  if [[ "${found}" -eq 1 ]]; then
    echo "check_cursor_artifacts: org handle or production domain under .cursor/" >&2
    echo "See docs/ops/private-cursor-overlay.md — org-pinned artifacts belong in the private deployment repo." >&2
    exit 1
  fi
}

scan_cursor_org_leak

echo "check_cursor_artifacts: ok"
