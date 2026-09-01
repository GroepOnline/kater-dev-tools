#!/usr/bin/env bash
set -Eeuo pipefail

fail() { echo "deploy-company-control: $*" >&2; exit 1; }

: "${KATER_DEPLOY_SHA:?KATER_DEPLOY_SHA is required}"
: "${KATER_DEPLOY_TARGET:?KATER_DEPLOY_TARGET is required (user@host)}"
: "${KATER_DEPLOY_SERVICE:?KATER_DEPLOY_SERVICE is required}"

SHA="$KATER_DEPLOY_SHA"
TARGET="$KATER_DEPLOY_TARGET"
SERVICE="$KATER_DEPLOY_SERVICE"
API_PORT="${KATER_DEPLOY_API_PORT:-9091}"
REMOTE_ROOT="${KATER_DEPLOY_ROOT:-/opt/chef}"
CURRENT="${KATER_DEPLOY_CURRENT:-$REMOTE_ROOT/services/kater}"
RELEASE_ROOT="${KATER_RELEASE_ROOT:-$REMOTE_ROOT/releases/kater}"
STATE="${KATER_STATE_PATH:-$REMOTE_ROOT/state/kater-project}"

[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || fail "SHA must be 40 lowercase hex chars"
[[ "$TARGET" =~ ^[A-Za-z0-9._@:-]+$ ]] || fail "unsafe deploy target"
[[ "$SERVICE" =~ ^[A-Za-z0-9_.@-]+$ ]] || fail "unsafe service name"
[[ "$API_PORT" =~ ^[0-9]+$ ]] || fail "API port must be numeric"
git cat-file -e "$SHA^{commit}" 2>/dev/null || fail "commit is not in this checkout"
git merge-base --is-ancestor "$SHA" origin/main || fail "commit is not on origin/main"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git archive "$SHA" | tar -x -C "$TMP"
ssh -o BatchMode=yes "$TARGET" \
  "mkdir -p '$RELEASE_ROOT/$SHA' '$(dirname "$STATE")'"

rsync -a --delete \
  --exclude='.venv/' --exclude='.kater/' \
  --exclude='.pytest_cache/' --exclude='.mypy_cache/' --exclude='.ruff_cache/' \
  "$TMP/" "$TARGET:$RELEASE_ROOT/$SHA/"

ssh -o BatchMode=yes "$TARGET" bash -s -- \
  "$SHA" "$SERVICE" "$API_PORT" "$CURRENT" "$RELEASE_ROOT" "$STATE" <<'REMOTE'
set -Eeuo pipefail
SHA="$1"; SERVICE="$2"; API_PORT="$3"; CURRENT="$4"; RELEASE_ROOT="$5"; STATE="$6"
RELEASE="$RELEASE_ROOT/$SHA"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
LEGACY="$CURRENT.pre-$TS"
FAILED="$CURRENT.failed-$TS"
PREVIOUS=""
FIRST=0
CUTOVER=0

rollback() {
  rc=$?
  if (( CUTOVER )); then
    echo "deploy: cutover failed; restoring previous runtime" >&2
    sudo -n systemctl stop "$SERVICE" >/dev/null 2>&1 || true
    if (( FIRST )); then
      if [[ -L "$CURRENT" ]]; then mv "$CURRENT" "$FAILED"; fi
      if [[ -d "$STATE" && -d "$LEGACY" ]]; then sudo -n mv "$STATE" "$LEGACY/.kater"; fi
      if [[ -d "$LEGACY" && ! -e "$CURRENT" ]]; then mv "$LEGACY" "$CURRENT"; fi
    elif [[ -n "$PREVIOUS" ]]; then
      ln -sfn "$PREVIOUS" "$CURRENT"
    fi
    sudo -n systemctl start "$SERVICE" >/dev/null 2>&1 || true
  fi
  exit "$rc"
}
trap rollback ERR

cd "$RELEASE"
printf '%s\n' "$SHA" > .deployed-sha
ln -sfn "$STATE" .kater
HOME="${HOME:-/home/chef}" uv sync --frozen
.venv/bin/python scripts/check_executor_contract.py

# Ensure release is readable by the kater service user (systemd chdir fails otherwise).
# rsync as chef may create 700 dirs; kater runs as different user.
sudo -n chmod -R a+rX "$RELEASE" 2>/dev/null || chmod -R a+rX "$RELEASE" 2>/dev/null || true
sudo -n chmod a+rx "$RELEASE_ROOT" "$(dirname "$CURRENT")" 2>/dev/null || true

curl -fsS --max-time 2 "http://127.0.0.1:$API_PORT/health/live" >/dev/null

if [[ -L "$CURRENT" ]]; then
  PREVIOUS="$(readlink -f "$CURRENT")"
else
  [[ -d "$CURRENT" ]] || { echo "deploy: current runtime missing" >&2; false; }
  FIRST=1
fi

CUTOVER=1
sudo -n systemctl stop "$SERVICE"
if (( FIRST )); then
  mv "$CURRENT" "$LEGACY"
  [[ -d "$LEGACY/.kater" ]] || { echo "deploy: persistent .kater state missing" >&2; false; }
  [[ ! -e "$STATE" ]] || { echo "deploy: state target already exists on first cutover" >&2; false; }
  sudo -n mv "$LEGACY/.kater" "$STATE"
fi

ln -sfn "$RELEASE" "$CURRENT"
sudo -n systemctl daemon-reload 2>/dev/null || true
sudo -n systemctl start "$SERVICE"
healthy=0
for _ in $(seq 1 40); do
  if curl -fsS --max-time 1 "http://127.0.0.1:$API_PORT/health/live" >/dev/null 2>&1; then
    healthy=1
    break
  fi
  sleep 0.5
done
if [[ "$healthy" != 1 ]]; then
  echo "deploy: new runtime did not become healthy — dumping diagnostics" >&2
  sudo -n systemctl status "$SERVICE" --no-pager 2>&1 | head -80 >&2 || true
  sudo -n journalctl -u "$SERVICE" -n 80 --no-pager 2>&1 | tail -80 >&2 || true
  echo "deploy: new runtime did not become healthy" >&2
  false
fi
[[ "$(cat "$CURRENT/.deployed-sha")" == "$SHA" ]] || { echo "deploy: active SHA mismatch" >&2; false; }

printf '%s\n' "$SHA" > "$(dirname "$STATE")/kater-deployed-sha"
printf '%s\n' "$PREVIOUS" > "$(dirname "$STATE")/kater-previous-release"
CUTOVER=0
trap - ERR

echo "deploy: active_sha=$SHA"
if (( FIRST )); then
  echo "deploy: legacy_rollback=$LEGACY"
elif [[ -n "$PREVIOUS" ]]; then
  echo "deploy: previous_release=$PREVIOUS"
fi
REMOTE
