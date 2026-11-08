#!/usr/bin/env sh
# Product OIDC canary: IdP discovery + authorize 302 + callback contract.
# No secrets required. Never prints AUTH_OIDC_CLIENT_SECRET or token bodies.
set -eu

ISSUER="${AUTH_OIDC_ISSUER:-}"
CLIENT_ID="${AUTH_OIDC_CLIENT_ID:-}"
BASE="${KATER_OIDC_CANARY_URL:-http://127.0.0.1:9091}"
CURL_MAX="${KATER_OIDC_CANARY_TIMEOUT:-15}"

fail() {
  echo "oidc-canary FAIL: $1" >&2
  exit 1
}

pass() {
  echo "oidc-canary ok: $1"
}

if [ -z "$ISSUER" ]; then
  fail "AUTH_OIDC_ISSUER is required (example: https://auth.example.com/application/o/kater/)"
fi

case "$ISSUER" in
  */.well-known/openid-configuration) DISCOVERY="$ISSUER" ;;
  */) DISCOVERY="${ISSUER}.well-known/openid-configuration" ;;
  *) DISCOVERY="${ISSUER}/.well-known/openid-configuration" ;;
esac

body="$(mktemp)"
hdrs="$(mktemp)"
trap 'rm -f "$body" "$hdrs"' EXIT

code="$(curl -sS -o "$body" -w "%{http_code}" --max-time "$CURL_MAX" "$DISCOVERY" || true)"
[ "$code" = "200" ] || fail "discovery HTTP $code"

AUTHZ="$(python3 - "$body" <<'PY'
import json, sys
data = json.loads(open(sys.argv[1], encoding="utf-8").read())
for key in ("issuer", "authorization_endpoint", "token_endpoint"):
    if not data.get(key):
        raise SystemExit(f"discovery missing {key}")
print(data["authorization_endpoint"])
PY
)"
pass "IdP discovery 200"

status_code="$(curl -sS -o "$body" -w "%{http_code}" --max-time "$CURL_MAX" "${BASE}/oidc/status" || true)"
if [ "$status_code" != "200" ]; then
  fail "Kater /oidc/status HTTP $status_code (is kater serve running on ${BASE}?)"
fi
pass "Kater /oidc/status 200"

enabled="$(python3 - "$body" <<'PY'
import json, sys
print("1" if json.loads(open(sys.argv[1], encoding="utf-8").read()).get("enabled") else "0")
PY
)"

cb_code="$(curl -sS -o "$body" -w "%{http_code}" --max-time "$CURL_MAX" "${BASE}/oidc/callback" || true)"
[ "$cb_code" = "400" ] || fail "/oidc/callback without code expected 400, got $cb_code"
pass "/oidc/callback missing-code 400"

if [ "$enabled" != "1" ]; then
  login_code="$(curl -sS -o "$body" -w "%{http_code}" --max-time "$CURL_MAX" "${BASE}/oidc/login" || true)"
  [ "$login_code" = "404" ] || fail "/oidc/login unset expected 404, got $login_code"
  pass "OIDC unset: /oidc/login 404 (local/Access mode)"
  echo "oidc-canary PASS (discovery + Kater callback contract; product gate off)"
  exit 0
fi

if [ -z "$CLIENT_ID" ]; then
  fail "AUTH_OIDC_CLIENT_ID required when Kater OIDC is enabled"
fi

login_code="$(curl -sS -D "$hdrs" -o /dev/null -w "%{http_code}" --max-time "$CURL_MAX" \
  "${BASE}/oidc/login" || true)"
[ "$login_code" = "302" ] || fail "/oidc/login expected 302, got $login_code"
location="$(awk 'BEGIN{IGNORECASE=1} /^Location:/{sub(/\r/,""); sub(/^Location:[[:space:]]*/,""); print; exit}' "$hdrs")"
case "$location" in
  "$AUTHZ"*) ;;
  *) fail "/oidc/login Location did not start at discovery authorization_endpoint" ;;
esac
case "$location" in
  *client_id=*) ;;
  *) fail "/oidc/login Location missing client_id" ;;
esac
pass "/oidc/login 302 → IdP authorize"

echo "oidc-canary PASS (authorize→callback contract; no token exchange)"
