from __future__ import annotations

from kater.settings import ListenConfig


def serve_unified(
    *,
    profile: str = "core",
    listen: ListenConfig | None = None,
) -> None:
    """Run the REST API, MCP SSE server, and WebSocket in one process.

    All three servers bind the same host (``listen.host``). The default is
    loopback-only; pass a ListenConfig with an explicit host to expose them.
    """
    from kater.runtime import KaterRuntime

    KaterRuntime(profile=profile, listen=listen).run_until_signal()
