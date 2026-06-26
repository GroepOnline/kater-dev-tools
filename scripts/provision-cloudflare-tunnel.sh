#!/usr/bin/env bash
# Provision a Cloudflare Tunnel + DNS for Kater (requires CLOUDFLARE_API_TOKEN).
set -eu

DOMAIN="${1:-${KATER_DOMAIN:-kater.example.com}}"
TUNNEL_NAME="${2:-kater}"
ZONE_NAME="${DOMAIN#*.}"

: "${CLOUDFLARE_API_TOKEN:?Set CLOUDFLARE_API_TOKEN}"
: "${CLOUDFLARE_ACCOUNT_ID:?Set CLOUDFLARE_ACCOUNT_ID}"

echo "=== Kater tunnel provision: ${DOMAIN} ==="

ZONE_ID=$(curl -sS "https://api.cloudflare.com/client/v4/zones?name=${ZONE_NAME}" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
  | python3 -c "import json,sys; r=json.load(sys.stdin)['result']; print(r[0]['id'] if r else '')")
if [[ -z "$ZONE_ID" ]]; then
  echo "ERROR: zone not found for ${ZONE_NAME}"
  exit 1
fi

EXISTING=$(curl -sS "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/cfd_tunnel" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
  | python3 -c "import json,sys; print(next((t['id'] for t in json.load(sys.stdin).get('result',[]) if t.get('name')=='${TUNNEL_NAME}'), ''))")

if [[ -n "$EXISTING" ]]; then
  TUNNEL_ID="$EXISTING"
  echo "Reusing tunnel: ${TUNNEL_ID}"
else
  TUNNEL_ID=$(curl -sS -X POST "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/cfd_tunnel" \
    -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
    -H "Content-Type: application/json" \
    --data "{\"name\":\"${TUNNEL_NAME}\",\"config_src\":\"cloudflare\"}" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('result',{}).get('id','')); sys.exit(0 if d.get('success') else 1)")
  echo "Created tunnel: ${TUNNEL_ID}"
fi

curl -sS -X PUT "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/cfd_tunnel/${TUNNEL_ID}/configurations" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data "{\"config\":{\"ingress\":[{\"hostname\":\"${DOMAIN}\",\"path\":\"/ws\",\"service\":\"http://localhost:9092\"},{\"hostname\":\"${DOMAIN}\",\"service\":\"http://localhost:9090\"},{\"service\":\"http_status:404\"}]}}" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('success') else 1)"

HOST="${DOMAIN%%.*}"
curl -sS -X POST "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/dns_records" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data "{\"type\":\"CNAME\",\"name\":\"${HOST}\",\"content\":\"${TUNNEL_ID}.cfargotunnel.com\",\"proxied\":true,\"ttl\":1}" \
  >/dev/null 2>&1 || true

TOKEN=$(curl -sS "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/cfd_tunnel/${TUNNEL_ID}/token" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('result','')); sys.exit(0 if d.get('success') else 1)")

mkdir -p "${HOME}/.config/kater"
cat > "${HOME}/.config/kater/tunnel.env" <<EOF
KATER_TUNNEL_TOKEN=${TOKEN}
KATER_DOMAIN=${DOMAIN}
EOF
chmod 600 "${HOME}/.config/kater/tunnel.env"

echo "Wrote ${HOME}/.config/kater/tunnel.env (mode 600)"
echo "MCP URL: https://${DOMAIN}/sse"
echo "Dashboard: https://${DOMAIN}/dashboard"
echo "Enable systemd: systemctl --user enable --now kater-cloudflared.service"
