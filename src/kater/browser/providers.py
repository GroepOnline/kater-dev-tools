"""Browser backends for the native browser lane.

Three interchangeable backends share one surface:

* ``PlaywrightProvider`` launches a local headless Chromium.
* ``CdpProvider`` attaches to any Chrome DevTools Protocol endpoint.
* ``SteelProvider`` drives Steel Browser (https://github.com/steel-dev/steel-browser),
  the supported open-source agent-browser backend: it creates a session over
  the REST API, then attaches to the CDP url that session hands back.

Playwright is an optional dependency. It is imported lazily inside
``start()``; importing this module never pulls it in, and a missing install
surfaces as :class:`BrowserUnavailableError`.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from typing import Any

from kater.browser.actions import execute_action
from kater.browser.base import (
    DEFAULT_STEEL_URL,
    ENV_ALLOW_EVALUATE,
    ENV_CDP_URL,
    ENV_NO_SANDBOX,
    ENV_PROVIDER,
    ENV_STEEL_KEY,
    ENV_STEEL_URL,
    BrowserProvider,
    BrowserUnavailableError,
    PageHandle,
    ProviderInfo,
    browsers_root,
    env_truthy,
    launch_args,
    redact_endpoint,
)
from kater.browser.models import ActionResult, BrowserAction, BrowserSession, ProviderKind
from kater.browser.network import install_network_guard, validate_cdp_endpoint
from kater.browser.policy import BrowserPolicy, load_policy
from kater.browser.probe import probe_cdp, probe_local, probe_providers, probe_steel
from kater.browser.runner import CallRunner
from kater.settings import KaterSettings

__all__ = [
    "DEFAULT_STEEL_URL",
    "ENV_ALLOW_EVALUATE",
    "ENV_CDP_URL",
    "ENV_NO_SANDBOX",
    "ENV_PROVIDER",
    "ENV_STEEL_KEY",
    "ENV_STEEL_URL",
    "BrowserProvider",
    "BrowserUnavailableError",
    "CdpProvider",
    "PageHandle",
    "PlaywrightProvider",
    "ProviderInfo",
    "SteelProvider",
    "browsers_root",
    "launch_args",
    "probe_cdp",
    "probe_local",
    "probe_providers",
    "probe_steel",
    "resolve_provider",
]

STEEL_HTTP_TIMEOUT = 10.0
# Slack added to the per-action deadline so the provider's own watchdog only
# fires when Playwright's internal timeout has already failed to.
ACTION_TIMEOUT_SLACK_SECONDS = 5.0

_CDP_URL_KEYS = (
    "websocketUrl",
    "webSocketDebuggerUrl",
    "wsEndpoint",
    "cdpUrl",
    "connectUrl",
    "debugUrl",
)


class PlaywrightProvider(BrowserProvider):
    """Local headless Chromium managed by Playwright.

    Every driver call is funnelled through one worker thread: the Playwright
    sync API is bound to the thread that created it, while Kater serves
    requests from a pool.
    """

    kind = ProviderKind.LOCAL

    def __init__(self, *, headless: bool = True, allow_evaluate: bool = False) -> None:
        self.headless = headless
        self.allow_evaluate = allow_evaluate
        self._runner = CallRunner(name=f"kater-browser-{self.kind.value}")
        self._lock = threading.RLock()
        self._playwright: Any = None
        self._browser: Any = None
        # Session manager cannot always pass policy into new_page; act() sets
        # this so the network guard sees the active session policy.
        self._guard_policy: BrowserPolicy | None = None

    # ── lifecycle ──────────────────────────────────────────────────

    def start(self) -> None:
        with self._lock:
            if self._browser is not None:
                return
            self._submit(self._start_on_worker)

    def _start_on_worker(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserUnavailableError(
                "playwright is not installed; install it with "
                "'uv pip install playwright && playwright install chromium'"
            ) from exc
        playwright = sync_playwright().start()
        try:
            self._browser = self._connect(playwright)
        except Exception as exc:
            _quiet(playwright.stop)
            raise BrowserUnavailableError(f"could not start browser: {exc}") from exc
        self._playwright = playwright

    def _connect(self, playwright: Any) -> Any:
        return playwright.chromium.launch(headless=self.headless, args=launch_args())

    def stop(self) -> None:
        with self._lock:
            if self._browser is None and self._playwright is None:
                self._runner.stop()
                return
            if self._runner.running:
                _quiet(lambda: self._submit(self._stop_on_worker, timeout=20.0))
            self._browser = None
            self._playwright = None
            self._runner.stop()

    def _stop_on_worker(self) -> None:
        browser, playwright = self._browser, self._playwright
        self._browser = None
        self._playwright = None
        if browser is not None:
            _quiet(browser.close)
        if playwright is not None:
            _quiet(playwright.stop)

    def _invalidate_after_timeout(self) -> None:
        """Drop Playwright objects bound to a wedged worker thread.

        Closing them from another thread is unsafe; leaking one Chromium until
        process exit is preferable to wedging the lane forever. The next
        ``start()`` relaunches on the replacement worker.
        """
        with self._lock:
            self._browser = None
            self._playwright = None

    def _submit(self, fn: Any, *, timeout: float | None = None) -> Any:
        try:
            return self._runner.submit(fn, timeout=timeout)
        except TimeoutError:
            # Runner already replaced the wedged worker; drop thread-affine state.
            self._invalidate_after_timeout()
            raise

    # ── pages ──────────────────────────────────────────────────────

    def new_page(
        self, session: BrowserSession, policy: BrowserPolicy | None = None
    ) -> PageHandle:
        if policy is not None:
            self._guard_policy = policy
        self.start()
        return self._submit(lambda: self._new_page_on_worker(session), timeout=60.0)

    def _new_page_on_worker(self, session: BrowserSession) -> PageHandle:
        if self._browser is None:
            raise BrowserUnavailableError("browser is not running")
        context = self._browser.new_context(
            viewport={"width": session.viewport_width, "height": session.viewport_height},
            ignore_https_errors=False,
        )
        page = context.new_page()
        self._attach_guard(page)
        return PageHandle(session_id=session.session_id, context=context, page=page)

    def _attach_guard(self, page: Any) -> None:
        install_network_guard(page, lambda: self._guard_policy or load_policy())
        page.on("popup", lambda popup: self._attach_guard(popup))

    def close_page(self, handle: Any) -> None:
        if not isinstance(handle, PageHandle) or not self._runner.running:
            return
        _quiet(
            lambda: self._submit(lambda: self._close_page_on_worker(handle), timeout=20.0)
        )

    def _close_page_on_worker(self, handle: PageHandle) -> None:
        _quiet(handle.page.close)
        _quiet(handle.context.close)

    # ── actions ────────────────────────────────────────────────────

    def act(self, handle: Any, action: BrowserAction, policy: BrowserPolicy) -> ActionResult:
        if not isinstance(handle, PageHandle):
            raise TypeError(f"expected a PageHandle, got {type(handle).__name__}")
        self._guard_policy = policy
        budget_ms = min(
            float(action.timeout_ms or policy.action_timeout_ms),
            float(policy.action_timeout_ms),
        )
        deadline = budget_ms / 1000.0 + ACTION_TIMEOUT_SLACK_SECONDS
        return self._submit(
            lambda: execute_action(
                handle.page,
                action,
                policy,
                session_id=handle.session_id,
                allow_evaluate=self.allow_evaluate,
            ),
            timeout=deadline,
        )

    def info(self) -> ProviderInfo:
        if self._browser is not None:
            version = _quiet_value(lambda: str(self._browser.version))
            return ProviderInfo(self.kind, True, "chromium running", version)
        return probe_local()


class CdpProvider(PlaywrightProvider):
    """Attach to an existing Chrome DevTools Protocol endpoint.

    Covers Browserless, Steel Browser and a plain
    ``chrome --remote-debugging-port`` — anything that speaks CDP over a
    websocket. Nothing is connected until ``start()`` is called.
    """

    kind = ProviderKind.CDP

    def __init__(self, endpoint: str, *, allow_evaluate: bool = False) -> None:
        super().__init__(headless=True, allow_evaluate=allow_evaluate)
        self.endpoint = endpoint

    def _connect(self, playwright: Any) -> Any:
        if not self.endpoint:
            raise BrowserUnavailableError(
                f"no CDP endpoint configured; set {ENV_CDP_URL} to e.g. ws://localhost:9222"
            )
        endpoint = validate_cdp_endpoint(self.endpoint)
        return playwright.chromium.connect_over_cdp(endpoint)

    def _stop_on_worker(self) -> None:
        # CDP / Steel attach to a browser we do not own. browser.close() would
        # kill the remote Chrome (or the operator's debug session). Pages and
        # contexts are already disposed via close_page; only disconnect the
        # Playwright driver.
        self._browser = None
        playwright, self._playwright = self._playwright, None
        if playwright is not None:
            _quiet(playwright.stop)

    def info(self) -> ProviderInfo:
        safe = redact_endpoint(self.endpoint) if self.endpoint else ""
        if self._browser is not None:
            return ProviderInfo(self.kind, True, f"connected to {safe}")
        detail = f"endpoint {safe}" if safe else "no endpoint configured"
        return ProviderInfo(self.kind, bool(self.endpoint), detail)


class SteelProvider(CdpProvider):
    """Steel Browser: create a REST session, then attach to its CDP url."""

    kind = ProviderKind.REMOTE

    def __init__(
        self,
        base_url: str = DEFAULT_STEEL_URL,
        api_key: str | None = None,
        *,
        allow_evaluate: bool = False,
        timeout: float = STEEL_HTTP_TIMEOUT,
    ) -> None:
        super().__init__("", allow_evaluate=allow_evaluate)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._steel_session_id: str | None = None

    def start(self) -> None:
        with self._lock:
            if self._browser is not None:
                return
            if not self.endpoint:
                self.endpoint, self._steel_session_id = self._create_steel_session()
        super().start()

    def stop(self) -> None:
        try:
            super().stop()
        finally:
            session_id, self._steel_session_id = self._steel_session_id, None
            self.endpoint = ""
            if session_id:
                _quiet(lambda: self._release_steel_session(session_id))

    def info(self) -> ProviderInfo:
        safe = redact_endpoint(self.base_url)
        if self._browser is not None:
            return ProviderInfo(self.kind, True, f"steel session on {safe}")
        return ProviderInfo(self.kind, True, f"steel api {safe} (not started)")

    def _connect(self, playwright: Any) -> Any:
        if not self.endpoint:
            raise BrowserUnavailableError(
                f"steel session at {self.base_url} has no CDP endpoint"
            )
        endpoint = validate_cdp_endpoint(self.endpoint, steel_base_url=self.base_url)
        return playwright.chromium.connect_over_cdp(endpoint)

    def _create_steel_session(self) -> tuple[str, str | None]:
        payload = self._steel_request("POST", "/v1/sessions", body={})
        endpoint = _first_url(payload)
        if not endpoint:
            raise BrowserUnavailableError(
                f"steel session response from {self.base_url} carried no CDP url "
                f"(looked for {', '.join(_CDP_URL_KEYS)})"
            )
        endpoint = validate_cdp_endpoint(endpoint, steel_base_url=self.base_url)
        session_id = payload.get("id") or payload.get("sessionId")
        return endpoint, str(session_id) if session_id else None

    def _release_steel_session(self, session_id: str) -> None:
        self._steel_request("DELETE", f"/v1/sessions/{session_id}")

    def _steel_request(
        self, method: str, path: str, *, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if not url.startswith(("http://", "https://")):
            raise BrowserUnavailableError(f"steel base url must be http(s): {self.base_url!r}")
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(url, data=data, method=method)  # noqa: S310 — scheme checked
        request.add_header("Accept", "application/json")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        if self.api_key:
            request.add_header("x-api-key", self.api_key)
            request.add_header("Authorization", f"Bearer {self.api_key}")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                raw = response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise BrowserUnavailableError(
                f"steel browser at {self.base_url} is unreachable ({method} {path}): {exc}"
            ) from exc
        if not raw:
            return {}
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BrowserUnavailableError(
                f"steel browser at {self.base_url} returned a non-JSON response"
            ) from exc
        return parsed if isinstance(parsed, dict) else {}


def resolve_provider(
    kind: ProviderKind | str | None = None,
    *,
    settings: KaterSettings | None = None,
) -> BrowserProvider:
    """Build the configured provider. Defaults to a local Playwright Chromium."""
    del settings  # env is the source of truth for browser backend selection
    raw = kind.value if isinstance(kind, ProviderKind) else (kind or os.environ.get(ENV_PROVIDER))
    name = (raw or "local").strip().lower()
    allow_evaluate = env_truthy(ENV_ALLOW_EVALUATE)

    if name in ("local", "playwright", "chromium"):
        return PlaywrightProvider(allow_evaluate=allow_evaluate)
    if name == "cdp":
        endpoint = os.environ.get(ENV_CDP_URL, "").strip()
        if not endpoint:
            raise BrowserUnavailableError(
                f"provider 'cdp' requires {ENV_CDP_URL} (e.g. ws://localhost:9222)"
            )
        return CdpProvider(endpoint, allow_evaluate=allow_evaluate)
    if name in ("steel", "remote"):
        base_url = os.environ.get(ENV_STEEL_URL, "").strip() or DEFAULT_STEEL_URL
        api_key = os.environ.get(ENV_STEEL_KEY, "").strip() or None
        return SteelProvider(base_url, api_key, allow_evaluate=allow_evaluate)
    raise ValueError(f"unknown browser provider: {name!r} (expected local, cdp or steel)")


def _first_url(payload: dict[str, Any]) -> str:
    for key in _CDP_URL_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _quiet(fn: Any) -> None:
    try:
        fn()
    except Exception:  # noqa: S110 — teardown must not mask the original failure
        pass


def _quiet_value(fn: Any) -> str | None:
    try:
        return str(fn())
    except Exception:
        return None
