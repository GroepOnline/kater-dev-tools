from __future__ import annotations

import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from kater.browser.base import BrowserUnavailableError
from kater.browser.network import install_network_guard, validate_cdp_endpoint
from kater.browser.policy import BrowserPolicy, PolicyViolation
from kater.browser.providers import probe_local
from kater.browser.runner import CallRunner

PUBLIC_IP = "93.184.216.34"
_LOCAL_PROBE = probe_local()
requires_chromium = pytest.mark.skipif(
    not _LOCAL_PROBE.available, reason=f"local chromium unavailable: {_LOCAL_PROBE.detail}"
)


def resolver_for(*addresses: str):
    """
    Create a resolver that returns the specified IP addresses for any host and port.

    Parameters:
        addresses (str): IP addresses to return from the resolver.

    Returns:
        Callable: A resolver callback accepting a host and port and returning socket address
            records.
    """
    def _resolve(host: str, port: int):
        del host, port
        return [
            (
                socket.AF_INET6 if ":" in address else socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                (address, 80),
            )
            for address in addresses
        ]

    return _resolve


def public_policy(**kwargs) -> BrowserPolicy:
    """
    Create a browser policy configured to resolve hosts to a public IP address by default.

    Parameters:
        **kwargs: Additional arguments passed to `BrowserPolicy`. A supplied `resolver` takes
            precedence over the default.

    Returns:
        BrowserPolicy: The configured browser policy.
    """
    kwargs.setdefault("resolver", resolver_for(PUBLIC_IP))
    return BrowserPolicy(**kwargs)


# ── check_request ──────────────────────────────────────────────────


def test_check_request_blocks_private_ip_on_xhr():
    policy = BrowserPolicy(resolver=resolver_for("127.0.0.1"))
    with pytest.raises(PolicyViolation, match="non-public address"):
        policy.check_request("http://127.0.0.1:8080/secret", resource_type="xhr")
    with pytest.raises(PolicyViolation, match="non-public address"):
        policy.check_request("https://169.254.169.254/latest/meta-data/", resource_type="fetch")


def test_check_request_allows_data_and_blob_subresources():
    policy = public_policy()
    policy.check_request("data:image/png;base64,aaa", resource_type="image")
    policy.check_request("blob:https://example.com/uuid", resource_type="image")


def test_check_request_blocks_dangerous_subresource_schemes():
    policy = public_policy()
    for url in ("file:///etc/passwd", "javascript:alert(1)", "chrome://settings"):
        with pytest.raises(PolicyViolation, match="never allowed"):
            policy.check_request(url, resource_type="script")


def test_check_request_blocks_data_on_document_navigation():
    policy = public_policy()
    with pytest.raises(PolicyViolation, match="never allowed"):
        policy.check_request("data:text/html,<h1>x</h1>", resource_type="document")


def test_check_request_applies_allow_domains_to_subresources():
    policy = public_policy(allow_domains=("example.com",))
    policy.check_request("https://example.com/", resource_type="document")
    policy.check_request("https://example.com/app.js", resource_type="script")
    with pytest.raises(PolicyViolation, match="not in the browser allow-list"):
        policy.check_request("https://cdn.other.test/app.js", resource_type="document")
    # A non-allowlisted host is an exfiltration path even as a subresource.
    with pytest.raises(PolicyViolation, match="not in the browser allow-list"):
        policy.check_request("https://cdn.other.test/app.js", resource_type="script")
    with pytest.raises(PolicyViolation, match="not in the browser allow-list"):
        policy.check_request("https://cdn.other.test/x.png", resource_type="image")


def test_check_request_deny_domains_apply_to_subresources():
    policy = public_policy(deny_domains=("evil.com",))
    with pytest.raises(PolicyViolation, match="denied domain"):
        policy.check_request("https://evil.com/", resource_type="document")
    # Denied hosts stay denied for subresources (trackers, beacons, XHR).
    with pytest.raises(PolicyViolation, match="denied domain"):
        policy.check_request("https://evil.com/tracker.js", resource_type="script")


def test_check_request_allow_private_opt_in():
    policy = BrowserPolicy(allow_private_networks=True, resolver=resolver_for("10.0.0.1"))
    policy.check_request("http://10.0.0.1/api", resource_type="fetch")
    policy.check_request("http://127.0.0.1/", resource_type="document")


def test_invalid_port_raises_policy_violation():
    policy = public_policy()
    with pytest.raises(PolicyViolation, match="invalid port"):
        policy.check_url("http://example.com:99999/")
    with pytest.raises(PolicyViolation, match="invalid port"):
        policy.check_request("http://example.com:99999/x", resource_type="xhr")


# ── validate_cdp_endpoint ──────────────────────────────────────────


def test_validate_cdp_accepts_local_chrome_loopback():
    assert validate_cdp_endpoint("ws://127.0.0.1:9222") == "ws://127.0.0.1:9222"
    assert validate_cdp_endpoint("ws://localhost:9222/devtools") == "ws://localhost:9222/devtools"


def test_validate_cdp_rejects_metadata_hosts():
    with pytest.raises(PolicyViolation, match="metadata"):
        validate_cdp_endpoint("ws://169.254.169.254:9222")
    with pytest.raises(PolicyViolation, match="metadata"):
        validate_cdp_endpoint("http://metadata.google.internal/devtools")


def test_validate_cdp_rejects_dangerous_schemes():
    for url in ("file:///tmp/x", "javascript:alert(1)", "data:text/plain,hi"):
        with pytest.raises((PolicyViolation, BrowserUnavailableError)):
            validate_cdp_endpoint(url)


