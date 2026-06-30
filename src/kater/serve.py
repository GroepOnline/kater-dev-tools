from __future__ import annotations

import os

from kater.settings import ListenConfig


def serve_unified(
    *,
    profile: str = "core",
    listen: ListenConfig | None = None,
    use_proxy: bool | None = None,
) -> None:
    """Run the REST API, MCP SSE server, and WebSocket in one process.

    All three servers bind the same host (``listen.host``). The default is
    loopback-only; pass a ListenConfig with an explicit host to expose them.
    """
    from kater.runtime import KaterRuntime

    if use_proxy is None:
        use_proxy = os.environ.get("KATER_PROXY", "0") == "1"

    KaterRuntime(profile=profile, listen=listen, use_proxy=use_proxy).run_until_signal()
