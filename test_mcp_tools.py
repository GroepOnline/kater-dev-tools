#!/usr/bin/env python3
"""Test calling actual proxied MCP tools through Kater gateway."""
import asyncio
import sys
sys.path.insert(0, ".venv/lib/python3.14/site-packages")

from mcp import ClientSession
from mcp.client.sse import sse_client

async def test():
    url = "http://127.0.0.1:9090/sse"
    headers = {"Authorization": "Bearer kat_preview_kater_2026"}

    print("1. Connecting to SSE endpoint...")
    async with sse_client(url, headers=headers) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            print("2. Initializing MCP session...")
            await session.initialize()

            print("3. Listing available tools...")
            tools = await session.list_tools()
            print(f"   Found {len(tools.tools)} tool(s)")

            # Find a tool from each backend
            print("\n--- Available tool names by backend ---")
            backends = {}
            for t in tools.tools:
                prefix = t.name.split("__")[0] if "__" in t.name else "kater"
                backends.setdefault(prefix, []).append(t.name)
            for prefix, names in sorted(backends.items()):
                print(f"  {prefix}: {len(names)} tools (e.g. {names[0]})")

            # Test 1: time tool
            print("\n4. Calling time__get_current_time...")
            result = await session.call_tool("time__get_current_time", {})
            for c in result.content:
                print(f"   Response: {c.text[:200]}")

            # Test 2: memory tool
            print("\n5. Calling memory__read_graph...")
            result = await session.call_tool("memory__read_graph", {})
            for c in result.content:
                print(f"   Response: {c.text[:200]}")

            # Test 3: filesystem tool
            print("\n6. Calling filesystem__list_allowed_directories...")
            result = await session.call_tool("filesystem__list_allowed_directories", {})
            for c in result.content:
                print(f"   Response: {c.text[:200]}")

            print("\n✅ SUCCESS: All MCP tool calls completed end-to-end!")

asyncio.run(test())
