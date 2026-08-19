from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import Mock, patch

import pytest

from kater import mcp_server
from kater.settings import AuthConfig, KaterSettings, save_settings


def test_mcp_missing_package_message() -> None:
    with (
        patch("kater.mcp_server.import_module", side_effect=ModuleNotFoundError("mcp")),
        pytest.raises(mcp_server.McpUnavailableError) as exc_info,
    ):
        mcp_server.create_server()

    assert "uv sync" in str(exc_info.value)


def test_mcp_registers_core_tools() -> None:
    fake_server = Mock()
    fake_server.tool.return_value = lambda handler: handler
    fake_module = Mock(
        FastMCP=Mock(return_value=fake_server),
        TransportSecuritySettings=Mock(side_effect=lambda **kw: kw),
    )

    with patch("kater.mcp_server.import_module", return_value=fake_module):
        server = mcp_server.create_server(profile="core")

    assert server is fake_server
    registered = [call.kwargs["name"] for call in fake_server.tool.call_args_list]
    assert "kater_profiles" in registered
    assert "kater_doctor" in registered


def test_create_server_native_tools_record_tool_calls() -> None:
    captured: dict[str, Any] = {}

    def capture(handler):
        captured[name_box[0]] = handler
        return handler

    name_box = [""]
    fake_server = Mock()
    fake_server.tool.side_effect = lambda **kwargs: (
        name_box.__setitem__(0, kwargs["name"]) or capture
    )
    fake_module = Mock(
        FastMCP=Mock(return_value=fake_server),
        TransportSecuritySettings=Mock(side_effect=lambda **kw: kw),
    )

    with patch("kater.mcp_server.import_module", return_value=fake_module):
        mcp_server.create_server(profile="core")

    result = captured["kater_profiles"]()
    assert "profiles" in result
    from kater.storage import query_events

    events = query_events(event_type="tool_call", name="kater_profiles")
    assert len(events) == 1
    assert events[0]["success"] is True


def test_create_server_allowlists_tunnel_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_server = Mock()
    fake_server.tool.return_value = lambda handler: handler
    fake_module = Mock(
        FastMCP=Mock(return_value=fake_server),
    )
    monkeypatch.setenv("KATER_DOMAIN", "kater.example.com")
    monkeypatch.setenv("KATER_HTTPS_HOSTS", "kater.example.com,alt.example.com")

    with patch("kater.mcp_server.import_module", return_value=fake_module):
        server = mcp_server.create_server(profile="core")

    # mcp 1.x passes transport_security to FastMCP(); mcp 2.x stores it for sse_app().
    if fake_module.FastMCP.called:
        settings = fake_module.FastMCP.call_args.kwargs["transport_security"]
    else:
        settings = server._kater_sse_transport_security

    assert settings.enable_dns_rebinding_protection is True
    assert settings.allowed_hosts == [
        "127.0.0.1:*",
        "localhost:*",
        "[::1]:*",
        "kater.example.com",
        "kater.example.com:*",
        "alt.example.com",
        "alt.example.com:*",
    ]
    assert settings.allowed_origins == [
        "http://127.0.0.1:*",
        "http://localhost:*",
        "http://[::1]:*",
        "https://kater.example.com",
        "https://kater.example.com:*",
        "http://kater.example.com",
        "http://kater.example.com:*",
        "https://alt.example.com",
        "https://alt.example.com:*",
        "http://alt.example.com",
        "http://alt.example.com:*",
    ]


def test_create_server_does_not_start_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_server = Mock()
    fake_server.tool.return_value = lambda handler: handler
    fake_module = Mock(
        FastMCP=Mock(return_value=fake_server),
        TransportSecuritySettings=Mock(side_effect=lambda **kw: kw),
    )
    proxy_start = Mock()
    monkeypatch.setattr(
        "kater.proxy.get_proxy",
        lambda: Mock(start=proxy_start, list_tools=Mock(return_value=[])),
    )

    with patch("kater.mcp_server.import_module", return_value=fake_module):
        mcp_server.create_server(profile="core")

    proxy_start.assert_not_called()


def test_mcp_rate_limit_ignores_spoofed_xff_from_public_peer(monkeypatch, tmp_path) -> None:
    seen_clients: list[str] = []

    class FakeLimiter:
        def check(self, client_ip: str) -> bool:
            seen_clients.append(client_ip)
            return False

    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.delenv("KATER_TRUST_PROXY", raising=False)
    monkeypatch.setattr("kater.api.server._rate_limiter", FakeLimiter())
    monkeypatch.chdir(tmp_path)
    save_settings(KaterSettings(auth=AuthConfig(mode="none")))

    async def app(scope, receive, send):
        raise AssertionError("rate limit should stop request")

    mw = mcp_server.AuthASGIMiddleware(app)
    sent: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        sent.append(message)

    asyncio.run(
        mw(
            {
                "type": "http",
                "path": "/sse",
                "query_string": b"",
                "headers": [(b"x-forwarded-for", b"198.51.100.1")],
                "client": ("8.8.8.8", 12345),
            },
            receive,
            send,
        )
    )

    assert seen_clients == ["8.8.8.8"]
    assert sent[0]["status"] == 429


