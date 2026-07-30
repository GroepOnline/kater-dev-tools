from __future__ import annotations

import base64
import socket
import sys
import time
from typing import Any

import pytest

from kater.browser.actions import execute_action
from kater.browser.base import PageHandle, redact_endpoint
from kater.browser.models import ActionKind, BrowserAction, ProviderKind
from kater.browser.policy import BrowserPolicy, PolicyViolation
from kater.browser.providers import (
    BrowserUnavailableError,
    CdpProvider,
    PlaywrightProvider,
    ProviderInfo,
    SteelProvider,
    browsers_root,
    launch_args,
    probe_cdp,
    probe_providers,
    resolve_provider,
)

BROWSER_ENV = (
    "KATER_BROWSER_PROVIDER",
    "KATER_BROWSER_CDP_URL",
    "KATER_BROWSER_STEEL_URL",
    "KATER_BROWSER_STEEL_KEY",
    "KATER_BROWSER_NO_SANDBOX",
    "KATER_BROWSER_ALLOW_EVALUATE",
)


@pytest.fixture(autouse=True)
def _clean_browser_env(monkeypatch):
    for name in BROWSER_ENV:
        monkeypatch.delenv(name, raising=False)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_probe_providers_shape():
    infos = probe_providers()
    assert [info.kind for info in infos] == [
        ProviderKind.LOCAL,
        ProviderKind.CDP,
        ProviderKind.REMOTE,
    ]
    for info in infos:
        assert isinstance(info, ProviderInfo)
        assert isinstance(info.available, bool)
        assert info.detail
        payload = info.to_dict()
        assert set(payload) == {"kind", "available", "detail", "version"}


def test_probe_does_not_import_playwright_or_launch(monkeypatch):
    monkeypatch.delitem(sys.modules, "playwright.sync_api", raising=False)
    probe_providers()
    assert "playwright.sync_api" not in sys.modules


def test_probe_local_reports_missing_chromium(monkeypatch, tmp_path):
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path / "empty"))
    local = probe_providers()[0]
    assert local.available is False
    assert "playwright install chromium" in local.detail


def test_probe_cdp_and_steel_report_env(monkeypatch):
    monkeypatch.setenv("KATER_BROWSER_CDP_URL", "ws://localhost:9222")
    monkeypatch.setenv("KATER_BROWSER_STEEL_URL", "http://localhost:3000")
    monkeypatch.setenv("KATER_BROWSER_STEEL_KEY", "sk-test")
    _, cdp, steel = probe_providers()
    assert cdp.available is True
    assert "ws://localhost:9222" in cdp.detail
    assert steel.available is True
    assert "with api key" in steel.detail


def test_probe_and_provider_info_redact_cdp_secrets(monkeypatch):
    dirty = "wss://user:s3cret@browserless.example:443/chrome?token=abc123"
    safe = redact_endpoint(dirty)
    assert "s3cret" not in safe
    assert "token=" not in safe
    assert "user@" not in safe
    assert "browserless.example" in safe

    monkeypatch.setenv("KATER_BROWSER_CDP_URL", dirty)
    info = probe_cdp()
    assert info.available is True
    assert "s3cret" not in info.detail
    assert "token=" not in info.detail
    assert "abc123" not in info.detail

    provider = CdpProvider(dirty)
    detail = provider.info().detail
    assert "s3cret" not in detail
    assert "token=" not in detail
    assert "abc123" not in detail


def test_browsers_root_honours_override(monkeypatch, tmp_path):
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))
    assert browsers_root() == tmp_path


def test_launch_args_keep_no_sandbox_opt_in(monkeypatch):
    assert launch_args() == ["--disable-dev-shm-usage"]
    monkeypatch.setenv("KATER_BROWSER_NO_SANDBOX", "1")
    assert "--no-sandbox" in launch_args()


def test_resolve_provider_defaults_to_local():
    provider = resolve_provider()
    assert isinstance(provider, PlaywrightProvider)
    assert provider.kind is ProviderKind.LOCAL
    assert provider.allow_evaluate is False


def test_resolve_provider_reads_env(monkeypatch):
    monkeypatch.setenv("KATER_BROWSER_PROVIDER", "cdp")
    monkeypatch.setenv("KATER_BROWSER_CDP_URL", "ws://localhost:9222")
    monkeypatch.setenv("KATER_BROWSER_ALLOW_EVALUATE", "true")
    provider = resolve_provider()
    assert isinstance(provider, CdpProvider)
    assert provider.kind is ProviderKind.CDP
    assert provider.endpoint == "ws://localhost:9222"
    assert provider.allow_evaluate is True


