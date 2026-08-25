from __future__ import annotations

import io
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from kater.connectors import api as api_connector
from kater.connectors import registry
from kater.connectors.errors import ConnectorAuthError, ConnectorPolicyError
from kater.connectors.models import (
    AuthBindingKind,
    AuthBindingRef,
    ConnectorCapability,
    ConnectorRecord,
    ConnectorStatus,
    ConnectorTransport,
    ConnectorType,
    PermissionLevel,
)
from kater.connectors.store import clear_connector_state, upsert_connector
from kater.settings import KaterSettings, ServerOverride, save_settings


class _ClickHouseHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return

    def do_GET(self) -> None:
        if self.path == "/ping":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"pong")
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        if self.path == "/":
            length = int(self.headers.get("Content-Length") or 0)
            query = self.rfile.read(length).decode() if length else ""
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"query": query}).encode())
            return
        self.send_response(404)
        self.end_headers()


@pytest.fixture
def clickhouse_server():
    server = HTTPServer(("127.0.0.1", 0), _ClickHouseHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture(autouse=True)
def connector_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".kater").mkdir()
    clear_connector_state()
    yield
    clear_connector_state()
    os.environ.pop("CLICKHOUSE_TOKEN", None)


def _clickhouse_record(
    endpoint: str, *, auth_value: str | None = "ch-test-value"
) -> ConnectorRecord:
    if auth_value:
        os.environ["CLICKHOUSE_TOKEN"] = auth_value
    return ConnectorRecord(
        id="clickhouse",
        display_name="ClickHouse",
        type=ConnectorType.API,
        version="1.0.0",
        transport=ConnectorTransport(kind="http", endpoint=endpoint),
        capabilities=(
            ConnectorCapability(id="clickhouse.ping", description="ping"),
            ConnectorCapability(id="clickhouse.query", description="query"),
        ),
        auth_binding=AuthBindingRef(kind=AuthBindingKind.ENV, ref="CLICKHOUSE_TOKEN"),
        profiles=frozenset({"ops"}),
        permissions={"ops": PermissionLevel.READ},
        status=ConnectorStatus.ENABLED,
        metadata={"shape": "clickhouse"},
    )


def test_api_ping_and_query(clickhouse_server):
    record = _clickhouse_record(clickhouse_server)
    upsert_connector(record)

    ping = api_connector.invoke(record, "clickhouse.ping", {})
    assert ping["status"] == 200
    assert ping["body"] == "pong"

    query = api_connector.invoke(record, "clickhouse.query", {"query": "SELECT 1"})
    assert query["status"] == 200
    assert "SELECT" in query["body"]


def test_unresolved_header_template_is_not_sent(clickhouse_server, monkeypatch):
    monkeypatch.delenv("OPTIONAL_TENANT", raising=False)
    record = ConnectorRecord(
        id="header-proof",
        display_name="Header proof",
        type=ConnectorType.API,
        version="1.0.0",
        transport=ConnectorTransport(
            kind="http",
            endpoint=clickhouse_server,
            headers_template={"X-Tenant": "${OPTIONAL_TENANT}"},
        ),
        capabilities=(ConnectorCapability(id="header-proof.ping", description="ping"),),
        auth_binding=AuthBindingRef(kind=AuthBindingKind.NONE),
        profiles=frozenset({"ops"}),
        permissions={"ops": PermissionLevel.READ},
        status=ConnectorStatus.ENABLED,
        metadata={
            "operations": {
                "header-proof.ping": {"method": "GET", "path": "/ping"}
            }
        },
    )

    headers = api_connector._resolve_headers(record)
    assert "X-Tenant" not in headers


def test_api_auth_resolves_single_ref_from_settings(clickhouse_server, monkeypatch, tmp_path):
    monkeypatch.delenv("CLICKHOUSE_TOKEN", raising=False)
    save_settings(
        KaterSettings(
            server_overrides={
                "clickhouse": ServerOverride(env={"CLICKHOUSE_TOKEN": "settings-token"})
            }
        ),
        tmp_path,
    )
    record = _clickhouse_record(clickhouse_server, auth_value=None)

    headers = api_connector._resolve_headers(record)
    assert headers["Authorization"] == "Bearer settings-token"