def test_validate_cdp_rejects_private_when_steel_base_is_public():
    with pytest.raises(PolicyViolation, match="non-public"):
        validate_cdp_endpoint(
            "ws://10.0.0.5:9222/devtools",
            steel_base_url="https://steel.example.com",
        )
    with pytest.raises(PolicyViolation, match="loopback"):
        validate_cdp_endpoint(
            "ws://127.0.0.1:9222",
            steel_base_url="https://steel.example.com",
        )


def test_validate_cdp_allows_private_when_steel_base_is_local():
    assert (
        validate_cdp_endpoint(
            "ws://10.0.0.5:9222/devtools",
            steel_base_url="http://127.0.0.1:3000",
        )
        == "ws://10.0.0.5:9222/devtools"
    )
    assert (
        validate_cdp_endpoint(
            "ws://127.0.0.1:9222",
            steel_base_url="http://localhost:3000",
        )
        == "ws://127.0.0.1:9222"
    )


def test_validate_cdp_rejects_private_for_plain_cdp():
    with pytest.raises(PolicyViolation, match="loopback only"):
        validate_cdp_endpoint("ws://10.0.0.5:9222")


def test_validate_cdp_allows_unresolved_same_host_as_steel():
    # Fake host shared with Steel — DNS may fail in CI; same-host is OK.
    assert (
        validate_cdp_endpoint(
            "ws://steel.test:3000/devtools",
            steel_base_url="http://steel.test:3000",
        )
        == "ws://steel.test:3000/devtools"
    )


# ── install_network_guard ──────────────────────────────────────────


class _FakeRequest:
    def __init__(self, url: str, resource_type: str = "xhr") -> None:
        """Initialize a fake request with its URL and resource type.

        Parameters:
            url (str): The requested URL.
            resource_type (str): The type of resource being requested.
        """
        self.url = url
        self.resource_type = resource_type


class _FakeRoute:
    def __init__(self, url: str, resource_type: str = "xhr") -> None:
        """Create a fake route for a request URL and resource type.

        Parameters:
            url (str): The request URL.
            resource_type (str): The request's resource type.
        """
        self.request = _FakeRequest(url, resource_type)
        self.aborted: str | None = None
        self.continued = False

    def abort(self, reason: str = "") -> None:
        """
        Record the reason that the route was aborted.

        Parameters:
            reason (str): The reason for aborting the route.
        """
        self.aborted = reason

    def continue_(self) -> None:
        self.continued = True


class _FakePage:
    def __init__(self) -> None:
        """Initialize an empty fake page with no registered route or popup handlers."""
        self.route_handler: Any = None
        self.popup_handler: Any = None

    def route(self, pattern: str, handler: Any) -> None:
        """
        Register a route handler for the fake page.

        Parameters:
            pattern (str): Route pattern accepted for API compatibility.
            handler (Any): Handler to store for later invocation.
        """
        del pattern
        self.route_handler = handler

    def on(self, event: str, handler: Any) -> None:
        """Register a handler for the popup event."""
        if event == "popup":
            self.popup_handler = handler


def test_install_network_guard_aborts_private_requests():
    page = _FakePage()
    install_network_guard(page, BrowserPolicy(resolver=resolver_for("127.0.0.1")))
    assert page.route_handler is not None

    blocked = _FakeRoute("http://127.0.0.1/x", "fetch")
    page.route_handler(blocked)
    assert blocked.aborted == "blockedbyclient"
    assert blocked.continued is False

    allowed = _FakeRoute("https://example.com/x.js", "script")
    # example.com resolves via policy resolver to PUBLIC_IP only if we use that policy
    page2 = _FakePage()
    install_network_guard(page2, public_policy())
    page2.route_handler(allowed)
    assert allowed.continued is True
    assert allowed.aborted is None


def test_install_network_guard_allows_data_images():
    page = _FakePage()
    install_network_guard(page, public_policy())
    route = _FakeRoute("data:image/png;base64,abc", "image")
    page.route_handler(route)
    assert route.continued is True


# ── CallRunner poison recovery ─────────────────────────────────────


def test_call_runner_timeout_abandons_worker_and_recovers():
    runner = CallRunner(name="test-poison")
    try:
        with pytest.raises(TimeoutError):
            runner.submit(lambda: time.sleep(60), timeout=0.2)
        assert runner.restarts >= 1
        generation_after = runner.generation
        assert runner.submit(lambda: 1, timeout=2.0) == 1
        assert runner.generation == generation_after
        assert runner.running is True
    finally:
        runner.stop(timeout=2.0)


def test_call_runner_replace_worker_increments_restarts():
    runner = CallRunner(name="test-replace")
    try:
        runner.start()
        assert runner.restarts == 0
        runner.replace_worker()
        assert runner.restarts == 1
        assert runner.submit(lambda: 7, timeout=2.0) == 7
    finally:
        runner.stop(timeout=2.0)


# ── playwright integration (optional) ──────────────────────────────


@requires_chromium
def test_network_guard_aborts_private_fetch_in_page():
    """Live Chromium check — skipped when the browser binary is not installed."""
    from playwright.sync_api import sync_playwright

    hits: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            hits.append(self.path)
            body = b"secret"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_port
    policy = BrowserPolicy(allow_private_networks=False)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                install_network_guard(page, policy)
                page.goto("about:blank")
                page.evaluate(
                    f"fetch('http://127.0.0.1:{port}/private').catch(() => {{}})"
                )
                page.wait_for_timeout(500)
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert hits == []
