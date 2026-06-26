from __future__ import annotations

import base64
import hashlib
import json
import socket
import struct
import threading
import time

import pytest

from kater.websocket import (
    WS_GUID,
    broadcast,
    broadcast_event,
    connected_clients_count,
    create_ws_server,
)


def _ws_handshake(sock: socket.socket) -> str:
    key = b"dGhlIHNhbXBsZSBub25jZSAxMjM0NTY3ODkwWQ=="
    request = (
        f"GET /ws HTTP/1.1\r\n"
        f"Host: localhost:9092\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key.decode()}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"\r\n"
    )
    sock.sendall(request.encode())
    response = b""
    while b"\r\n\r\n" not in response:
        response += sock.recv(4096)
    header_part = response.split(b"\r\n\r\n")[0]
    return header_part.decode()


def _ws_recv_all(sock: socket.socket, timeout: float = 1.0) -> list[str]:
    messages = []
    sock.settimeout(timeout)
    try:
        while True:
            msg = _ws_recv_text(sock, timeout=1.0)
            if not msg:
                break
            messages.append(msg)
    except (TimeoutError, OSError):
        pass
    return messages


def _ws_send_and_recv(
    sock: socket.socket, command: str, skip_welcome: bool = True
) -> str:
    if skip_welcome:
        _ws_recv_all(sock, timeout=0.3)
    _ws_send_text(sock, command)
    return _ws_recv_text(sock, timeout=2.0)


def _ws_send_text(sock: socket.socket, message: str) -> None:
    data = message.encode("utf-8")
    header = bytearray([0x81])
    mask_key = b"\x00\x01\x02\x03"
    if len(data) < 126:
        header.append(0x80 | len(data))
    elif len(data) < 65536:
        header.append(0x80 | 126)
        header.extend(struct.pack(">H", len(data)))
    else:
        header.append(0x80 | 127)
        header.extend(struct.pack(">Q", len(data)))
    header.extend(mask_key)
    masked = bytes(data[i] ^ mask_key[i % 4] for i in range(len(data)))
    sock.sendall(bytes(header) + masked)


def _ws_recv_text(sock: socket.socket, timeout: float = 2.0) -> str:
    sock.settimeout(timeout)
    first_two = sock.recv(2)
    if len(first_two) < 2:
        return ""
    b2 = first_two[1]
    length = b2 & 0x7F
    if length == 126:
        ext = sock.recv(2)
        length = struct.unpack(">H", ext)[0]
    elif length == 127:
        ext = sock.recv(8)
        length = struct.unpack(">Q", ext)[0]
    payload = b""
    while len(payload) < length:
        payload += sock.recv(length - len(payload))
    return payload.decode("utf-8")


@pytest.fixture
def ws_server():
    server = create_ws_server("127.0.0.1", 9093)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    yield server
    server.shutdown()
    server.server_close()
    time.sleep(0.2)


def test_websocket_handshake(ws_server) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3.0)
    sock.connect(("127.0.0.1", 9093))
    response = _ws_handshake(sock)
    assert "101" in response
    assert "Upgrade" in response
    expected = base64.b64encode(
        hashlib.sha1(b"dGhlIHNhbXBsZSBub25jZSAxMjM0NTY3ODkwWQ==" + WS_GUID.encode()).digest()
    ).decode()
    assert expected in response
    sock.close()


def test_websocket_ping_command(ws_server) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3.0)
    sock.connect(("127.0.0.1", 9093))
    _ws_handshake(sock)
    time.sleep(0.2)
    response = _ws_send_and_recv(sock, json.dumps({"cmd": "ping"}))
    data = json.loads(response)
    assert data.get("type") == "pong"
    sock.close()


def test_websocket_status_command(ws_server) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3.0)
    sock.connect(("127.0.0.1", 9093))
    _ws_handshake(sock)
    time.sleep(0.2)
    response = _ws_send_and_recv(sock, json.dumps({"cmd": "status"}))
    data = json.loads(response)
    assert "version" in data or "type" in data
    sock.close()


def test_broadcast_to_connected(ws_server) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3.0)
    sock.connect(("127.0.0.1", 9093))
    _ws_handshake(sock)
    time.sleep(0.3)
    assert connected_clients_count() >= 1
    _ws_recv_all(sock, timeout=0.3)
    broadcast_event({"type": "test_broadcast", "msg": "hello"})
    response = _ws_recv_text(sock, timeout=2.0)
    data = json.loads(response)
    assert data["type"] == "test_broadcast"
    sock.close()


def test_broadcast_string(ws_server) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3.0)
    sock.connect(("127.0.0.1", 9093))
    _ws_handshake(sock)
    time.sleep(0.3)
    _ws_recv_all(sock, timeout=0.3)
    broadcast("simple test message")
    response = _ws_recv_text(sock, timeout=2.0)
    assert "simple test message" in response
    sock.close()
