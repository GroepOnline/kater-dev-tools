#!/usr/bin/env bash
# Bootstrap ChefGroep meta-skills into this Cloud/desktop agent workspace.
#
# Does not hardcode an org GitHub slug. Pass the private meta-repo via:
#   CHEFGROEP_SKILLS_REPO=github.com/<org>/chefgroep-skills
# or a full git URL in CHEFGROEP_SKILLS_GIT_URL.
#
# Installs under .cursor/plugins/chefgroep-skills/ so workspaceOpen can register
# pluginPaths without polluting committed .cursor/skills (mesh satellites stay SSOT).
#
# Usage:
#   CHEFGROEP_SKILLS_REPO=github.com/example/chefgroep-skills ./scripts/sync-chefgroep-skills.sh
#   ./scripts/sync-chefgroep-skills.sh --dry-run
#   ./scripts/sync-chefgroep-skills.sh --check
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_DIR}"

DRY_RUN=0
CHECK_ONLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --check) CHECK_ONLY=1; shift ;;
    -h|--help)
      sed -n '2,20p' "$0"
      exit 0
      ;;
    *)
      printf '[sync-chefgroep-skills] ERROR: unknown arg %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

log() { printf '[sync-chefgroep-skills] %s\n' "$*"; }

PLUGIN_NAME="chefgroep-skills"
PLUGIN_DEST="${REPO_DIR}/.cursor/plugins/${PLUGIN_NAME}"
CACHE_ROOT="${CURSOR_PLUGINS_HOME:-${HOME}/.cursor/plugins}/sources/${PLUGIN_NAME}"

resolve_git_url() {
  if [[ -n "${CHEFGROEP_SKILLS_GIT_URL:-}" ]]; then
    printf '%s\n' "${CHEFGROEP_SKILLS_GIT_URL}"
    return
  fi
  if [[ -n "${CHEFGROEP_SKILLS_REPO:-}" ]]; then
    local repo="${CHEFGROEP_SKILLS_REPO}"
    repo="${repo#https://}"
    repo="${repo#git@}"
    repo="${repo%.git}"
    repo="${repo#github.com/}"
    repo="${repo#github.com:}"
    printf 'https://github.com/%s.git\n' "${repo}"
    return
  fi
  return 1
}

if [[ "${CHECK_ONLY}" -eq 1 ]]; then
  if resolve_git_url >/dev/null; then
    log "check OK (repo env present)"
    exit 0
  fi
  log "ERROR: set CHEFGROEP_SKILLS_REPO or CHEFGROEP_SKILLS_GIT_URL"
  exit 1
fi

if ! GIT_URL="$(resolve_git_url)"; then
  log "ERROR: set CHEFGROEP_SKILLS_REPO=github.com/<org>/chefgroep-skills (or CHEFGROEP_SKILLS_GIT_URL)"
  log "skip: ChefGroep meta-skills not synced"
  exit 0
fi

if [[ "${DRY_RUN}" -eq 1 ]]; then
  log "would sync ChefGroep skills -> ${CACHE_ROOT}"
  log "would install plugin tree -> ${PLUGIN_DEST}"
  exit 0
fi

if ! command -v git >/dev/null 2>&1; then
  log "ERROR: git is required"
  exit 1
fi

mkdir -p "$(dirname "${CACHE_ROOT}")"
if [[ -d "${CACHE_ROOT}/.git" ]]; then
  log "update ${CACHE_ROOT}"
  git -C "${CACHE_ROOT}" remote set-url origin "${GIT_URL}"
  git -C "${CACHE_ROOT}" fetch --depth 1 origin
  git -C "${CACHE_ROOT}" checkout --force FETCH_HEAD
  git -C "${CACHE_ROOT}" pull --ff-only 2>/dev/null || true
else
  log "clone ChefGroep skills"
  rm -rf "${CACHE_ROOT}"
  if ! git clone --depth 1 "${GIT_URL}" "${CACHE_ROOT}"; then
    log "ERROR: clone failed (grant Cloud Agent token access to the meta-skills repo)"
    exit 1
  fi
fi

# Prefer upstream sync contract when present. Fail closed: a broken
# upstream sync must not report a successful plugin install.
if [[ -x "${CACHE_ROOT}/sync.sh" ]]; then
  log "run upstream sync.sh"
  (cd "${CACHE_ROOT}" && ./sync.sh)
elif [[ -x "${CACHE_ROOT}/scripts/sync.sh" ]]; then
  log "run upstream scripts/sync.sh"
  (cd "${CACHE_ROOT}" && ./scripts/sync.sh)
fi

# Cursor Cloud plugin discovery via workspaceOpen pluginPaths.
rm -rf "${PLUGIN_DEST}"
mkdir -p "${PLUGIN_DEST}"
copied=0
for component in skills commands agents rules hooks assets mcp.json .mcp.json .cursor-plugin .claude-plugin; do
  src="${CACHE_ROOT}/${component}"
  if [[ -e "${src}" ]]; then
    cp -a "${src}" "${PLUGIN_DEST}/${component}"
    copied=$((copied + 1))
  fi
done

# Some layouts keep skills under skills/ at repo root only; also accept .cursor/skills.
if [[ ! -d "${PLUGIN_DEST}/skills" && -d "${CACHE_ROOT}/.cursor/skills" ]]; then
  cp -a "${CACHE_ROOT}/.cursor/skills" "${PLUGIN_DEST}/skills"
  copied=$((copied + 1))
fi
if [[ ! -d "${PLUGIN_DEST}/commands" && -d "${CACHE_ROOT}/.cursor/commands" ]]; then
  cp -a "${CACHE_ROOT}/.cursor/commands" "${PLUGIN_DEST}/commands"
  copied=$((copied + 1))
fi

mkdir -p "${REPO_DIR}/.cursor/plugins/installed"
PLUGIN_NAME="${PLUGIN_NAME}" PLUGIN_DEST="${PLUGIN_DEST}" python3 - <<'PY'
import json
import os
from datetime import UTC, datetime
from pathlib import Path

name = os.environ["PLUGIN_NAME"]
dest = Path(os.environ["PLUGIN_DEST"])
manifest = dest.parent / "installed" / "manifest.json"
payload: dict = {}
if manifest.is_file():
    payload = json.loads(manifest.read_text(encoding="utf-8"))
plugins = payload.setdefault("plugins", {})
plugins[name] = str(dest)
payload["version"] = 1
payload["generated_at"] = datetime.now(UTC).isoformat()
manifest.parent.mkdir(parents=True, exist_ok=True)
manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY

log "done (plugin components=${copied}; dest=${PLUGIN_DEST})"
