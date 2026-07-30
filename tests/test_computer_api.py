"""REST + CLI coverage for the Computer connector production paths."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from kater.api import ROUTER, Request, Response
from kater.cli import app
from kater.openapi_spec import generate_spec

COMPUTER_ROUTES = [
    ("GET", "/api/computer"),
    ("GET", "/api/computer/capabilities"),
    ("POST", "/api/computer/invoke"),
]

runner = CliRunner()


def _call(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
) -> Response:
    """
    Dispatch a test request to a registered API route.
    
    Parameters:
    	method (str): HTTP method for the request.
    	path (str): Request path to match against the router.
    	body (dict[str, Any] | None): Optional JSON request body.
    
    Returns:
    	Response: The route handler's response.
    """
    matched = ROUTER.match(method, path)
    assert matched is not None, f"{method} {path} has no route"
    route, params = matched
    raw = b"" if body is None else json.dumps(body).encode()
    headers = {"content-type": "application/json"} if body is not None else {}
    req = Request(
        method=method,
        path=path,
        query={},
        headers=headers,
        raw_body=raw,
        client_ip="127.0.0.1",
        base_url="http://127.0.0.1",
        params=params,
    )
    return route.handler(req)


@pytest.fixture(autouse=True)
def _reset_computer_connector() -> Any:
    """Reset the computer connector before and after each test."""
    from kater.capabilities.wiring import reset_computer_connector

    reset_computer_connector()
    yield
    reset_computer_connector()


@pytest.mark.parametrize("method,path", COMPUTER_ROUTES)
def test_computer_routes_registered(method: str, path: str) -> None:
    assert ROUTER.match(method, path) is not None, f"{method} {path} missing from ROUTER"


def test_computer_status_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KATER_COMPUTER_URL", raising=False)
    monkeypatch.delenv("KATER_COMPUTER_TOKEN", raising=False)

    resp = _call("GET", "/api/computer")
    assert resp.status == 200
    assert isinstance(resp.payload, dict)
    assert resp.payload["configured"] is False
    assert resp.payload["active"] is False
    assert resp.payload["capability_count"] == 0
    assert resp.payload["capability_ids"] == []
    assert resp.payload["base_url_host"] == ""


def test_computer_capabilities_empty_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KATER_COMPUTER_URL", raising=False)
    monkeypatch.delenv("KATER_COMPUTER_TOKEN", raising=False)

    resp = _call("GET", "/api/computer/capabilities")
    assert resp.status == 200
    assert resp.payload == {"tools": [], "total": 0}


def test_computer_invoke_503_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KATER_COMPUTER_URL", raising=False)
    monkeypatch.delenv("KATER_COMPUTER_TOKEN", raising=False)

    resp = _call(
        "POST",
        "/api/computer/invoke",
        body={"capability_id": "filesystem.read", "arguments": {"path": "README.md"}},
    )
    assert resp.status == 503
    assert isinstance(resp.payload, dict)
    assert "not configured" in resp.payload["error"]


def test_computer_invoke_400_without_capability_id(monkeypatch: pytest.MonkeyPatch) -> None:
    import kater.api.routes as routes

    monkeypatch.setattr(routes, "get_computer_connector", lambda: MagicMock())

    resp = _call("POST", "/api/computer/invoke", body={"arguments": {}})
    assert resp.status == 400
    assert isinstance(resp.payload, dict)
    assert "capability_id" in resp.payload["error"]


def test_computer_invoke_calls_connector(monkeypatch: pytest.MonkeyPatch) -> None:
    import kater.api.routes as routes

    connector = MagicMock()
    connector.call.return_value = {
        "protocol_version": "0.1.0-m0",
        "status": "succeeded",
        "request_id": "req_" + "a" * 32,
        "result": {},
        "artifacts": [],
    }
    monkeypatch.setattr(routes, "get_computer_connector", lambda: connector)

    resp = _call(
        "POST",
        "/api/computer/invoke",
        body={
            "capability_id": "filesystem.read",
            "computer_session_id": "csess_" + "a" * 32,
            "arguments": {"path": "README.md"},
        },
    )
    assert resp.status == 200
    assert resp.payload["status"] == "succeeded"
    connector.call.assert_called_once_with(
        "filesystem.read",
        {
            "computer_session_id": "csess_" + "a" * 32,
            "arguments": {"path": "README.md"},
        },
    )


def test_computer_status_redacts_to_host_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """
    Verify that the computer status response exposes only the configured host and redacts sensitive URL details.
    """
    import kater.api.routes as routes
    import kater.capabilities.wiring as wiring

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KATER_COMPUTER_URL", "http://guest.internal:8080/v1")
    monkeypatch.setenv("KATER_COMPUTER_TOKEN", "secret-token")
    connector = MagicMock()
    connector.profile = "core"
    connector.list_tools.return_value = [
        {"name": "filesystem.read", "description": "read", "inputSchema": {}}
    ]
    # routes.py imports get_computer_connector directly (so /capabilities and
    # /invoke resolve the routes-bound symbol), while /api/computer flows through
    # wiring.computer_status(), which calls wiring's own module-level reference.
    # Patch both so every computer route sees the mock connector.
    monkeypatch.setattr(routes, "get_computer_connector", lambda: connector)
    monkeypatch.setattr(wiring, "get_computer_connector", lambda: connector)

    resp = _call("GET", "/api/computer")
    assert resp.status == 200
    assert resp.payload["configured"] is True
    assert resp.payload["active"] is True
    assert resp.payload["base_url_host"] == "guest.internal"
    assert "secret" not in json.dumps(resp.payload)
    assert "8080" not in resp.payload["base_url_host"]
    assert resp.payload["capability_ids"] == ["filesystem.read"]


def test_openapi_documents_computer_paths() -> None:
    paths = generate_spec()["paths"]
    assert "get" in paths["/api/computer"]
    assert "get" in paths["/api/computer/capabilities"]
    assert "post" in paths["/api/computer/invoke"]


def test_cli_computer_status_unconfigured_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KATER_COMPUTER_URL", raising=False)
    monkeypatch.delenv("KATER_COMPUTER_TOKEN", raising=False)

    result = runner.invoke(app, ["computer", "status", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["configured"] is False
    assert payload["active"] is False


def test_cli_computer_capabilities_empty_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KATER_COMPUTER_URL", raising=False)
    monkeypatch.delenv("KATER_COMPUTER_TOKEN", raising=False)

    result = runner.invoke(app, ["computer", "capabilities", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload == {"tools": [], "total": 0}


def test_cli_computer_invoke_fails_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KATER_COMPUTER_URL", raising=False)
    monkeypatch.delenv("KATER_COMPUTER_TOKEN", raising=False)

    result = runner.invoke(app, ["computer", "invoke", "filesystem.read", "--json"])
    assert result.exit_code == 1
    assert "not configured" in result.output


def test_computer_configured_and_build(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from kater.capabilities.registry import reset_default_registry
    from kater.capabilities.wiring import (
        build_computer_connector,
        computer_configured,
        reset_computer_connector,
        set_computer_connector,
    )

    monkeypatch.chdir(tmp_path)
    reset_default_registry()
    reset_computer_connector()
    monkeypatch.setenv("KATER_COMPUTER_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("KATER_COMPUTER_TOKEN", "tok")
    monkeypatch.setenv("KATER_COMPUTER_PROFILE", "core")

    assert computer_configured() is True
    connector = build_computer_connector("core")
    assert connector is not None
    assert connector.base_url == "http://127.0.0.1:8080"
    assert connector.auth_token == "tok"
    set_computer_connector(connector)
    tools = connector.list_tools()
    assert tools
    assert all("name" in tool for tool in tools)
    reset_computer_connector()
    reset_default_registry()
