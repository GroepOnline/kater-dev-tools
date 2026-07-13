#!/usr/bin/env bash
set -eu

DOMAIN="${1:-kater.example.com}"
TUNNEL_NAME="${2:-kater}"
AUTH_MODE="${KATER_AUTH_MODE:-oauth}"
CONFIG_DIR="$HOME/.cloudflared"
CONFIG_FILE="$CONFIG_DIR/${TUNNEL_NAME}.yml"

echo "=== Kater Cloudflare Deploy (secured) ==="
echo "Domain: $DOMAIN"
echo "Tunnel: $TUNNEL_NAME"
echo "Auth:   $AUTH_MODE"
echo ""

if [[ "$AUTH_MODE" != "oauth" && "$AUTH_MODE" != "apikey" ]]; then
    echo "ERROR: KATER_AUTH_MODE must be 'oauth' (ChatGPT) or 'apikey' (Cursor/agents)"
    exit 1
fi

if [[ "$AUTH_MODE" == "apikey" && -z "${KATER_API_KEY:-}" && -z "${KATER_API_KEYS:-}" ]]; then
    echo "ERROR: Set KATER_API_KEY before deploying with apikey auth."
    exit 1
fi

if ! command -v cloudflared &>/dev/null; then
    echo "ERROR: cloudflared not installed"
    echo "  https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
    exit 1
fi

if [[ ! -f "$CONFIG_DIR/cert.pem" ]]; then
    echo "ERROR: Cloudflare origin certificate missing."
    echo "  Run once: cloudflared tunnel login"
    exit 1
fi

if ! cloudflared tunnel list 2>/dev/null | grep -q "$TUNNEL_NAME"; then
    echo "Creating tunnel: $TUNNEL_NAME"
    cloudflared tunnel create "$TUNNEL_NAME"
fi

echo "Creating DNS route: $DOMAIN -> $TUNNEL_NAME"
cloudflared tunnel route dns "$TUNNEL_NAME" "$DOMAIN" 2>/dev/null || true

echo "Generating config: $CONFIG_FILE"
mkdir -p "$CONFIG_DIR"
uv run kater tunnel config -p cloudflare --domain "$DOMAIN" > "$CONFIG_FILE"

export KATER_PUBLIC=1
export KATER_AUTH_MODE="$AUTH_MODE"
export KATER_HOST=127.0.0.1
export KATER_RATE_LIMIT="${KATER_RATE_LIMIT:-60}"
export KATER_CORS_ORIGINS="${KATER_CORS_ORIGINS:-https://${DOMAIN}}"

echo ""
echo "Starting secured Kater + tunnel..."
echo ""

uv run kater serve &
KATER_PID=$!

# Wait (with a deadline) for Kater to become locally healthy before exposing it.
wait_for_health() {
    local url="$1" deadline label pid
    deadline=$((SECONDS + 30))
    label="$2"
    pid="$3"
    until curl -fsS "$url" >/dev/null 2>&1; do
        if [[ $SECONDS -ge $deadline ]]; then
            echo "ERROR: $label did not become healthy within 30s. Check logs above."
            kill "$pid" 2>/dev/null || true
            return 1
        fi
        sleep 1
    done
    echo "$label healthy at $url"
}

if ! wait_for_health "http://127.0.0.1:9091/health" "Kater" "$KATER_PID"; then
    exit 1
fi

cloudflared tunnel --config "$CONFIG_FILE" run "$TUNNEL_NAME" &
TUNNEL_PID=$!

# Deadline-based wait for the public tunnel endpoint to serve a healthy Kater.
if ! wait_for_health "https://$DOMAIN/health" "Tunnel ($DOMAIN)" "$TUNNEL_PID"; then
    exit 1
fi

echo ""
echo "Kater PID: $KATER_PID"
echo "Tunnel PID: $TUNNEL_PID"
echo ""
echo "Dashboard: http://127.0.0.1:9091"
echo "MCP SSE:   https://$DOMAIN/sse"
echo ""
if [[ "$AUTH_MODE" == "oauth" ]]; then
    echo "ChatGPT: paste https://$DOMAIN/sse — OAuth flow starts automatically."
else
    echo "Cursor/agents: use Authorization: Bearer \$KATER_API_KEY on /sse requests."
fi
echo ""
echo "Press Ctrl+C to stop..."

trap "kill $KATER_PID $TUNNEL_PID 2>/dev/null || true" EXIT
wait
