#!/usr/bin/env bash
set -Eeuo pipefail

fail() { echo "deploy-company-control: $*" >&2; exit 1; }

: "${KATER_DEPLOY_SHA:?KATER_DEPLOY_SHA is required}"
: "${KATER_DEPLOY_TARGET:?KATER_DEPLOY_TARGET is required (user@host)}"
: "${KATER_DEPLOY_SERVICE:?KATER_DEPLOY_SERVICE is required}"
: "${KATER_RESOURCE_AUTH_ISSUER:?KATER_RESOURCE_AUTH_ISSUER is required}"
: "${KATER_RESOURCE_AUTH_RESOURCE:?KATER_RESOURCE_AUTH_RESOURCE is required}"
: "${KATER_RESOURCE_AUTH_SCOPES:?KATER_RESOURCE_AUTH_SCOPES is required}"
: "${KATER_RESOURCE_AUTH_SERVICE_KEY:?KATER_RESOURCE_AUTH_SERVICE_KEY is required}"

SHA="$KATER_DEPLOY_SHA"
TARGET="$KATER_DEPLOY_TARGET"
SERVICE="$KATER_DEPLOY_SERVICE"
API_PORT="${KATER_DEPLOY_API_PORT:-9091}"
PRODUCT_PORT="${KATER_PRODUCT_MCP_PORT:-9093}"
REMOTE_ROOT="${KATER_DEPLOY_ROOT:-/opt/chef}"
CURRENT="${KATER_DEPLOY_CURRENT:-$REMOTE_ROOT/services/kater}"
RELEASE_ROOT="${KATER_RELEASE_ROOT:-$REMOTE_ROOT/releases/kater}"
STATE="${KATER_STATE_PATH:-$REMOTE_ROOT/state/kater-project}"

[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || fail "SHA must be 40 lowercase hex chars"
[[ "$TARGET" =~ ^[A-Za-z0-9._@:-]+$ ]] || fail "unsafe deploy target"
[[ "$SERVICE" =~ ^[A-Za-z0-9_.@-]+$ ]] || fail "unsafe service name"
[[ "$API_PORT" =~ ^[0-9]+$ ]] || fail "API port must be numeric"
[[ "$PRODUCT_PORT" =~ ^[0-9]+$ ]] || fail "product MCP port must be numeric"
[[ "${KATER_RESOURCE_AUTH_ENABLED:-}" == 1 ]] || fail "product resource auth must be enabled"
[[ "$KATER_RESOURCE_AUTH_ISSUER" =~ ^https://[^[:space:]]+$ ]] || fail "resource issuer must be HTTPS"
[[ "$KATER_RESOURCE_AUTH_RESOURCE" =~ ^https://[^[:space:]]+/mcp$ ]] || fail "resource URL must be exact HTTPS /mcp"
[[ "$KATER_RESOURCE_AUTH_SCOPES" =~ ^[a-z0-9:_-]+([[:space:]][a-z0-9:_-]+)*$ ]] || fail "resource scopes are invalid"
[[ "${KATER_RESOURCE_AUTH_SERVICE_KEY_ENV:-}" == KATER_RESOURCE_AUTH_SERVICE_KEY ]] || fail "service key env indirection is invalid"
[[ "$KATER_RESOURCE_AUTH_SERVICE_KEY" =~ ^[A-Za-z0-9._~-]{32,}$ ]] || fail "resource service key is invalid"
git cat-file -e "$SHA^{commit}" 2>/dev/null || fail "commit is not in this checkout"
git merge-base --is-ancestor "$SHA" origin/main || fail "commit is not on origin/main"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
ARCHIVE="$TMP/release"
mkdir "$ARCHIVE"
cat > "$TMP/product.env" <<EOF
KATER_RESOURCE_AUTH_ENABLED=1
KATER_RESOURCE_AUTH_ISSUER=$KATER_RESOURCE_AUTH_ISSUER
KATER_RESOURCE_AUTH_RESOURCE=$KATER_RESOURCE_AUTH_RESOURCE
KATER_RESOURCE_AUTH_SCOPES=$KATER_RESOURCE_AUTH_SCOPES
KATER_RESOURCE_AUTH_SERVICE_KEY_ENV=KATER_RESOURCE_AUTH_SERVICE_KEY
KATER_PRODUCT_MCP_PORT=$PRODUCT_PORT
EOF
printf 'KATER_RESOURCE_AUTH_SERVICE_KEY=%s\n' "$KATER_RESOURCE_AUTH_SERVICE_KEY" > "$TMP/product-secrets.env"
chmod 600 "$TMP/product.env" "$TMP/product-secrets.env"
git archive "$SHA" | tar -x -C "$ARCHIVE"
ssh -o BatchMode=yes "$TARGET" \
  "mkdir -p '$RELEASE_ROOT/$SHA' '$(dirname "$STATE")'"

rsync -a --delete \
  --exclude='.venv/' --exclude='.kater/' \
  --exclude='.pytest_cache/' --exclude='.mypy_cache/' --exclude='.ruff_cache/' \
  "$ARCHIVE/" "$TARGET:$RELEASE_ROOT/$SHA/"

tar -C "$TMP" -cf - product.env product-secrets.env | \
  ssh -o BatchMode=yes "$TARGET" \
    "set -Eeuo pipefail; stage=\$(mktemp -d); trap 'find \"\$stage\" -depth -delete' EXIT; tar -xf - -C \"\$stage\"; '$RELEASE_ROOT/$SHA/scripts/deploy-company-control-remote.sh' '$SHA' '$SERVICE' '$API_PORT' '$PRODUCT_PORT' '$CURRENT' '$RELEASE_ROOT' '$STATE' \"\$stage/product.env\" \"\$stage/product-secrets.env\""
