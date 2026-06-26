from __future__ import annotations

import threading


def serve_unified(
    *,
    profile: str = "core",
    api_host: str = "0.0.0.0",
    api_port: int = 9091,
    mcp_host: str = "0.0.0.0",
    mcp_port: int = 9090,
    ws_host: str = "0.0.0.0",
    ws_port: int = 9092,
) -> None:
    """Run the REST API, MCP SSE server, and WebSocket in one process."""
    import os

    os.environ["KATER_PROFILE"] = profile

    from kater.api import create_api_server
    from kater.mcp_server import create_server
    from kater.websocket import create_ws_server

    api_server = create_api_server(api_host, api_port)
    api_thread = threading.Thread(target=api_server.serve_forever, daemon=True)
    api_thread.start()

    ws_server = create_ws_server(ws_host, ws_port)
    ws_thread = threading.Thread(target=ws_server.serve_forever, daemon=True)
    ws_thread.start()

    mcp_server = create_server(profile=profile)
    mcp_server.settings.host = mcp_host
    mcp_server.settings.port = mcp_port
    mcp_server.run()
