#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Correctness backpressure: tests + lint must pass before a result may be kept.
uv run pytest -q 2>&1 | tail -15
uv run ruff check src 2>&1 | tail -5