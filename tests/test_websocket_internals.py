from __future__ import annotations

import io
import json
import struct

from kater.websocket import (
    MAX_FRAME_SIZE,
    WSClient,
    WSHandler,
    _encode_pong_frame,
    _encode_text_frame,
    _read_frame,
    _send_close_frame,
    consume_ws_ticket,
    issue_ws_ticket,
)

# ── Frame encoding ─────────────────────────────────────────────────


def test_encode_text_frame_small() -> None:
    data = b"hello"
    frame = _encode_text_frame(data)
    assert frame[0] == 0x81  # text opcode, FIN
    assert frame[1] == len(data)
    assert frame[2:] == data


def test_encode_text_frame_medium() -> None:
    data = b"x" * 200
    frame = _encode_text_frame(data)
    assert frame[0] == 0x81
    assert frame[1] == 126
    ext_len = struct.unpack(">H", frame[2:4])[0]
    assert ext_len == 200
    assert frame[4:] == data


def test_encode_text_frame_large() -> None:
    data = b"x" * 70000
    frame = _encode_text_frame(data)
    assert frame[0] == 0x81
    assert frame[1] == 127
    ext_len = struct.unpack(">Q", frame[2:10])[0]
    assert ext_len == 70000
    assert frame[10:] == data


def test_encode_pong_frame_small() -> None:
    frame = _encode_pong_frame(b"pong")
    assert frame[0] == 0x8A  # pong opcode, FIN
    assert frame[1] == 4


def test_encode_pong_frame_large() -> None:
    data = b"y" * 200
    frame = _encode_pong_frame(data)
    assert frame[0] == 0x8A
    assert frame[1] == 126
    ext_len = struct.unpack(">H", frame[2:4])[0]
    assert ext_len == 200


# ── Close frame ────────────────────────────────────────────────────


def test_send_close_frame() -> None:
    buf = io.BytesIO()
    _send_close_frame(buf)
    data = buf.getvalue()
    assert data[0] == 0x88  # close opcode
    assert data[1] == 0x00  # zero length


def test_send_close_frame_broken_pipe() -> None:
    """_send_close_frame silently handles write errors."""

    class FailingWriter:
        def write(self, data):
            raise BrokenPipeError()

        def flush(self):
            pass

    # Should not raise
    _send_close_frame(FailingWriter())


# ── Read frame ─────────────────────────────────────────────────────


def test_read_frame_text() -> None:
    payload = b"hello ws"
    header = bytearray([0x81, len(payload)])
    buf = io.BytesIO(bytes(header) + payload)
    opcode, data = _read_frame(buf)
    assert opcode == 0x1
    assert data == payload


def test_read_frame_close() -> None:
    buf = io.BytesIO(bytes([0x88, 0x00]))
    opcode, data = _read_frame(buf)
    assert opcode == 0x8
    assert data == b""


def test_read_frame_ping() -> None:
    buf = io.BytesIO(bytes([0x89, 0x00]))
    opcode, data = _read_frame(buf)
    assert opcode == 0x9


def test_read_frame_pong() -> None:
    buf = io.BytesIO(bytes([0x8A, 0x00]))
    opcode, data = _read_frame(buf)
    assert opcode == 0xA


def test_read_frame_short_header_returns_none() -> None:
    buf = io.BytesIO(b"\x81")  # only one byte
    result = _read_frame(buf)
    assert result is None


def test_read_frame_medium_length() -> None:
    payload = b"x" * 200
    header = bytearray([0x81, 126])
    header.extend(struct.pack(">H", 200))
    buf = io.BytesIO(bytes(header) + payload)
    opcode, data = _read_frame(buf)
    assert opcode == 0x1
    assert len(data) == 200


def test_read_frame_large_length() -> None:
    payload = b"x" * 70000
    header = bytearray([0x81, 127])
    header.extend(struct.pack(">Q", 70000))
    buf = io.BytesIO(bytes(header) + payload)
    opcode, data = _read_frame(buf)
    assert opcode == 0x1
    assert len(data) == 70000


def test_read_frame_exceeds_max_returns_none() -> None:
    payload = b"x" * (MAX_FRAME_SIZE + 1)
    header = bytearray([0x81, 127])
    header.extend(struct.pack(">Q", MAX_FRAME_SIZE + 1))
    buf = io.BytesIO(bytes(header) + payload)
    result = _read_frame(buf)
    assert result is None


def test_read_frame_masked() -> None:
    payload = b"secret"
    mask_key = b"\x01\x02\x03\x04"
    masked_payload = bytes(payload[i] ^ mask_key[i % 4] for i in range(len(payload)))
    header = bytearray([0x81, 0x80 | len(payload)])
    buf = io.BytesIO(bytes(header) + mask_key + masked_payload)
    opcode, data = _read_frame(buf)
    assert opcode == 0x1
    assert data == payload