def test_build_mcp_app_combines_sse_and_streamable_http() -> None:
    class _Route:
        def __init__(self, path: str) -> None:
            self.path = path

    fake_sse_app = Mock()
    fake_sse_app.routes = [_Route("/sse"), _Route("/messages")]
    fake_stream_app = Mock()
    fake_stream_app.routes = [_Route("/mcp")]

    class FakeServer:
        def sse_app(self, **kwargs: Any) -> Mock:
            return fake_sse_app

        def streamable_http_app(self, **kwargs: Any) -> Mock:
            return fake_stream_app

        @property
        def session_manager(self) -> Mock:
            return self._session_manager

        def __init__(self) -> None:
            self._session_manager = Mock()
            self._session_manager.run.return_value = _FakeAsyncContext()

    fake_server = FakeServer()

    with patch("kater.mcp_server.create_server", return_value=fake_server):
        app = mcp_server.build_mcp_app(profile="core")

    auth_mw = app._app
    starlette = auth_mw._app
    paths = [route.path for route in starlette.routes]
    assert paths == ["/sse", "/messages", "/mcp"]
    assert starlette.router.lifespan_context is not None


def test_build_mcp_app_sse_only_without_streamable_http() -> None:
    fake_sse_app = Mock()
    fake_sse_app.routes = [Mock(path="/sse")]

    class FakeServer:
        def sse_app(self, **kwargs: Any) -> Mock:
            return fake_sse_app

    fake_server = FakeServer()

    with patch("kater.mcp_server.create_server", return_value=fake_server):
        app = mcp_server.build_mcp_app(profile="core")

    auth_mw = app._app
    assert auth_mw._app is fake_sse_app


class _FakeAsyncContext:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: object) -> None:
        return None


def test_build_proxy_handler_allocates_extra_suffixes_on_name_collision() -> None:
    """When fallback names collide, keep suffixing instead of skipping the tool."""
    import inspect

    proxy = Mock()
    proxy.call_tool.return_value = {"ok": True}

    handler = mcp_server._build_proxy_handler(
        "evil__collide",
        {
            "type": "object",
            "properties": {
                "from_": {"type": "string"},
                "arg_from": {"type": "string"},
                "from": {"type": "string"},
            },
        },
        proxy,
    )

    sig = inspect.signature(handler)
    assert list(sig.parameters) == ["from_", "arg_from", "from__"]
    handler(from_="a", arg_from="b", from__="c")
    proxy.call_tool.assert_called_once_with(
        "evil__collide",
        {"from_": "a", "arg_from": "b", "from": "c"},
    )


def test_build_proxy_handler_reflects_python_keyword_params() -> None:
    """Schema properties named like Python keywords must not crash registration."""
    import inspect

    proxy = Mock()
    proxy.call_tool.return_value = {"ok": True}

    handler = mcp_server._build_proxy_handler(
        "firecrawl__search",
        {
            "type": "object",
            "properties": {
                "from": {"type": "string"},
                "class": {"type": "string"},
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
        proxy,
    )

    sig = inspect.signature(handler)
    assert list(sig.parameters) == ["from_", "class_", "query"]
    for param in sig.parameters.values():
        assert param.kind == inspect.Parameter.KEYWORD_ONLY
        assert param.annotation is Any

    handler(from_="2024-01-01", class_="article", query="mcp")
    proxy.call_tool.assert_called_once_with(
        "firecrawl__search",
        {"from": "2024-01-01", "class": "article", "query": "mcp"},
    )


def test_wrap_native_handler_accepts_empty_and_extra_args() -> None:
    """No-arg native tools must accept {}, nulls, and unknown keys."""
    import inspect

    from mcp.server.mcpserver.utilities.func_metadata import func_metadata

    def no_arg_tool() -> dict[str, str]:
        return {"ok": "yes"}

    wrapped = mcp_server._wrap_native_handler(no_arg_tool)
    assert list(inspect.signature(wrapped).parameters) == []

    meta = func_metadata(wrapped)
    for args in [{}, {"extra": "ignored"}, {"_meta": {}}, {"unused": None}]:
        validated = meta.validate_arguments(args)
        assert wrapped(**validated) == {"ok": "yes"}


def test_wrap_native_handler_optional_profile_and_null() -> None:
    """Optional native params tolerate omission, null, and extra keys."""
    import inspect

    from mcp.server.mcpserver.utilities.func_metadata import func_metadata

    calls: list[str] = []

    def doctor_like(profile: str = "core") -> dict[str, str]:
        calls.append(profile)
        return {"profile": profile}

    wrapped = mcp_server._wrap_native_handler(doctor_like)
    assert list(inspect.signature(wrapped).parameters) == ["profile"]

    meta = func_metadata(wrapped)
    for args in [{}, {"profile": "ops"}, {"profile": None}, {"extra": 1}]:
        validated = meta.validate_arguments(args)
        wrapped(**validated)

    assert calls == ["core", "ops", "core", "core"]


def test_native_tools_callable_with_cursor_like_payloads() -> None:
    """Registered native tools accept loose CallTool argument shapes."""
    from unittest.mock import Mock

    async def _run() -> None:
        server = mcp_server.create_server(profile="core")
        tm = server._tool_manager
        ctx = Mock()

        await tm.call_tool("kater_profiles", {}, ctx)
        await tm.call_tool("kater_profiles", {"_meta": {}, "extra": "x"}, ctx)

        await tm.call_tool("kater_doctor", {}, ctx)
        await tm.call_tool("kater_doctor", {"profile": "ops"}, ctx)
        await tm.call_tool("kater_doctor", {"profile": None, "extra": "ignored"}, ctx)

    asyncio.run(_run())
