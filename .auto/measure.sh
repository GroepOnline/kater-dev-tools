#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Cold-start bucket timing (whole python process).
T0_MS=$(date +%s%3N)

# Kater Dev MCP — offline tool-surface battery.
# Emits METRIC name=value lines. No live gateway/auth calls.

uv run python - <<'PY'
import json, sys, time

t0 = time.perf_counter()

# 1. Registry walk: every tool def must carry name + description (MCP tool-call quality).
from kater.registry import build_native_tools, tools_for_profile

builtins = build_native_tools()
core = tools_for_profile("core")

t_boot = time.perf_counter()

# 2. Boot the MCP app surface if it exposes list_tools (guarded: proxy/ext deps).
app_tools_listed = -1
from kater.mcp_server import create_server  # type: ignore
try:
    app = create_server(profile="core")
    try:
        tools = app.list_tools()
        app_tools_listed = len(tools)
    except AttributeError:
        app_tools_listed = 0
except Exception as exc:
    app_tools_listed = -1

t_end = time.perf_counter()

boot_ms = (t_boot - t0) * 1000
walk_ms = (t_end - t_boot) * 1000

t_total = len(builtins)
t_descr = sum(1 for t in builtins if (t.description or "").strip())
lat_descr = sum(len(t.description) for t in builtins)

print(f"METRIC boot_ms={boot_ms:.2f}")
print(f"METRIC registry_walk_ms={walk_ms:.2f}")
print(f"METRIC tool_count={t_total}")
print(f"METRIC described_tools={t_descr}")
print(f"METRIC description_ratio={(t_descr / max(t_total, 1)):.4f}")
print(f"METRIC avg_description_chars={(lat_descr / max(t_descr, 1)):.1f}")
print(f"METRIC app_tools_listed={app_tools_listed}")
print(f"METRIC core_profile_tools={len(core)}")
print(json.dumps({"_battery": "kater-mcp-toolsurface", "sample": [t.name for t in builtins[:3]]}))
PY

T1_MS=$(date +%s%3N)
COLD_MS=$((T1_MS - T0_MS))
echo "METRIC cold_ms=${COLD_MS}"