def test_read_frame_continuation() -> None:
    payload = b"cont"
    header = bytearray([0x00, len(payload)])
    buf = io.BytesIO(bytes(header) + payload)
    opcode, data = _read_frame(buf)
    assert opcode == 0x0
    assert data == payload


def test_read_frame_truncated_medium_length() -> None:
    header = bytearray([0x81, 126])
    buf = io.BytesIO(bytes(header))
    result = _read_frame(buf)
    assert result is None


def test_read_frame_truncated_large_length() -> None:
    header = bytearray([0x81, 127])
    buf = io.BytesIO(bytes(header) + b"\x00" * 4)  # only 4 of 8 ext bytes
    result = _read_frame(buf)
    assert result is None


# ── Tickets ────────────────────────────────────────────────────────


def test_issue_and_consume_ticket() -> None:
    ticket = issue_ws_ticket()
    assert len(ticket) > 0
    assert consume_ws_ticket(ticket) is True
    # Already consumed
    assert consume_ws_ticket(ticket) is False


def test_consume_none_ticket() -> None:
    assert consume_ws_ticket(None) is False


def test_consume_invalid_ticket() -> None:
    assert consume_ws_ticket("invalid_ticket_12345") is False


# ── WSClient ───────────────────────────────────────────────────────


def test_wsclient_send_text() -> None:
    buf = io.BytesIO()

    class FakeSock:
        pass

    client = WSClient(FakeSock(), io.BytesIO(), buf)
    client.send_text("test message")
    data = buf.getvalue()
    assert data[0] == 0x81


def test_wsclient_send_json() -> None:
    buf = io.BytesIO()

    class FakeSock:
        pass

    client = WSClient(FakeSock(), io.BytesIO(), buf)
    client.send_json({"type": "test", "value": 42})
    data = buf.getvalue()
    assert data[0] == 0x81


def test_wsclient_send_text_broken_pipe() -> None:
    """send_text handles write errors silently."""

    class FailingWriter:
        def write(self, data):
            raise BrokenPipeError()

        def flush(self):
            pass

    client = WSClient(None, None, FailingWriter())
    client.send_text("hello")  # should not raise


def test_wsclient_close_handles_os_error() -> None:
    """close() handles OSError on socket close."""

    class FailingSock:
        def close(self):
            raise OSError("already closed")

    client = WSClient(FailingSock(), io.BytesIO(), io.BytesIO())
    client.close()  # should not raise


# ── WSHandler — _handle_text ────────────────────────────────────────


def _decode_frame_text(raw: bytes) -> str:
    """Extract the text payload from a WebSocket text frame written by send_text."""
    if len(raw) < 2:
        return ""
    b1, b2 = raw[0], raw[1]
    assert b1 == 0x81, f"expected text frame, got {b1:#x}"
    length = b2 & 0x7F
    offset = 2
    if length == 126:
        length = struct.unpack(">H", raw[2:4])[0]
        offset = 4
    elif length == 127:
        length = struct.unpack(">Q", raw[2:10])[0]
        offset = 10
    payload = raw[offset : offset + length]
    return payload.decode("utf-8")


# ── WSHandler — _handle_text ────────────────────────────────────────


def _make_handler() -> WSHandler:
    """Create a minimal WSHandler with fake request attributes."""

    class FakeHandler(WSHandler):
        def __init__(self):
            self.path = "/ws"
            self.headers = {}
            self.client_address = ("127.0.0.1", 12345)
            self.wfile = io.BytesIO()
            self.rfile = io.BytesIO()
            self.connection = None
            self._status = None
            self._sent_headers = []

        def send_response(self, code, *args):
            self._status = code

        def send_header(self, key, value):
            self._sent_headers.append((key, value))

        def end_headers(self):
            pass

    return FakeHandler()


def _make_client() -> WSClient:
    """Create a WSClient paired with a BytesIO for capturing output."""

    class FakeSock:
        pass

    return WSClient(FakeSock(), io.BytesIO(), io.BytesIO())


def _client_json(client: WSClient) -> dict:
    """Read the JSON payload from the client's wfile buffer."""
    raw = client.wfile.getvalue()
    text = _decode_frame_text(raw)
    return json.loads(text)


def test_handle_text_ping() -> None:
    h = _make_handler()
    c = _make_client()
    h._handle_text(c, json.dumps({"cmd": "ping"}))
    data = _client_json(c)
    assert data["type"] == "pong"


def test_handle_text_status(monkeypatch) -> None:
    monkeypatch.setattr(
        "kater.telemetry.status_overview",
        lambda: {
            "version": "1.0.0", "profile": "core", "auth_mode": "none",
            "servers": {"total": 0, "enabled": 0, "configured": 0},
            "telemetry": {"total_events": 0, "tool_calls": 0, "errors": 0, "success_rate": 100},
            "api_port": 9091, "mcp_port": 9090, "rate_limit": 0, "storage_backend": "sqlite",
        },
    )
    h = _make_handler()
    c = _make_client()
    h._handle_text(c, json.dumps({"cmd": "status"}))
    data = _client_json(c)
    assert data["type"] == "status"


