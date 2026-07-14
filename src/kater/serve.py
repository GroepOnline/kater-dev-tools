from __future__ import annotations

from kater.envfile import resolve_use_proxy
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
        use_proxy = resolve_use_proxy(profile=profile)

    KaterRuntime(profile=profile, listen=listen, use_proxy=use_proxy).run_until_signal()
