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

# git clone/fetch/set-url/checkout diagnostics can echo the remote URL,
# including credentials in CHEFGROEP_SKILLS_GIT_URL. Never surface that
# on stdout, stderr, or Git trace destinations.
git_quiet() {
  (
    unset \
      GIT_TRACE \
      GIT_TRACE2 \
      GIT_TRACE2_EVENT \
      GIT_TRACE2_PERF \
      GIT_TRACE2_BRIEF \
      GIT_TRACE2_EVENT_BRIEF \
      GIT_TRACE2_PERF_BRIEF \
      GIT_TRACE2_CONFIG_PARAMS \
      GIT_TRACE2_ENV_VARS \
      GIT_TRACE2_DST_DEBUG \
      GIT_TRACE_PACKET \
      GIT_TRACE_PERFORMANCE \
      GIT_TRACE_SETUP \
      GIT_TRACE_SHALLOW \
      GIT_TRACE_CURL \
      GIT_TRACE_CURL_NO_DATA \
      GIT_TRACE_PACK_ACCESS \
      GIT_TRACE_PACKFILE \
      GIT_CURL_VERBOSE
    export GIT_TERMINAL_PROMPT=0
    exec git "$@" >/dev/null 2>&1
  )
}

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

# Never persist userinfo in .git/config. Credentials stay in-process via
# a one-shot http.extraHeader on clone/fetch only.
credential_free_url() {
  local url="$1"
  case "$url" in
    https://*@*) printf 'https://%s\n' "${url#https://*@}" ;;
    http://*@*) printf 'http://%s\n' "${url#http://*@}" ;;
    *) printf '%s\n' "$url" ;;
  esac
}

userinfo_basic() {
  local url="$1"
  local rest userinfo
  case "$url" in
    https://*@*|http://*@*)
      rest="${url#*://}"
      userinfo="${rest%%@*}"
      if [[ -n "${userinfo}" && "${userinfo}" == *:* ]]; then
        printf '%s' "${userinfo}" | base64 -w0 2>/dev/null || printf '%s' "${userinfo}" | base64
        return 0
      fi
      ;;
  esac
  return 1
}

git_transport() {
  local hdr
  if hdr="$(userinfo_basic "${GIT_URL}")"; then
    git_quiet -c "http.extraHeader=Authorization: Basic ${hdr}" "$@"
  else
    git_quiet "$@"
  fi
}

scrub_origin_userinfo() {
  local existing
  existing="$(git -C "${CACHE_ROOT}" remote get-url origin 2>/dev/null || true)"
  if [[ -z "${existing}" ]]; then
    return 0
  fi
  git_quiet -C "${CACHE_ROOT}" remote set-url origin "$(credential_free_url "${existing}")" || true
}

run_upstream_sync() {
  (
    unset CHEFGROEP_SKILLS_GIT_URL
    unset \
      GIT_TRACE \
      GIT_TRACE2 \
      GIT_TRACE2_EVENT \
      GIT_TRACE2_PERF \
      GIT_TRACE2_BRIEF \
      GIT_TRACE2_EVENT_BRIEF \
      GIT_TRACE2_PERF_BRIEF \
      GIT_TRACE2_CONFIG_PARAMS \
      GIT_TRACE2_ENV_VARS \
      GIT_TRACE2_DST_DEBUG \
      GIT_TRACE_PACKET \
      GIT_TRACE_PERFORMANCE \
      GIT_TRACE_SETUP \
      GIT_TRACE_SHALLOW \
      GIT_TRACE_CURL \
      GIT_TRACE_CURL_NO_DATA \
      GIT_TRACE_PACK_ACCESS \
      GIT_TRACE_PACKFILE \
      GIT_CURL_VERBOSE
    export GIT_TERMINAL_PROMPT=0
    exec "$@"
  )
}

SAFE_URL="$(credential_free_url "${GIT_URL}")"
mkdir -p "$(dirname "${CACHE_ROOT}")"
if [[ -d "${CACHE_ROOT}/.git" ]]; then
  log "update ${CACHE_ROOT}"
  scrub_origin_userinfo
  if ! git_quiet -C "${CACHE_ROOT}" remote set-url origin "${SAFE_URL}"; then
    log "ERROR: could not retarget origin"
    exit 1
  fi
  if ! git_transport -C "${CACHE_ROOT}" fetch --depth 1 --quiet origin; then
    log "ERROR: fetch failed (grant Cloud Agent token access to the meta-skills repo)"
    exit 1
  fi
  if ! git_quiet -C "${CACHE_ROOT}" checkout --force --quiet FETCH_HEAD; then
    log "ERROR: checkout failed"
    exit 1
  fi
else
  log "clone ChefGroep skills"
  rm -rf "${CACHE_ROOT}"
  if ! git_transport clone --depth 1 --quiet "${SAFE_URL}" "${CACHE_ROOT}"; then
    log "ERROR: clone failed (grant Cloud Agent token access to the meta-skills repo)"
    exit 1
  fi
  git_quiet -C "${CACHE_ROOT}" remote set-url origin "${SAFE_URL}" || true
fi

# Prefer upstream sync contract when present. Fail closed: a broken
# upstream sync must not report a successful plugin install.
if [[ -x "${CACHE_ROOT}/sync.sh" ]]; then
  log "run upstream sync.sh"
  (cd "${CACHE_ROOT}" && run_upstream_sync ./sync.sh)
elif [[ -x "${CACHE_ROOT}/scripts/sync.sh" ]]; then
  log "run upstream scripts/sync.sh"
  (cd "${CACHE_ROOT}" && run_upstream_sync ./scripts/sync.sh)
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
if ! command -v uv >/dev/null 2>&1; then
  log "ERROR: uv is required to write plugin manifest"
  exit 1
fi
PLUGIN_NAME="${PLUGIN_NAME}" PLUGIN_DEST="${PLUGIN_DEST}" uv run python - <<'PY'
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
