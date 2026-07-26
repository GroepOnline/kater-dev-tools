"""Capability invoke audit log and context allowlist gating."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from kater.api import ROUTER, Request, Response
from kater.authgate import RequestIdentity
from kater.capabilities import audit as capability_audit
from kater.proxy.manager import ProxyManager


@pytest.fixture
def audit_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    capability_audit.reset_cache()
    yield tmp_path
    capability_audit.reset_cache()


def _call(
    method: str,
    path: str,
    *,
    query: dict[str, list[str]] | None = None,
) -> Response:
    matched = ROUTER.match(method, path)
    assert matched is not None, f"{method} {path} has no route"
    route, params = matched
    req = Request(
        method=method,
        path=path,
        query=query or {},
        headers={},
        raw_body=b"",
        client_ip="127.0.0.1",
        base_url="http://127.0.0.1",
        params=params,
    )
    return route.handler(req)


def test_record_and_query_capability_audit(audit_db) -> None:
    row_id = capability_audit.record_capability_audit(
        capability_id="kater.profiles.list",
        outcome="allowed",
        principal_id="agent-1",
        context_id="rctx_demo",
        reason=None,
        duration_ms=12.5,
        profile="core",
    )
    assert row_id > 0
    capability_audit.record_capability_audit(
        capability_id="web.search",
        outcome="denied",
        principal_id="agent-1",
        context_id="rctx_demo",
        reason="not in context allowlist",
        duration_ms=1.0,
        profile="core",
    )

    rows = capability_audit.query_capability_audit(limit=10)
    assert len(rows) == 2
    assert rows[0]["outcome"] == "denied"
    assert rows[1]["capability_id"] == "kater.profiles.list"

    filtered = capability_audit.query_capability_audit(capability_id="web.search")
    assert len(filtered) == 1
    assert filtered[0]["reason"] == "not in context allowlist"


def test_audit_api_lists_recent_rows(audit_db) -> None:
    capability_audit.record_capability_audit(
        capability_id="kater.profiles.list",
        outcome="allowed",
        principal_id="api-agent",
        context_id="rctx_api",
    )
    resp = _call("GET", "/api/audit/capabilities", query={"limit": ["5"]})
    assert resp.status == 200
    assert resp.payload is not None
    assert resp.payload["total"] >= 1
    assert resp.payload["events"][0]["capability_id"] == "kater.profiles.list"


def test_proxy_deny_writes_audit_row(audit_db) -> None:
    manager = ProxyManager()
    identity = RequestIdentity(
        principal_id="agent-deny",
        context_id="rctx_deny",
        allowed_capabilities=frozenset({"kater.profiles.list"}),
    )
    result = manager.call_tool("web.search", {"query": "x"}, identity=identity)
    assert result.get("code") == "capability_denied"
    assert result.get("reason") == "not in context allowlist"

    rows = capability_audit.query_capability_audit(context_id="rctx_deny")
    assert len(rows) == 1
    assert rows[0]["outcome"] == "denied"
    assert rows[0]["capability_id"] == "web.search"
    assert rows[0]["principal_id"] == "agent-deny"


def test_proxy_allow_writes_audit_row(audit_db, monkeypatch) -> None:
    manager = ProxyManager()
    manager._computer_connector = None
    monkeypatch.setattr(
        "kater.proxy.manager.assert_invocable",
        lambda _name: None,
    )
    monkeypatch.setattr(manager, "_aggregator", MagicMock())
    manager._aggregator.resolve.return_value = None

    def _logical(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "name": name, "arguments": arguments}

    monkeypatch.setattr(manager, "_call_logical_tool", _logical)

    identity = RequestIdentity(
        principal_id="agent-allow",
        context_id="rctx_allow",
        allowed_capabilities=frozenset({"kater.profiles"}),
    )
    result = manager.call_tool("kater.profiles.list", {}, identity=identity)
    assert result.get("ok") is True

    rows = capability_audit.query_capability_audit(context_id="rctx_allow")
    assert len(rows) == 1
    assert rows[0]["outcome"] == "allowed"
    assert rows[0]["capability_id"] == "kater.profiles.list"


def test_unrestricted_identity_skips_allowlist(audit_db, monkeypatch) -> None:
    manager = ProxyManager()
    manager._computer_connector = None
    monkeypatch.setattr(
        "kater.proxy.manager.assert_invocable",
        lambda _name: None,
    )
    monkeypatch.setattr(manager, "_aggregator", MagicMock())
    manager._aggregator.resolve.return_value = None
    monkeypatch.setattr(
        manager,
        "_call_logical_tool",
        lambda name, arguments: {"ok": True, "name": name},
    )

    result = manager.call_tool(
        "anything.goes",
        {},
        identity=RequestIdentity(principal_id="open"),
    )
    assert result.get("ok") is True
    rows = capability_audit.query_capability_audit(limit=5)
    assert rows[0]["outcome"] == "allowed"
