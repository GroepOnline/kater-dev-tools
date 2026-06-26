#!/usr/bin/env bash
# Ensure Kater + Cloudflare tunnel are online.
set -eu

systemctl --user daemon-reload
systemctl --user restart kater.service
sleep 2
systemctl --user restart kater-cloudflared.service
sleep 3

if curl -4 -sf "https://kater.chefgroep.online/health" >/dev/null; then
  echo "OK: https://kater.chefgroep.online/dashboard"
  exit 0
fi

echo "ERROR: public health check failed" >&2
systemctl --user status kater.service kater-cloudflared.service --no-pager >&2
exit 1