def test_resolve_provider_explicit_kind_beats_env(monkeypatch):
    monkeypatch.setenv("KATER_BROWSER_PROVIDER", "steel")
    assert isinstance(resolve_provider(ProviderKind.LOCAL), PlaywrightProvider)


def test_resolve_provider_cdp_without_endpoint_fails(monkeypatch):
    monkeypatch.setenv("KATER_BROWSER_PROVIDER", "cdp")
    with pytest.raises(BrowserUnavailableError, match="KATER_BROWSER_CDP_URL"):
        resolve_provider()


def test_resolve_provider_steel_uses_env(monkeypatch):
    monkeypatch.setenv("KATER_BROWSER_PROVIDER", "steel")
    monkeypatch.setenv("KATER_BROWSER_STEEL_URL", "http://steel.internal:3000/")
    monkeypatch.setenv("KATER_BROWSER_STEEL_KEY", "sk-test")
    provider = resolve_provider()
    assert isinstance(provider, SteelProvider)
    assert provider.kind is ProviderKind.REMOTE
    assert provider.base_url == "http://steel.internal:3000"
    assert provider.api_key == "sk-test"


def test_resolve_provider_rejects_unknown_kind():
    with pytest.raises(ValueError, match="unknown browser provider"):
        resolve_provider("teleport")


def test_cdp_provider_does_not_connect_at_construction():
    provider = CdpProvider(f"ws://127.0.0.1:{free_port()}")
    assert provider.info().available is True  # endpoint configured, nothing dialled
    assert provider._browser is None
    assert provider._playwright is None


def test_cdp_provider_without_endpoint_is_unavailable():
    info = CdpProvider("").info()
    assert info.available is False
    assert "no endpoint" in info.detail


def test_steel_provider_raises_on_dead_endpoint():
    provider = SteelProvider(f"http://127.0.0.1:{free_port()}", timeout=2.0)
    with pytest.raises(BrowserUnavailableError, match="unreachable"):
        provider.start()
    provider.stop()


def test_steel_provider_rejects_non_http_base_url():
    provider = SteelProvider("ws://localhost:3000")
    with pytest.raises(BrowserUnavailableError, match="must be http"):
        provider.start()


def test_steel_provider_requires_a_cdp_url_in_the_response(monkeypatch):
    provider = SteelProvider("http://steel.test:3000")
    monkeypatch.setattr(
        SteelProvider, "_steel_request", lambda self, method, path, body=None: {"id": "abc"}
    )
    with pytest.raises(BrowserUnavailableError, match="no CDP url"):
        provider.start()


def test_steel_provider_attaches_to_returned_cdp_url(monkeypatch):
    provider = SteelProvider("http://steel.test:3000", "sk-test")
    calls: list[tuple[str, str]] = []

    def fake_request(self, method, path, body=None):
        calls.append((method, path))
        if method == "POST":
            return {"id": "sess-1", "websocketUrl": "ws://steel.test:3000/devtools"}
        return {}

    connected: list[str] = []
    monkeypatch.setattr(SteelProvider, "_steel_request", fake_request)
    monkeypatch.setattr(
        SteelProvider,
        "_start_on_worker",
        lambda self: connected.append(self.endpoint),
    )
    provider.start()
    assert connected == ["ws://steel.test:3000/devtools"]
    assert provider.endpoint == "ws://steel.test:3000/devtools"
    provider.stop()
    assert calls == [("POST", "/v1/sessions"), ("DELETE", "/v1/sessions/sess-1")]
    assert provider.endpoint == ""


