#!/usr/bin/env sh
set -eu

BASE="${KATER_HEALTH_URL:-http://127.0.0.1:9091}"

curl -fsS "${BASE}/health" >/dev/null
curl -fsS "${BASE}/health/live" >/dev/null
curl -fsS "${BASE}/health/ready" >/dev/null

echo "dev-health ok (${BASE})"
