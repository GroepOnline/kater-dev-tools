from __future__ import annotations

from kater.envfile import resolve_use_proxy
from kater.settings import ListenConfig


def serve_unified(
    *,
    profile: str = "core",
    listen: ListenConfig | None = None,
    use_proxy: bool | None = None,
) -> None:
    """Run REST API, private MCP, WebSocket and optional product MCP in one process.

    All enabled listeners bind the same host (``listen.host``). The default is
    loopback-only; pass a ListenConfig with an explicit host to expose them.
    """
    from kater.runtime import KaterRuntime

    if use_proxy is None:
        use_proxy = resolve_use_proxy(profile=profile)

    KaterRuntime(profile=profile, listen=listen, use_proxy=use_proxy).run_until_signal()