class FakePage:
    """Just enough of the Playwright page surface to drive execute_action."""

    def __init__(self, *, redirect_to: str | None = None, screenshots: list[bytes] | None = None):
        self.url = "about:blank"
        self.redirect_to = redirect_to
        self.screenshots = screenshots or [b"\xff\xd8" + b"jpeg" * 8]
        self.calls: list[tuple[str, Any]] = []
        self.text = "hello"
        self.snapshot_payload: Any = [{"tag": "button", "selector": "#go"}]
        self.raise_on_click: BaseException | None = None

    def goto(self, url, timeout=None, wait_until=None):
        self.calls.append(("goto", url))
        if self.redirect_to and url != "about:blank":
            self.url = self.redirect_to
        else:
            self.url = url

    def title(self):
        return "Fake page"

    def click(self, selector, timeout=None):
        self.calls.append(("click", selector))
        if self.raise_on_click is not None:
            raise self.raise_on_click
        if self.redirect_to:
            self.url = self.redirect_to

    def screenshot(self, type=None, quality=None, full_page=False):
        self.calls.append(("screenshot", full_page))
        index = 0 if full_page or len(self.screenshots) == 1 else 1
        return self.screenshots[index]

    def inner_text(self, selector, timeout=None):
        self.calls.append(("inner_text", selector))
        return self.text

    def evaluate(self, expression, *args):
        self.calls.append(("evaluate", expression))
        if args:
            return self.snapshot_payload
        if self.redirect_to:
            self.url = self.redirect_to
        return "evaluated"


def public_policy(**kwargs) -> BrowserPolicy:
    kwargs.setdefault("resolver", lambda host, port: [(2, 1, 6, "", ("93.184.216.34", 80))])
    return BrowserPolicy(**kwargs)


def run_action(page: FakePage, payload: dict[str, Any], policy: BrowserPolicy, **kwargs):
    return execute_action(
        page, BrowserAction.from_dict(payload), policy, session_id="bsess_" + "f" * 32, **kwargs
    )


def test_navigation_is_checked_before_the_browser_is_touched():
    page = FakePage()
    result = run_action(page, {"kind": "navigate", "url": "file:///etc/passwd"}, public_policy())
    assert result.ok is False
    assert "never allowed" in (result.error or "")
    assert page.calls == []


def test_redirect_to_a_blocked_host_is_caught_after_navigation():
    page = FakePage(redirect_to="http://169.254.169.254/latest/meta-data/")
    result = run_action(page, {"kind": "navigate", "url": "https://example.com/"}, public_policy())
    assert result.ok is False
    assert "non-public address" in (result.error or "")
    assert page.url == "about:blank"  # containment: the page is parked


def test_click_that_navigates_to_a_denied_host_is_caught():
    page = FakePage(redirect_to="https://evil.com/")
    policy = public_policy(deny_domains=("evil.com",))
    result = run_action(page, {"kind": "click", "selector": "#link"}, policy)
    assert result.ok is False
    assert "denied domain" in (result.error or "")


def test_browser_errors_are_returned_not_raised():
    page = FakePage()
    page.raise_on_click = RuntimeError("element detached")
    result = run_action(page, {"kind": "click", "selector": "#go"}, public_policy())
    assert result.ok is False
    assert result.error == "RuntimeError: element detached"
    assert result.title == "Fake page"


def test_evaluate_is_denied_unless_explicitly_allowed():
    page = FakePage()
    denied = run_action(page, {"kind": "evaluate", "expression": "1+1"}, public_policy())
    assert denied.ok is False
    assert "evaluate is disabled" in (denied.error or "")

    allowed = run_action(
        page, {"kind": "evaluate", "expression": "1+1"}, public_policy(), allow_evaluate=True
    )
    assert allowed.ok is True
    assert allowed.text == "evaluated"


def test_evaluate_that_navigates_to_a_denied_host_is_caught():
    page = FakePage(redirect_to="https://evil.com/")
    policy = public_policy(deny_domains=("evil.com",))
    result = run_action(
        page,
        {"kind": "evaluate", "expression": "location.href='https://evil.com/'"},
        policy,
        allow_evaluate=True,
    )
    assert result.ok is False
    assert "denied domain" in (result.error or "")


def test_action_timeout_is_clamped_to_policy():
    page = FakePage()
    calls: list[float] = []

    def wait_for_timeout(timeout):
        calls.append(timeout)

    page.wait_for_timeout = wait_for_timeout  # type: ignore[method-assign]
    policy = public_policy(action_timeout_ms=1_000)
    result = run_action(page, {"kind": "wait", "timeout_ms": 999_999}, policy)
    assert result.ok is True
    assert calls == [1_000.0]


def test_screenshot_over_the_cap_is_refused():
    page = FakePage(screenshots=[b"x" * 500])
    result = run_action(page, {"kind": "screenshot"}, public_policy(max_screenshot_bytes=100))
    assert result.ok is False
    assert "over the 100 byte cap" in (result.error or "")


