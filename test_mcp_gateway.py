#!/usr/bin/env python3
"""Test MCP tool call through Kater gateway SSE endpoint."""
import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:9090"
AUTH = "Bearer kat_preview_kater_2026"

# Step 1: Connect to SSE to get session endpoint
print("1. Connecting to SSE endpoint...")
req = urllib.request.Request(f"{BASE}/sse", headers={"Authorization": AUTH})
resp = urllib.request.urlopen(req, timeout=30)
endpoint_url = None
for _ in range(20):
    line = resp.readline().decode()
    if line.startswith("data:"):
        data = line[5:].strip()
        if data.startswith("http"):
            endpoint_url = data
            print(f"   Session endpoint: {endpoint_url}")
            break
    if not line:
        break

if not endpoint_url:
    print("ERROR: No session endpoint received from SSE")
    sys.exit(1)

# Step 2: Send initialize request
print("2. Sending initialize...")
init_msg = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "kater-test", "version": "1.0.0"}
    }
}
data = json.dumps(init_msg).encode()
req = urllib.request.Request(
    endpoint_url,
    data=data,
    headers={"Authorization": AUTH, "Content-Type": "application/json"},
    method="POST"
)
resp = urllib.request.urlopen(req, timeout=10)
print(f"   Status: {resp.status}")

# Step 3: Send initialized notification
print("3. Sending initialized notification...")
notif = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
data = json.dumps(notif).encode()
req = urllib.request.Request(
    endpoint_url,
    data=data,
    headers={"Authorization": AUTH, "Content-Type": "application/json"},
    method="POST"
)
urllib.request.urlopen(req, timeout=10)

# Step 4: List tools
print("4. Listing tools...")
list_msg = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
data = json.dumps(list_msg).encode()
req = urllib.request.Request(
    endpoint_url,
    data=data,
    headers={"Authorization": AUTH, "Content-Type": "application/json"},
    method="POST"
)
resp = urllib.request.urlopen(req, timeout=10)
time.sleep(2)
tools_found = []
for _ in range(30):
    line = resp.readline().decode()
    if line.startswith("data:"):
        try:
            result = json.loads(line[5:].strip())
            if "result" in result and "tools" in result["result"]:
                tools_found = result["result"]["tools"]
                break
        except json.JSONDecodeError:
            pass

if tools_found:
    print(f"   Found {len(tools_found)} tool(s):")
    for t in tools_found:
        print(f"     - {t['name']}: {t.get('description', '')[:80]}")
else:
    print("   No tools found in response")

# Step 5: Call sequential_thinking tool
print("5. Calling sequential_thinking tool...")
call_msg = {
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
        "name": "sequentialthinking",
        "arguments": {
            "thought": "Testing that the Kater gateway can proxy MCP tool calls end-to-end. This is a verification step.",
            "thoughtNumber": 1,
            "totalThoughts": 1,
            "nextThoughtNeeded": False
        }
    }
}
data = json.dumps(call_msg).encode()
req = urllib.request.Request(
    endpoint_url,
    data=data,
    headers={"Authorization": AUTH, "Content-Type": "application/json"},
    method="POST"
)
resp = urllib.request.urlopen(req, timeout=30)
print(f"   Status: {resp.status}")

time.sleep(3)
for _ in range(30):
    line = resp.readline().decode()
    if line.startswith("data:"):
        try:
            result = json.loads(line[5:].strip())
            if result.get("id") == 3:
                if "result" in result:
                    content = result["result"].get("content", [])
                    for c in content:
                        text = c.get("text", "")
                        print(f"   Tool response: {text[:200]}")
                    print("\n✅ SUCCESS: MCP tool call completed through Kater gateway!")
                elif "error" in result:
                    print(f"   Error: {result['error']}")
                    print("\n❌ FAILED: Tool call returned an error")
                sys.exit(0)
        except json.JSONDecodeError:
            pass

print("\n⚠️  No response received within timeout")
resp.close()
