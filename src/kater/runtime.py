from __future__ import annotations

import logging
import os
import signal
import threading
import time
from http.server import ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

import uvicorn

from kater.settings import ListenConfig

_log = logging.getLogger("kater.runtime")

# Light janitor wake (browser reap + automations tick). Short enough that a
# 1-minute automation schedule can actually fire.
_TICK_INTERVAL = 60.0
# Heavy work (oauth cleanup, telemetry prune, control-plane prune) runs every
# N light wakes, or sooner if wall-clock since the last heavy pass exceeds
# ``_HEAVY_INTERVAL`` (covers a wake that was interrupted early).
_HEAVY_EVERY_N_TICKS = 10
_HEAVY_INTERVAL = 600.0


def _should_run_heavy(iteration: int, elapsed_since_heavy: float = 0.0) -> bool:
    """Return True when the expensive janitor pass should run this wake."""
    if iteration > 0 and iteration % _HEAVY_EVERY_N_TICKS == 0:
        return True
    return elapsed_since_heavy >= _HEAVY_INTERVAL


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

        from kater.migrations import ensure_migrated

        try:
            ensure_migrated()
        except Exception as exc:
            _log.warning("schema migrate failed: %s", exc)

        try:
            from kater.automations import get_engine

            get_engine().ensure_defaults()
        except Exception as exc:
            _log.warning("automations ensure_defaults failed: %s", exc)

        if self._use_proxy:
            try:
                from kater.proxy import get_proxy

                get_proxy().start(self._profile)
            except Exception as exc:
                _log.warning("proxy startup failed: %s", exc)

        # Computer lane: standalone HTTP guest connector (works with or without proxy).
        try:
            from kater.capabilities.wiring import (
                build_computer_connector,
                set_computer_connector,
            )

            connector = build_computer_connector(self._profile)
            if connector is not None:
                set_computer_connector(connector)
                if self._use_proxy:
                    from kater.proxy import get_proxy

                    get_proxy().register_computer_connector(connector)
                host = urlsplit(connector.base_url).hostname or ""
                _log.info(
                    "computer connector active (profile=%s, host=%s)",
                    connector.profile,
                    host,
                )
        except Exception as exc:
            _log.warning("computer connector setup failed: %s", exc)

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

    def _run_light_janitor(self) -> None:
        """Browser reap + automations tick — every wake."""
        try:
            from kater.browser.session import get_manager

            closed = get_manager().reap_expired()
            if closed:
                _log.info("janitor: reaped %d expired browser sessions", closed)
        except Exception as exc:
            _log.warning("janitor: browser reap failed: %s", exc)
        try:
            from kater.automations import get_engine

            get_engine().ensure_defaults()
            ran = get_engine().tick()
            if ran:
                _log.info("janitor: ran %d automations", ran)
        except Exception as exc:
            _log.warning("janitor: automations tick failed: %s", exc)

    def _run_heavy_janitor(self) -> None:
        """
        Run infrequent maintenance for expired OAuth records, telemetry storage, and control-plane state.
        
        Each maintenance category is handled independently so a failure in one does not prevent the others from running.
        """
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
            from kater.control_plane.usage import prune_usage_events

            prune_control_plane_state()
            removed = prune_usage_events()
            if removed:
                _log.info("janitor: pruned %d usage ledger rows", removed)
        except Exception as exc:
            _log.warning("janitor: control-plane prune failed: %s", exc)

    def _maintenance_loop(self) -> None:
        """Wake often for automations; run heavier sweeps on a longer cadence."""
        iteration = 0
        last_heavy = time.monotonic()
        while not self._shutdown_event.is_set():
            self._shutdown_event.wait(_TICK_INTERVAL)
            if self._shutdown_event.is_set():
                break
            iteration += 1
            self._run_light_janitor()
            elapsed = time.monotonic() - last_heavy
            if _should_run_heavy(iteration, elapsed):
                self._run_heavy_janitor()
                last_heavy = time.monotonic()

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

        try:
            from kater.browser.session import reset_manager

            reset_manager()
        except Exception as exc:
            _log.warning("browser shutdown failed: %s", exc)

        try:
            from kater.capabilities.wiring import reset_computer_connector

            reset_computer_connector()
        except Exception as exc:
            _log.warning("computer connector shutdown failed: %s", exc)

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
