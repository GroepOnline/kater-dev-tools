#!/usr/bin/env bash
set -Eeuo pipefail
SHA="$1"; SERVICE="$2"; API_PORT="$3"; PRODUCT_PORT="$4"; CURRENT="$5"; RELEASE_ROOT="$6"; STATE="$7"
PRODUCT_ENV_STAGE="$8"; PRODUCT_SECRET_STAGE="$9"
RELEASE="$RELEASE_ROOT/$SHA"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
LEGACY="$CURRENT.pre-$TS"
FAILED="$CURRENT.failed-$TS"
PREVIOUS=""
FIRST=0
CUTOVER=0
ACTIVE_DEPENDENTS=()
CONFIG_DIR=/etc/chef/kater
DROPIN_DIR="/etc/systemd/system/$SERVICE.d"
PRODUCT_ENV="$CONFIG_DIR/product.env"
PRODUCT_SECRET="$CONFIG_DIR/product-secrets.env"
PRODUCT_DROPIN="$DROPIN_DIR/30-product-mcp.conf"
CONFIG_BACKUP="$CONFIG_DIR/.rollback-$SHA-$TS"
CONFIG_APPLIED=0

cleanup_staged_config() {
  unlink "$PRODUCT_ENV_STAGE" "$PRODUCT_SECRET_STAGE" 2>/dev/null || true
}
trap cleanup_staged_config EXIT

discard_config_backup() {
  if sudo -n test -d "$CONFIG_BACKUP"; then
    sudo -n find "$CONFIG_BACKUP" -depth -delete
  fi
}

restore_product_config() {
  [[ "$CONFIG_APPLIED" == 1 ]] || return 0
  for name in product.env product-secrets.env 30-product-mcp.conf; do
    backup="$CONFIG_BACKUP/$name"
    case "$name" in
      30-product-mcp.conf) destination="$PRODUCT_DROPIN" ;;
      product.env) destination="$PRODUCT_ENV" ;;
      *) destination="$PRODUCT_SECRET" ;;
    esac
    if sudo -n test -e "$backup"; then
      sudo -n install -m "$(sudo -n stat -c %a "$backup")" -o root -g root "$backup" "$destination"
    else
      sudo -n unlink "$destination" 2>/dev/null || true
    fi
  done
  sudo -n systemctl daemon-reload
  discard_config_backup
}

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
    restore_product_config || true
    sudo -n systemctl start "$SERVICE" >/dev/null 2>&1 || true
    for dependent in "${ACTIVE_DEPENDENTS[@]}"; do
      sudo -n systemctl start "$dependent" >/dev/null 2>&1 || \
        echo "deploy: rollback could not restart dependent $dependent" >&2
    done
  fi
  exit "$rc"
}
trap rollback ERR

cd "$RELEASE"
printf '%s\n' "$SHA" > .deployed-sha
ln -sfn "$STATE" .kater
HOME="${HOME:-/home/chef}" uv sync --frozen
.venv/bin/python scripts/check_executor_contract.py

# rsync copies the 0700 mode of mktemp's archive root onto RELEASE.  The
# systemd service runs as a different user, so make the release path traversable
# explicitly and prove that exact service identity can reach the executable
# before stopping the healthy runtime. Never hide permission failures here.
if ! sudo -n chmod a+rx "$RELEASE" "$RELEASE_ROOT" "$(dirname "$CURRENT")" 2>/dev/null; then
  chmod a+rx "$RELEASE" "$RELEASE_ROOT" "$(dirname "$CURRENT")"
fi
if ! sudo -n chmod -R a+rX "$RELEASE" 2>/dev/null; then
  chmod -R a+rX "$RELEASE"
