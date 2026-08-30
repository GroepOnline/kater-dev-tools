#!/usr/bin/env python3
"""Rerunnable structural proof for Kater's search -> execute agent surface."""

from kater.openapi_spec import generate_spec
from kater.registry import build_native_tools

EXPECTED_TOOLS = {"kater_tool_search", "kater_execute"}
EXPECTED_PATHS = {"/api/tools/search", "/api/execute"}


def main() -> int:
    native = {tool.name for tool in build_native_tools()}
    missing_tools = EXPECTED_TOOLS - native
    paths = set(generate_spec()["paths"])
    missing_paths = EXPECTED_PATHS - paths
    if missing_tools or missing_paths:
        detail = f"tools={sorted(missing_tools)} paths={sorted(missing_paths)}"
        raise SystemExit(f"executor contract incomplete: {detail}")
    print("executor-contract: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