def test_api_auth_multiple_refs_require_explicit_header_template(clickhouse_server, monkeypatch):
    monkeypatch.setenv("TOKEN_A", "a")
    monkeypatch.setenv("TOKEN_B", "b")
    record = _clickhouse_record(clickhouse_server, auth_value=None)
    record = ConnectorRecord.from_mapping(
        {
            **record.as_dict(),
            "auth_binding": {"kind": "env", "ref": "TOKEN_A,TOKEN_B"},
        }
    )

    with pytest.raises(ConnectorAuthError, match="explicit Authorization header template"):
        api_connector._resolve_headers(record)


def test_api_auth_missing(clickhouse_server):
    os.environ.pop("CLICKHOUSE_TOKEN", None)
    record = _clickhouse_record(clickhouse_server, auth_value=None)
    upsert_connector(record)

    with pytest.raises(ConnectorAuthError):
        api_connector.invoke(record, "clickhouse.ping", {})


def test_semicolon_inside_sql_literal_stays_read_only(clickhouse_server):
    record = _clickhouse_record(clickhouse_server)
    upsert_connector(record)

    result = registry.invoke(
        "clickhouse",
        "clickhouse.query",
        {"query": "SELECT 'a;b'"},
        profile="ops",
    )
    assert result["status"] == 200


def test_multi_statement_write_query_blocked_on_read_profile(clickhouse_server):
    record = _clickhouse_record(clickhouse_server)
    upsert_connector(record)

    with pytest.raises(ConnectorPolicyError):
        registry.invoke(
            "clickhouse",
            "clickhouse.query",
            {"query": "SELECT 1; INSERT INTO t VALUES (1)"},
            profile="ops",
        )


def test_write_query_blocked_on_read_profile(clickhouse_server):
    record = _clickhouse_record(clickhouse_server)
    upsert_connector(record)

    with pytest.raises(ConnectorPolicyError):
        registry.invoke(
            "clickhouse",
            "clickhouse.query",
            {"query": "INSERT INTO t VALUES (1)"},
            profile="ops",
        )


def test_write_query_allowed_on_write_profile(clickhouse_server):
    record = _clickhouse_record(clickhouse_server)
    record = ConnectorRecord.from_mapping(
        {
            **record.as_dict(),
            "permissions": {"ops": PermissionLevel.WRITE.value},
        }
    )
    upsert_connector(record)

    result = registry.invoke(
        "clickhouse",
        "clickhouse.query",
        {"query": "INSERT INTO t VALUES (1)"},
        profile="ops",
    )
    assert result["status"] == 200


def test_secret_not_in_error_text(clickhouse_server, monkeypatch):
    record = _clickhouse_record(clickhouse_server)
    upsert_connector(record)

    def _fail(*args, **kwargs):
        raise OSError("boom Bearer ch-test-value leaked")

    monkeypatch.setattr(api_connector.urllib.request, "urlopen", _fail)

    with pytest.raises(Exception) as exc:
        api_connector.invoke(record, "clickhouse.ping", {})
    assert "ch-test-value" not in str(exc.value)
    assert "[REDACTED]" in str(exc.value) or "***" in str(exc.value) or "boom" in str(exc.value)


def test_http_error_does_not_include_upstream_headers(clickhouse_server, monkeypatch):
    record = _clickhouse_record(clickhouse_server)
    headers = {"Set-Cookie": "session=upstream-secret", "X-Vendor-Token": "opaque-secret"}
    error = api_connector.urllib.error.HTTPError(
        url=f"{clickhouse_server}/",
        code=429,
        msg="rate limited",
        hdrs=headers,
        fp=io.BytesIO(b"try later"),
    )

    def _fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(api_connector.urllib.request, "urlopen", _fail)
    with pytest.raises(Exception) as exc:
        api_connector.invoke(record, "clickhouse.query", {"query": "SELECT 1"})
    text = str(exc.value)
    assert "upstream-secret" not in text
    assert "opaque-secret" not in text
    assert "HTTP 429: try later" in text
