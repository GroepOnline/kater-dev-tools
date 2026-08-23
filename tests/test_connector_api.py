from __future__ import annotations

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
        if self.path.startswith("/?"):
            query = self.path.split("query=", 1)[-1]
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


def test_api_auth_missing(clickhouse_server):
    os.environ.pop("CLICKHOUSE_TOKEN", None)
    record = _clickhouse_record(clickhouse_server, auth_value=None)
    upsert_connector(record)

    with pytest.raises(ConnectorAuthError):
        api_connector.invoke(record, "clickhouse.ping", {})


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