def test_full_page_screenshot_falls_back_to_the_viewport():
    page = FakePage(screenshots=[b"x" * 500, b"y" * 10])
    result = run_action(
        page, {"kind": "screenshot", "full_page": True}, public_policy(max_screenshot_bytes=100)
    )
    assert result.ok is True
    assert result.screenshot_b64 == base64.b64encode(b"y" * 10).decode("ascii")
    assert [call for call in page.calls if call[0] == "screenshot"] == [
        ("screenshot", True),
        ("screenshot", False),
    ]


def test_extracted_text_is_truncated():
    page = FakePage()
    page.text = "a" * 25_000
    result = run_action(page, {"kind": "extract_text"}, public_policy())
    assert result.ok is True
    assert (result.text or "").startswith("a" * 100)
    assert "truncated at 20000 chars" in (result.text or "")
    assert page.calls[-1] == ("inner_text", "body")


def test_snapshot_returns_interactive_elements_and_tolerates_junk():
    page = FakePage()
    result = run_action(page, {"kind": "snapshot"}, public_policy())
    assert result.snapshot == ({"tag": "button", "selector": "#go"},)

    page.snapshot_payload = "not-a-list"
    assert run_action(page, {"kind": "snapshot"}, public_policy()).snapshot == ()


def test_playwright_provider_stop_is_safe_before_start():
    PlaywrightProvider().stop()


def test_act_rejects_a_foreign_handle():
    provider = PlaywrightProvider()
    with pytest.raises(TypeError, match="PageHandle"):
        provider.act(object(), None, None)  # type: ignore[arg-type]


def test_cdp_stop_does_not_close_remote_browser():
    provider = CdpProvider("ws://127.0.0.1:9222")
    closed: list[str] = []

    class _Browser:
        def close(self) -> None:
            closed.append("browser")

    class _Playwright:
        def stop(self) -> None:
            closed.append("playwright")

    provider._browser = _Browser()
    provider._playwright = _Playwright()
    provider._stop_on_worker()
    assert closed == ["playwright"]
    assert provider._browser is None
    assert provider._playwright is None


def test_local_stop_closes_browser():
    provider = PlaywrightProvider()
    closed: list[str] = []

    class _Browser:
        def close(self) -> None:
            closed.append("browser")

    class _Playwright:
        def stop(self) -> None:
            closed.append("playwright")

    provider._browser = _Browser()
    provider._playwright = _Playwright()
    provider._stop_on_worker()
    assert closed == ["browser", "playwright"]


def test_steel_rejects_metadata_cdp_url_in_session_response(monkeypatch):
    provider = SteelProvider("https://steel.example.com")
    monkeypatch.setattr(
        SteelProvider,
        "_steel_request",
        lambda self, method, path, body=None: {
            "id": "sess-evil",
            "websocketUrl": "ws://169.254.169.254/devtools",
        },
    )
    with pytest.raises(PolicyViolation, match="metadata"):
        provider._create_steel_session()


def test_steel_rejects_private_cdp_url_when_base_is_public(monkeypatch):
    provider = SteelProvider("https://steel.example.com")
    monkeypatch.setattr(
        SteelProvider,
        "_steel_request",
        lambda self, method, path, body=None: {
            "id": "sess-evil",
            "websocketUrl": "ws://10.0.0.5:9222/devtools",
        },
    )
    with pytest.raises(PolicyViolation, match="non-public"):
        provider._create_steel_session()


def test_act_timeout_invalidates_browser_state(monkeypatch):
    provider = PlaywrightProvider()
    provider._browser = object()
    provider._playwright = object()
    provider._runner.start()
    handle = PageHandle(session_id="bsess_" + "a" * 32, context=object(), page=object())

    monkeypatch.setattr(
        "kater.browser.providers.execute_action",
        lambda *args, **kwargs: time.sleep(60),
    )
    with pytest.raises(TimeoutError):
        provider.act(
            handle,
            BrowserAction(kind=ActionKind.SNAPSHOT, timeout_ms=100),
            public_policy(action_timeout_ms=100),
        )
    assert provider._browser is None
    assert provider._playwright is None
    assert provider._runner.restarts >= 1
    # Replacement worker must still accept work.
    assert provider._runner.submit(lambda: 42, timeout=2.0) == 42
    provider.stop()

