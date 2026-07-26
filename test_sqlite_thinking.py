#!/usr/bin/env python3
"""Test sqlite and sequential-thinking tools through Kater gateway."""
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

            backends = {}
            for t in tools.tools:
                prefix = t.name.split("__")[0] if "__" in t.name else "kater"
                backends.setdefault(prefix, []).append(t.name)
            print(f"   Backends loaded: {sorted(backends.keys())}")

            sqlite_tools = [t for t in tools.tools if t.name.startswith("sqlite")]
            print(f"   sqlite tools available: {len(sqlite_tools)}")
            for t in sqlite_tools[:3]:
                print(f"     - {t.name}: {(t.description or '')[:80]}")

            print("\n--- Test 1: SQLite ---")
            if sqlite_tools:
                # Try a list_tables or similar basic operation
                # The sqlite MCP server typically provides: list_tables, execute_sql, etc.
                target_tool = sqlite_tools[0].name
                print(f"4. Calling {target_tool}...")
                try:
                    result = await session.call_tool(target_tool, {})
                    for c in result.content:
                        print(f"   Response: {c.text[:300]}")
                    print("\n✅ sqlite tool call worked!")
                except Exception as e:
                    print(f"   Error: {e}")
            else:
                print("   sqlite backend not loaded in this profile. Trying to find sequential-thinking...")
                st_tools = [t for t in tools.tools if "thinking" in t.name.lower()]
                print(f"   sequential-thinking tools: {len(st_tools)}")
                if st_tools:
                    print("\n--- Test 2: Sequential Thinking ---")
                    target_tool = st_tools[0].name
                    print(f"4. Calling {target_tool}...")
                    try:
                        result = await session.call_tool(target_tool, {"thought": "Testing the proxy.", "thoughtNumber": 1, "totalThoughts": 1, "nextThoughtNeeded": False})
                        for c in result.content:
                            print(f"   Response: {c.text[:300]}")
                        print("\n✅ sequential-thinking call worked!")
                    except Exception as e:
                        print(f"   Error: {e}")
                else:
                    print("\n⚠️  Neither sqlite nor sequential-thinking tools visible.")
                    print("   Available prefixes:", sorted(backends.keys()))

asyncio.run(test())
