#!/usr/bin/env sh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MODE="${1:-}"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "created .env from .env.example"
fi

case "$MODE" in
  ""|compose)
    docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
    ;;
  native)
    if ! command -v uv >/dev/null 2>&1; then
      echo "uv not found; install from https://docs.astral.sh/uv/ or use: ./scripts/dev-boot.sh compose" >&2
      exit 1
    fi
    uv sync --dev
    if curl -sf --max-time 2 http://127.0.0.1:9091/health >/dev/null 2>&1; then
      echo "kater already listening on :9091"
    else
      echo "start gateway: uv run kater serve --profile core --no-proxy --host 127.0.0.1"
      exec uv run kater serve --profile core --no-proxy --host 127.0.0.1
    fi
    ;;
  *)
    echo "usage: $0 [compose|native]" >&2
    echo "  compose (default) — docker compose dev stack" >&2
    echo "  native            — uv sync + kater serve on loopback" >&2
    exit 2
    ;;
esac

if [ "$MODE" = "" ] || [ "$MODE" = "compose" ]; then
  for _ in $(seq 1 30); do
    if curl -sf --max-time 2 http://127.0.0.1:9091/health >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  ./scripts/dev-health.sh
fi