def test_handle_text_subscribe() -> None:
    h = _make_handler()
    c = _make_client()
    h._handle_text(c, json.dumps({"cmd": "subscribe", "type": "tool_call"}))
    data = _client_json(c)
    assert data["type"] == "subscribed"
    assert "tool_call" in data["subscriptions"]


def test_handle_text_subscribe_missing_type() -> None:
    h = _make_handler()
    c = _make_client()
    h._handle_text(c, json.dumps({"cmd": "subscribe"}))
    data = _client_json(c)
    assert data["type"] == "error"
    assert "missing_type" in data["error"]


def test_handle_text_subscribe_all() -> None:
    h = _make_handler()
    c = _make_client()
    c.subscriptions = {"tool_call"}
    h._handle_text(c, json.dumps({"cmd": "subscribe_all"}))
    data = _client_json(c)
    assert data["type"] == "subscribed_all"
    assert c.subscriptions is None


def test_handle_text_unsubscribe() -> None:
    h = _make_handler()
    c = _make_client()
    c.subscriptions = {"tool_call", "error"}
    h._handle_text(c, json.dumps({"cmd": "unsubscribe", "type": "tool_call"}))
    data = _client_json(c)
    assert data["type"] == "unsubscribed"
    assert data["subscriptions"] == ["error"]


def test_handle_text_unsubscribe_last() -> None:
    h = _make_handler()
    c = _make_client()
    c.subscriptions = {"tool_call"}
    h._handle_text(c, json.dumps({"cmd": "unsubscribe", "type": "tool_call"}))
    data = _client_json(c)
    assert data["type"] == "unsubscribed"
    assert data["subscriptions"] is None
    assert c.subscriptions is None


def test_handle_text_unknown_cmd() -> None:
    h = _make_handler()
    c = _make_client()
    h._handle_text(c, json.dumps({"cmd": "unknown_command_xyz"}))
    data = _client_json(c)
    assert data["type"] == "error"
    assert "unknown_cmd" in data["error"]


def test_handle_text_invalid_json() -> None:
    h = _make_handler()
    c = _make_client()
    h._handle_text(c, "not json at all")
    data = _client_json(c)
    assert data["type"] == "error"
    assert data["error"] == "invalid_json"


def test_handle_text_not_a_dict() -> None:
    h = _make_handler()
    c = _make_client()
    h._handle_text(c, json.dumps(["list", "not", "dict"]))
    data = _client_json(c)
    assert data["type"] == "error"
    assert data["error"] == "invalid_command"


# ── WSHandler — do_GET ─────────────────────────────────────────────


def test_do_get_not_websocket() -> None:
    h = _make_handler()
    h.headers = {"Upgrade": "h2c"}
    h.do_GET()
    assert h._status == 404


def test_do_get_wrong_path() -> None:
    h = _make_handler()
    h.headers = {"Upgrade": "websocket"}
    h.path = "/not-ws"
    h.do_GET()
    assert h._status == 404


# ── Authorization header ───────────────────────────────────────────


def test_authorization_header_from_header() -> None:
    h = _make_handler()
    h.headers = {"Authorization": "Bearer my-token"}
    from urllib.parse import parse_qs

    result = h._authorization_header(parse_qs(""), allow_query_token=True)
    assert result == "Bearer my-token"


def test_authorization_header_from_query() -> None:
    h = _make_handler()
    h.headers = {}
    from urllib.parse import parse_qs

    result = h._authorization_header(parse_qs("token=my-query-token"), allow_query_token=True)
    assert result == "Bearer my-query-token"


def test_authorization_header_query_disabled() -> None:
    h = _make_handler()
    h.headers = {}
    from urllib.parse import parse_qs

    result = h._authorization_header(parse_qs("token=my-query-token"), allow_query_token=False)
    assert result is None


def test_authorization_header_none() -> None:
    h = _make_handler()
    h.headers = {}
    from urllib.parse import parse_qs

    result = h._authorization_header(parse_qs(""), allow_query_token=True)
    assert result is None


# ── WSHandler — _check_auth ────────────────────────────────────────


def test_check_auth_with_valid_ticket() -> None:
    ticket = issue_ws_ticket()
    h = _make_handler()
    h.path = f"/ws?ticket={ticket}"
    assert h._check_auth() is True


def test_check_auth_without_auth_returns_401(monkeypatch) -> None:
    # Ensure public mode + apikey auth so auth is required but no token is present
    from kater.settings import AuthConfig, KaterSettings, save_settings

    monkeypatch.setenv("KATER_PUBLIC", "1")
    save_settings(KaterSettings(auth=AuthConfig(mode="apikey", api_keys=["test-key"])))
    h = _make_handler()
    h.path = "/ws"
    result = h._check_auth()
    assert result is False
    assert h._status == 401
