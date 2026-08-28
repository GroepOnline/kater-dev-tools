#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Kater Dev MCP — offline tool-surface battery.
# Emits METRIC name=value lines. No live gateway/auth calls.

uv run python - <<'PY'
import json, sys, time

t0 = time.perf_counter()

# 1. Boot the MCP app and list its tool surface (schema quality + count).
from kater.mcp_server import load_server_app  # type: ignore
app = load_server_app()
try:
    tools = app.list_tools()
except AttributeError:
    # FastMCP 2.x renamed internals; fall back to the registry walk.
    tools = []

t_boot = time.perf_counter()

# 2. Registry walk: every profile's tool defs must carry name+description+schema.
from kater.registry import tools_for_profile
from kater.profiles import all_tool_sources

t_names = 0
t_descr = 0
t_schema = 0
t_total_defs = 0
lat_descr = 0.0
for src in all_tool_sources():
    for name, fn in src.tools.items():
        t_total_defs += 1
        descr = getattr(fn, "__doc__", "") or ""
        if descr.strip():
            t_descr += 1
            lat_descr += len(descr)
        import inspect
        try:
            sig = inspect.signature(fn)
            t_schema += 1 if len(sig.parameters) > 0 else 0 if True else 0
        except (ValueError, TypeError):
            pass

t_end = time.perf_counter()

boot_ms = (t_boot - t0) * 1000
walk_ms = (t_end - t_boot) * 1000

print(f"METRIC boot_ms={boot_ms:.1f}")
print(f"METRIC registry_walk_ms={walk_ms:.1f}")
print(f"METRIC tool_count={t_total_defs}")
print(f"METRIC described_tools={t_descr}")
print(f"METRIC avg_description_chars={(lat_descr / max(t_descr, 1)):.1f}")
print(f"METRIC app_tools_listed={len(tools)}")
print(json.dumps({"_battery": "kater-mcp-toolsurface", "profiles": list(all_tool_sources())}))
PY