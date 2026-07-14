from __future__ import annotations

import logging
import os
import signal
import threading
from http.server import ThreadingHTTPServer
from typing import Any

import uvicorn

from kater.settings import ListenConfig

_log = logging.getLogger("kater.runtime")

# How often the background janitor sweeps expired OAuth tokens/codes and prunes
# persisted telemetry and control-plane state. These are cheap, so 10 minutes is plenty.
_MAINTENANCE_INTERVAL = 600.0


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
        self._api_server: ThreadingHTTPServer | None = None
        self._api_thread: threading.Thread | None = None
        self._ws_server: ThreadingHTTPServer | None = None
        self._ws_thread: threading.Thread | None = None
        self._mcp_uvicorn: uvicorn.Server | None = None
        self._mcp_thread: threading.Thread | None = None
        self._maintenance_thread: threading.Thread | None = None

    def start(self) -> None:
        if self._started:
            return

        os.environ["KATER_PROFILE"] = self._profile

        # Project secrets + dashboard-persisted credentials before proxy start.
        from kater.envfile import load_project_env
        from kater.settings import load_settings

        load_project_env()
        load_settings().apply_credentials_to_env()

        if self._use_proxy:
            try:
                from kater.proxy import get_proxy

                get_proxy().start(self._profile)
            except Exception as exc:
                _log.warning("proxy startup failed: %s", exc)

        from kater.api import create_api_server
        from kater.mcp_server import build_sse_app
        from kater.websocket import create_ws_server

        self._api_server = create_api_server(self._listen.host, self._listen.api_port)
        self._api_thread = threading.Thread(
            target=self._api_server.serve_forever,
            daemon=True,
            name="kater-api",
        )
        self._api_thread.start()

        self._ws_server = create_ws_server(self._listen.host, self._listen.ws_port)
        self._ws_thread = threading.Thread(
            target=self._ws_server.serve_forever,
            daemon=True,
            name="kater-ws",
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
            name="kater-mcp",
        )
        self._mcp_thread.start()

        self._maintenance_thread = threading.Thread(
            target=self._maintenance_loop,
            daemon=True,
            name="kater-janitor",
        )
        self._maintenance_thread.start()

        self._started = True

    def _maintenance_loop(self) -> None:
        """Periodically purge expired state and enforce persisted row caps."""
        while not self._shutdown_event.is_set():
            self._shutdown_event.wait(_MAINTENANCE_INTERVAL)
            if self._shutdown_event.is_set():
                break
            try:
                from kater.oauth import cleanup_expired

                removed = cleanup_expired()
                if removed:
                    _log.info("janitor: purged %d expired OAuth entries", removed)
            except Exception as exc:
                _log.warning("janitor: oauth cleanup failed: %s", exc)
            try:
                from kater.storage import prune_all

                prune_all()
            except Exception as exc:
                _log.warning("janitor: telemetry prune failed: %s", exc)
            try:
                from kater.control_plane import prune_control_plane_state

                prune_control_plane_state()
            except Exception as exc:
                _log.warning("janitor: control-plane prune failed: %s", exc)

    def stop(self, timeout: float = 5.0) -> None:
        if not self._started:
            return

        self._shutdown_event.set()

        if self._mcp_uvicorn is not None:
            try:
                self._mcp_uvicorn.should_exit = True
            except Exception as exc:
                _log.warning("mcp shutdown signal failed: %s", exc)

        if self._ws_server is not None:
            try:
                self._ws_server.shutdown()
                self._ws_server.server_close()
            except Exception as exc:
                _log.warning("ws shutdown failed: %s", exc)

        if self._api_server is not None:
            try:
                self._api_server.shutdown()
                self._api_server.server_close()
            except Exception as exc:
                _log.warning("api shutdown failed: %s", exc)

        if self._use_proxy:
            try:
                from kater.proxy import get_proxy

                get_proxy().stop()
            except Exception as exc:
                _log.warning("proxy shutdown failed: %s", exc)

        # Join worker threads so stop() blocks until in-flight requests drain.
        for thread in (self._api_thread, self._ws_thread, self._mcp_thread):
            if thread is not None and thread.is_alive():
                thread.join(timeout=timeout)
        if self._maintenance_thread is not None and self._maintenance_thread.is_alive():
            self._maintenance_thread.join(timeout=2.0)

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
