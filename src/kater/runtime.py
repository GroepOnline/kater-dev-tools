from __future__ import annotations

import os
import signal
import threading
from typing import Any

import uvicorn

from kater.settings import ListenConfig


class KaterRuntime:
    """Owns ordered startup and shutdown for the unified Kater process."""

    def __init__(
        self,
        *,
        profile: str = "core",
        listen: ListenConfig | None = None,
        use_proxy: bool = False,
    ) -> None:
        self._profile = profile
        self._listen = listen or ListenConfig()
        self._use_proxy = use_proxy
        self._started = False
        self._shutdown_event = threading.Event()
        self._api_server: Any = None
        self._api_thread: threading.Thread | None = None
        self._ws_server: Any = None
        self._ws_thread: threading.Thread | None = None
        self._mcp_uvicorn: uvicorn.Server | None = None
        self._mcp_thread: threading.Thread | None = None

    def start(self) -> None:
        if self._started:
            return

        os.environ["KATER_PROFILE"] = self._profile

        if self._use_proxy:
            try:
                from kater.proxy import get_proxy

                get_proxy().start(self._profile)
            except Exception:
                pass

        from kater.api import create_api_server
        from kater.mcp_server import build_sse_app
        from kater.websocket import create_ws_server

        self._api_server = create_api_server(self._listen.host, self._listen.api_port)
        self._api_thread = threading.Thread(
            target=self._api_server.serve_forever,
            daemon=True,
        )
        self._api_thread.start()

        self._ws_server = create_ws_server(self._listen.host, self._listen.ws_port)
        self._ws_thread = threading.Thread(
            target=self._ws_server.serve_forever,
            daemon=True,
        )
        self._ws_thread.start()

        mcp_app = build_sse_app(profile=self._profile, use_proxy=self._use_proxy)
        config = uvicorn.Config(
            mcp_app,
            host=self._listen.host,
            port=self._listen.mcp_port,
            log_level="warning",
        )
        self._mcp_uvicorn = uvicorn.Server(config)
        self._mcp_thread = threading.Thread(
            target=self._mcp_uvicorn.run,
            daemon=True,
        )
        self._mcp_thread.start()

        self._started = True

    def stop(self, timeout: float = 5.0) -> None:
        del timeout  # reserved for future thread joins
        if not self._started:
            return

        if self._mcp_uvicorn is not None:
            try:
                self._mcp_uvicorn.should_exit = True
            except Exception:
                pass

        if self._ws_server is not None:
            try:
                self._ws_server.shutdown()
                self._ws_server.server_close()
            except Exception:
                pass

        if self._api_server is not None:
            try:
                self._api_server.shutdown()
                self._api_server.server_close()
            except Exception:
                pass

        if self._use_proxy:
            try:
                from kater.proxy import get_proxy

                get_proxy().stop()
            except Exception:
                pass

        self._started = False

    def run_until_signal(self) -> None:
        self.start()

        def _handle_signal(signum: int, frame: Any) -> None:
            del signum, frame
            self.stop()
            self._shutdown_event.set()

        previous_sigint = signal.signal(signal.SIGINT, _handle_signal)
        previous_sigterm = signal.signal(signal.SIGTERM, _handle_signal)
        try:
            self._shutdown_event.wait()
        finally:
            signal.signal(signal.SIGINT, previous_sigint)
            signal.signal(signal.SIGTERM, previous_sigterm)
            self.stop()

    def __enter__(self) -> KaterRuntime:
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()