fi
SERVICE_USER="$(systemctl show -p User --value "$SERVICE")"
SERVICE_USER="${SERVICE_USER:-root}"
[[ "$SERVICE_USER" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "deploy: unsafe service user: $SERVICE_USER" >&2; false; }
if ! sudo -n -u "$SERVICE_USER" test -x "$RELEASE"; then
  echo "deploy: service user $SERVICE_USER cannot traverse release $RELEASE" >&2
  false
fi
if ! sudo -n -u "$SERVICE_USER" test -x "$RELEASE/.venv/bin/kater"; then
  echo "deploy: service user $SERVICE_USER cannot execute staged kater" >&2
  false
fi

curl -fsS --max-time 2 "http://127.0.0.1:$API_PORT/health/live" >/dev/null

if [[ -L "$CURRENT" ]]; then
  PREVIOUS="$(readlink -f "$CURRENT")"
else
  [[ -d "$CURRENT" ]] || { echo "deploy: current runtime missing" >&2; false; }
  FIRST=1
fi

# Stopping a required backend also stops reverse-dependent proxy services.
# Preserve only the service units that are active before cutover and restore
# that exact exposure set after either a successful cutover or rollback.
while IFS= read -r dependent; do
  dependent="${dependent#"${dependent%%[![:space:]]*}"}"
  [[ "$dependent" == *.service && "$dependent" != "$SERVICE" ]] || continue
  if systemctl is-active --quiet "$dependent"; then
    ACTIVE_DEPENDENTS+=("$dependent")
  fi
done < <(systemctl list-dependencies --reverse --plain --no-legend "$SERVICE")

CUTOVER=1
sudo -n systemctl stop "$SERVICE"
if (( FIRST )); then
  mv "$CURRENT" "$LEGACY"
  [[ -d "$LEGACY/.kater" ]] || { echo "deploy: persistent .kater state missing" >&2; false; }
  [[ ! -e "$STATE" ]] || { echo "deploy: state target already exists on first cutover" >&2; false; }
  sudo -n mv "$LEGACY/.kater" "$STATE"
fi

ln -sfn "$RELEASE" "$CURRENT"
sudo -n mkdir -p "$CONFIG_DIR" "$DROPIN_DIR" "$CONFIG_BACKUP"
sudo -n chmod 700 "$CONFIG_BACKUP"
for pair in "$PRODUCT_ENV:product.env" "$PRODUCT_SECRET:product-secrets.env" "$PRODUCT_DROPIN:30-product-mcp.conf"; do
  source_path="${pair%%:*}"; backup_name="${pair#*:}"
  if sudo -n test -e "$source_path"; then
    sudo -n cp -a "$source_path" "$CONFIG_BACKUP/$backup_name"
  fi
done
sudo -n install -m 0644 -o root -g root "$PRODUCT_ENV_STAGE" "$PRODUCT_ENV"
sudo -n install -m 0600 -o root -g root "$PRODUCT_SECRET_STAGE" "$PRODUCT_SECRET"
printf '%s\n' '[Service]' \
  'EnvironmentFile=/etc/chef/kater/product.env' \
  'EnvironmentFile=/etc/chef/kater/product-secrets.env' | \
  sudo -n tee "$PRODUCT_DROPIN" >/dev/null
sudo -n chmod 0644 "$PRODUCT_DROPIN"
unlink "$PRODUCT_ENV_STAGE" "$PRODUCT_SECRET_STAGE"
CONFIG_APPLIED=1
sudo -n systemctl daemon-reload
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
# Readiness includes the enabled product listener, exact resource metadata,
# bearer rejection and live Auth introspection. Failure keeps rollback armed.
ready=0
ready_deadline=$((SECONDS + 30))
while (( SECONDS < ready_deadline )); do
  readiness="$(curl --fail-with-body -sS --max-time 15 "http://127.0.0.1:$API_PORT/health/ready" || true)"
  if printf '%s' "$readiness" | "$RELEASE/.venv/bin/python" -c \
    'import json,sys; data=json.load(sys.stdin); raise SystemExit(0 if data.get("components",{}).get("product_mcp",{}).get("status")=="ok" else 1)'; then
    printf '%s\n' "$readiness"
    ready=1
    break
  fi
  sleep 0.5
done
[[ "$ready" == 1 ]] || { echo "deploy: product/Auth readiness failed" >&2; false; }
metadata_status="$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PRODUCT_PORT/.well-known/oauth-protected-resource/mcp")"
anonymous_status="$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' --data '{}' "http://127.0.0.1:$PRODUCT_PORT/mcp")"
[[ "$metadata_status" == 200 ]] || { echo "deploy: product metadata probe failed" >&2; false; }
[[ "$anonymous_status" == 401 ]] || { echo "deploy: product bearer probe failed" >&2; false; }
[[ "$(cat "$CURRENT/.deployed-sha")" == "$SHA" ]] || { echo "deploy: active SHA mismatch" >&2; false; }
for dependent in "${ACTIVE_DEPENDENTS[@]}"; do
  sudo -n systemctl start "$dependent"
  if ! systemctl is-active --quiet "$dependent"; then
    echo "deploy: dependent did not become active: $dependent" >&2
    false
  fi
done

sudo -n mkdir -p "$(dirname "$STATE")" 2>/dev/null || true
sudo -n chmod a+rwx "$(dirname "$STATE")" 2>/dev/null || true
printf '%s\n' "$SHA" | sudo -n tee "$(dirname "$STATE")/kater-deployed-sha" >/dev/null 2>&1 || printf '%s\n' "$SHA" > "$(dirname "$STATE")/kater-deployed-sha"
printf '%s\n' "$PREVIOUS" | sudo -n tee "$(dirname "$STATE")/kater-previous-release" >/dev/null 2>&1 || printf '%s\n' "$PREVIOUS" > "$(dirname "$STATE")/kater-previous-release"
discard_config_backup
CUTOVER=0
trap - ERR

echo "deploy: active_sha=$SHA"
if (( FIRST )); then
  echo "deploy: legacy_rollback=$LEGACY"
elif [[ -n "$PREVIOUS" ]]; then
  echo "deploy: previous_release=$PREVIOUS"
fi
