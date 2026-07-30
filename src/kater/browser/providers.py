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
from urllib.parse import quote

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
# Bound the browser launch/attach so start() cannot block on the worker forever
# while holding self._lock.
START_TIMEOUT_SECONDS = 60.0

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
        """Initialize a local browser provider with the specified launch and evaluation settings.

        Parameters:
            headless (bool): Whether to launch the browser in headless mode.
            allow_evaluate (bool): Whether browser actions may evaluate page scripts.
        """
        self.headless = headless
        self.allow_evaluate = allow_evaluate
        self._runner = CallRunner(name=f"kater-browser-{self.kind.value}")
        self._lock = threading.RLock()
        self._playwright: Any = None
        self._browser: Any = None
        # Session manager cannot always pass policy into new_page; act() sets
        # this so the network guard sees the active session policy. Kept as the
        # fallback for pages that have no per-page policy registered yet.
        self._guard_policy: BrowserPolicy | None = None
        # Per-page policy keyed by id(page). The provider is shared across
        # sessions, so a single shared policy would let one page's request be
        # evaluated against another session's policy; resolve each page's own.
        self._page_policies: dict[int, BrowserPolicy] = {}

    # ── lifecycle ──────────────────────────────────────────────────

    def start(self) -> None:
        """Start the browser provider if it is not already running."""
        with self._lock:
            if self._browser is not None:
                return
            self._submit(self._start_on_worker, timeout=START_TIMEOUT_SECONDS)

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
        """Launch a Chromium browser with the configured headless mode and launch arguments.

        Parameters:
            playwright (Any): Playwright instance used to launch Chromium.

        Returns:
            Any: The launched Chromium browser instance.
        """
        return playwright.chromium.launch(headless=self.headless, args=launch_args())

    def stop(self) -> None:
        """Stop the browser and its associated driver resources."""
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
        """
        Close the browser and stop the Playwright instance on the worker thread.
        """
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
        """
        Submit a browser operation to the worker thread.

        Parameters:
            fn (Any): The operation to execute.
            timeout (float | None): Maximum time to wait for completion.

        Returns:
            Any: The operation's result.

        Raises:
            TimeoutError: If the operation exceeds the specified timeout.
        """
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
        """
        Create a browser page for a session and optionally apply its browser policy.

        Parameters:
            session (BrowserSession): Session whose viewport dimensions configure the page context.
            policy (BrowserPolicy | None): Policy to apply to the page and its popups.

        Returns:
            PageHandle: Handle for the newly created page and its browser context.
        """
        if policy is not None:
            self._guard_policy = policy
        self.start()
        return self._submit(
            lambda: self._new_page_on_worker(session, policy), timeout=60.0
        )

    def _new_page_on_worker(
        self, session: BrowserSession, policy: BrowserPolicy | None = None
    ) -> PageHandle:
        """Create a browser page configured for the session viewport and network policy.

        Parameters:
            session (BrowserSession): Session containing the page dimensions and identifier.
            policy (BrowserPolicy | None): Optional policy to apply to the page.

        Returns:
            PageHandle: Handle containing the session identifier, browser context, and page.

        Raises:
            BrowserUnavailableError: If the browser is not running.
        """
        if self._browser is None:
            raise BrowserUnavailableError("browser is not running")
        context = self._browser.new_context(
            viewport={"width": session.viewport_width, "height": session.viewport_height},
            ignore_https_errors=False,
        )
        page = context.new_page()
        self._attach_guard(page, policy)
        return PageHandle(session_id=session.session_id, context=context, page=page)

    def _attach_guard(self, page: Any, policy: BrowserPolicy | None = None) -> None:
        """
        Attach network policy enforcement to a page and propagate its active policy to popups.

        Parameters:
            page (Any): The page to guard.
            policy (BrowserPolicy | None): The policy associated with the page, if specified.
        """
        if policy is not None:
            self._page_policies[id(page)] = policy
        install_network_guard(page, lambda: self._policy_for(page))
        # Popups belong to the opener's session; inherit its active policy.
        page.on("popup", lambda popup: self._attach_guard(popup, self._policy_for(page)))
        # Drop the per-page entry when the page closes so a recycled id() cannot
        # inherit a stale policy.
        page.on("close", lambda: self._page_policies.pop(id(page), None))

    def _policy_for(self, page: Any) -> BrowserPolicy:
        """Return the policy configured for a page.

        Parameters:
            page (Any): The page whose policy should be retrieved.

        Returns:
            BrowserPolicy: The page-specific policy, or the current default policy when no
                page-specific policy is configured.
        """
        policy = self._page_policies.get(id(page))
        if policy is not None:
            return policy
        return self._guard_policy or load_policy()

    def close_page(self, handle: Any) -> None:
        """Close a browser page and its associated context when the handle is valid."""
        if not isinstance(handle, PageHandle) or not self._runner.running:
            return
        _quiet(
            lambda: self._submit(lambda: self._close_page_on_worker(handle), timeout=20.0)
        )

    def _close_page_on_worker(self, handle: PageHandle) -> None:
        """Close a page and its browser context, removing any associated policy."""
        self._page_policies.pop(id(handle.page), None)
        _quiet(handle.page.close)
        _quiet(handle.context.close)

    # ── actions ────────────────────────────────────────────────────

    def act(self, handle: Any, action: BrowserAction, policy: BrowserPolicy) -> ActionResult:
        """Execute a browser action on a page using the specified policy.

        Parameters:
            handle (Any): Page handle on which to perform the action.
            action (BrowserAction): Action to execute.
            policy (BrowserPolicy): Policy governing action execution.

        Returns:
            ActionResult: Result of the executed action.

        Raises:
            TypeError: If handle is not a PageHandle.
        """
        if not isinstance(handle, PageHandle):
            raise TypeError(f"expected a PageHandle, got {type(handle).__name__}")
        self._guard_policy = policy
        self._page_policies[id(handle.page)] = policy
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
        """
        Describe the local Chromium provider's current availability and version.

        Returns:
            ProviderInfo: Provider status and version when Chromium is running; otherwise, local
                browser probe results.
        """
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
        """Initialize a provider that connects to the specified Chrome DevTools Protocol endpoint.

        Parameters:
            endpoint (str): WebSocket endpoint of the browser to connect to
            allow_evaluate (bool): Whether browser evaluation actions are permitted
        """
        super().__init__(headless=True, allow_evaluate=allow_evaluate)
        self.endpoint = endpoint

    def _connect(self, playwright: Any) -> Any:
        """Connect to the configured browser through its Chrome DevTools Protocol endpoint.

        Parameters:
            playwright (Any): Playwright instance used to establish the connection.

        Returns:
            Any: Connected browser instance.

        Raises:
            BrowserUnavailableError: If no CDP endpoint is configured.
        """
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
        """
        Disconnect the Playwright driver without closing the remotely managed browser.
        """
        self._browser = None
        playwright, self._playwright = self._playwright, None
        if playwright is not None:
            _quiet(playwright.stop)

    def info(self) -> ProviderInfo:
        """Describe the configured CDP endpoint and whether the provider is connected.

        Returns:
            ProviderInfo: Provider status with a redacted endpoint description.
        """
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
        """Initialize a provider that creates browser sessions through the Steel API.

        Parameters:
            base_url (str): Base URL of the Steel API.
            api_key (str | None): Optional API key for Steel requests.
            allow_evaluate (bool): Whether browser evaluation actions are permitted.
            timeout (float): Timeout for Steel API requests.
        """
        super().__init__("", allow_evaluate=allow_evaluate)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._steel_session_id: str | None = None

    def start(self) -> None:
        """Create a Steel Browser session when needed and attach to its CDP endpoint."""
        with self._lock:
            if self._browser is not None:
                return
            if not self.endpoint:
                self.endpoint, self._steel_session_id = self._create_steel_session()
        super().start()

    def stop(self) -> None:
        """Stops the provider and releases the associated Steel Browser session."""
        try:
            super().stop()
        finally:
            session_id, self._steel_session_id = self._steel_session_id, None
            self.endpoint = ""
            if session_id:
                _quiet(lambda: self._release_steel_session(session_id))

    def info(self) -> ProviderInfo:
        """
        Describe the Steel provider's current connection status.

        Returns:
            ProviderInfo: Provider information indicating whether a Steel browser
                session is attached and identifying the configured Steel API endpoint.
        """
        safe = redact_endpoint(self.base_url)
        if self._browser is not None:
            return ProviderInfo(self.kind, True, f"steel session on {safe}")
        return ProviderInfo(self.kind, True, f"steel api {safe} (not started)")

    def _connect(self, playwright: Any) -> Any:
        """Connect to the Steel Browser session through its validated CDP endpoint.

        Parameters:
            playwright (Any): Playwright instance used to establish the connection.

        Returns:
            Any: Connected browser instance.

        Raises:
            BrowserUnavailableError: If no CDP endpoint is configured.
        """
        if not self.endpoint:
            raise BrowserUnavailableError(
                f"steel session at {self.base_url} has no CDP endpoint"
            )
        endpoint = validate_cdp_endpoint(self.endpoint, steel_base_url=self.base_url)
        return playwright.chromium.connect_over_cdp(endpoint)

    def _create_steel_session(self) -> tuple[str, str | None]:
        """
        Create a Steel Browser session and extract its validated CDP endpoint.

        Returns:
            tuple[str, str | None]: The CDP endpoint and the session identifier, if provided.

        Raises:
            BrowserUnavailableError: If the session response does not contain a CDP endpoint.
        """
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
        """Release a Steel Browser session identified by its session ID.

        Parameters:
            session_id (str): The Steel session identifier to release.
        """
        self._steel_request("DELETE", f"/v1/sessions/{quote(session_id, safe='')}")

    def _steel_request(
        self, method: str, path: str, *, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Send an HTTP request to the Steel Browser API and parse its JSON object response.

        Parameters:
            method (str): HTTP method to use.
            path (str): API path appended to the configured base URL.
            body (dict[str, Any] | None): Optional JSON request body.

        Returns:
            dict[str, Any]: Parsed response object, or an empty dictionary for an empty or
                non-object response.

        Raises:
            BrowserUnavailableError: If the base URL is invalid, the request cannot reach the Steel
                Browser API, or the response is not valid JSON.
        """
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
    """
    Selects a browser provider based on the requested kind and environment configuration.

    Parameters:
        kind (ProviderKind | str | None): Provider kind to instantiate. When omitted, uses the
            configured environment value or defaults to a local provider.
        settings (KaterSettings | None): Ignored; environment variables provide the configuration.

    Returns:
        BrowserProvider: The configured local, CDP, or Steel browser provider.

    Raises:
        BrowserUnavailableError: If the CDP provider is selected without a configured endpoint.
        ValueError: If the provider kind is unsupported.
    """
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
    """
    Find the first non-empty CDP URL in a session payload.

    Parameters:
        payload (dict[str, Any]): Session data to inspect.

    Returns:
        str: The first non-empty CDP URL, or an empty string if none is present.
    """
    for key in _CDP_URL_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _quiet(fn: Any) -> None:
    """Execute a callable while suppressing any exception it raises."""
    try:
        fn()
    except Exception:  # noqa: S110 — teardown must not mask the original failure
        pass


def _quiet_value(fn: Any) -> str | None:
    """Return the string representation of a callable's result.

    Parameters:
        fn (Any): Callable to invoke.

    Returns:
        str | None: The stringified result, or `None` if invocation or conversion fails.
    """
    try:
        return str(fn())
    except Exception:
        return None
