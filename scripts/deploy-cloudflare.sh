#!/usr/bin/env bash
set -eu

DOMAIN="${1:-kater.chefgroep.online}"
TUNNEL_NAME="${2:-kater}"
CONFIG_DIR="$HOME/.cloudflared"
CONFIG_FILE="$CONFIG_DIR/${TUNNEL_NAME}.yml"

echo "=== Kater Cloudflare Deploy ==="
echo "Domain: $DOMAIN"
echo "Tunnel: $TUNNEL_NAME"
echo ""

if ! command -v cloudflared &>/dev/null; then
    echo "ERROR: cloudflared not installed"
    echo "  brew install cloudflared"
    echo "  or: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
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
kater tunnel config -p cloudflare --domain "$DOMAIN" > "$CONFIG_FILE"

echo ""
echo "Config written to: $CONFIG_FILE"
echo ""
echo "Starting Kater + tunnel..."
echo ""

kater serve &
KATER_PID=$!
sleep 2

cloudflared tunnel --config "$CONFIG_FILE" run "$TUNNEL_NAME" &
TUNNEL_PID=$!

echo ""
echo "Kater PID: $KATER_PID"
echo "Tunnel PID: $TUNNEL_PID"
echo ""
echo "Dashboard: http://localhost:9091"
echo "MCP SSE:   https://$DOMAIN/sse"
echo ""
echo "ChatGPT config:"
echo "  MCP Server URL: https://$DOMAIN/sse"
echo "  (OAuth flow will start automatically)"
echo ""
echo "Press Ctrl+C to stop..."

trap "kill $KATER_PID $TUNNEL_PID 2>/dev/null || true" EXIT
wait
