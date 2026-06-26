from __future__ import annotations

import base64
import hashlib
import json
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from kater.telemetry import status_overview

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

_clients: set[Any] = set()
_clients_lock = threading.Lock()


class WSClient:
    def __init__(self, sock: Any, rfile: Any, wfile: Any) -> None:
        self.sock = sock
        self.rfile = rfile
        self.wfile = wfile
        self.lock = threading.Lock()
        self.subscriptions: set[str] | None = None

    def send_text(self, message: str) -> None:
        data = message.encode("utf-8")
        frame = _encode_text_frame(data)
        with self.lock:
            try:
                self.wfile.write(frame)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

    def send_json(self, data: dict[str, Any]) -> None:
        self.send_text(json.dumps(data, ensure_ascii=False))

    def close(self) -> None:
        with _clients_lock:
            _clients.discard(self)
        try:
            self.sock.close()
        except OSError:
            pass


def _encode_text_frame(data: bytes) -> bytes:
    header = bytearray([0x81])
    length = len(data)
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.append(126)
        header.extend(struct.pack(">H", length))
    else:
        header.append(127)
        header.extend(struct.pack(">Q", length))
    return bytes(header) + data


def _encode_pong_frame(data: bytes = b"") -> bytes:
    header = bytearray([0x8A])
    length = len(data)
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.append(126)
        header.extend(struct.pack(">H", length))
    else:
        header.append(127)
        header.extend(struct.pack(">Q", length))
    return bytes(header) + data


def _send_close_frame(wfile: Any) -> None:
    try:
        wfile.write(bytes([0x88, 0x00]))
        wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass


def _read_frame(rfile: Any) -> tuple[int, bytes] | None:
    first_two = rfile.read(2)
    if len(first_two) < 2:
        return None
    b1, b2 = first_two[0], first_two[1]
    fin = bool(b1 & 0x80)
    opcode = b1 & 0x0F
    masked = bool(b2 & 0x80)
    length = b2 & 0x7F
    if length == 126:
        ext = rfile.read(2)
        if len(ext) < 2:
            return None
        length = struct.unpack(">H", ext)[0]
    elif length == 127:
        ext = rfile.read(8)
        if len(ext) < 8:
            return None
        length = struct.unpack(">Q", ext)[0]
    mask_key = rfile.read(4) if masked else b""
    payload = rfile.read(length) if length > 0 else b""
    if masked and payload:
        payload = bytes(payload[i] ^ mask_key[i % 4] for i in range(len(payload)))
    if not fin and opcode == 0x0:
        return (0x0, payload)
    return (opcode, payload)


class WSHandler(BaseHTTPRequestHandler):
    server_version = "KaterWS/1.0"

    def _do_handshake(self) -> bool:
        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            self.send_response(400)
            self.end_headers()
            return False
        digest = hashlib.sha1((key + WS_GUID).encode("ascii")).digest()
        accept = base64.b64encode(digest).decode("ascii")
        self.send_response(101)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        return True

    def _serve(self, client: WSClient) -> None:
        while True:
            try:
                frame = _read_frame(client.rfile)
            except (BrokenPipeError, ConnectionResetError, OSError):
                break
            if frame is None:
                break
            opcode, payload = frame
            if opcode == 0x8:
                _send_close_frame(client.wfile)
                break
            elif opcode == 0x9:
                pong = _encode_pong_frame(payload)
                with client.lock:
                    try:
                        client.wfile.write(pong)
                        client.wfile.flush()
                    except OSError:
                        break
            elif opcode == 0xA:
                continue
            elif opcode == 0x1:
                text = payload.decode("utf-8", errors="replace")
                self._handle_text(client, text)
            else:
                continue

    def _handle_text(self, client: WSClient, text: str) -> None:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            client.send_json({"type": "error", "error": "invalid_json"})
            return
        if not isinstance(data, dict):
            client.send_json({"type": "error", "error": "invalid_command"})
            return
        cmd = data.get("cmd")
        if cmd == "ping":
            client.send_json({"type": "pong", "t": time.time()})
        elif cmd == "status":
            client.send_json({"type": "status", "data": status_overview()})
        elif cmd == "subscribe":
            sub_type = data.get("type")
            if not isinstance(sub_type, str):
                client.send_json({"type": "error", "error": "missing_type"})
                return
            if client.subscriptions is None:
                client.subscriptions = set()
            client.subscriptions.add(sub_type)
            client.send_json(
                {
                    "type": "subscribed",
                    "subscriptions": sorted(client.subscriptions),
                }
            )
        elif cmd == "subscribe_all":
            client.subscriptions = None
            client.send_json({"type": "subscribed_all"})
        elif cmd == "unsubscribe":
            sub_type = data.get("type")
            if (
                isinstance(sub_type, str)
                and client.subscriptions is not None
                and sub_type in client.subscriptions
            ):
                client.subscriptions.discard(sub_type)
                if not client.subscriptions:
                    client.subscriptions = None
            client.send_json(
                {
                    "type": "unsubscribed",
                    "subscriptions": (
                        sorted(client.subscriptions) if client.subscriptions is not None else None
                    ),
                }
            )
        else:
            client.send_json({"type": "error", "error": f"unknown_cmd:{cmd}"})

    def do_GET(self) -> None:
        upgrade = self.headers.get("Upgrade", "").lower()
        if upgrade != "websocket":
            self.send_response(404)
            self.end_headers()
            return
        path = self.path.split("?", 1)[0].rstrip("/")
        if path != "/ws":
            self.send_response(404)
            self.end_headers()
            return
        if not self._check_auth():
            return
        if not self._do_handshake():
            return
        client = WSClient(self.connection, self.rfile, self.wfile)
        with _clients_lock:
            _clients.add(client)
            count = len(_clients)
        try:
            client.send_json({"type": "hello", "clients": count})
            self._serve(client)
        finally:
            client.close()

    def _check_auth(self) -> bool:
        from urllib.parse import parse_qs, urlparse

        from kater.authgate import AuthContext, authenticate
        from kater.settings import load_settings

        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        decision = authenticate(
            AuthContext(
                settings=load_settings(),
                authorization_header=self.headers.get("Authorization"),
                query_api_key=query.get("api_key", [None])[0],
            )
        )
        if not decision.allowed:
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": decision.error}).encode())
            return False
        return True

    def log_message(self, fmt: str, *args: Any) -> None:
        pass


class WSServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def connected_clients_count() -> int:
    with _clients_lock:
        return len(_clients)


def broadcast(message: str) -> None:
    with _clients_lock:
        clients = list(_clients)
    for client in clients:
        client.send_text(message)


def broadcast_event(event: dict[str, Any]) -> None:
    event_type = event.get("type") if isinstance(event, dict) else None
    message = json.dumps(event, ensure_ascii=False, default=str)
    with _clients_lock:
        clients = list(_clients)
    for client in clients:
        if client.subscriptions is None or event_type in client.subscriptions:
            client.send_text(message)


def create_ws_server(host: str = "0.0.0.0", port: int = 9092) -> ThreadingHTTPServer:
    return WSServer((host, port), WSHandler)


def serve_ws(host: str = "0.0.0.0", port: int = 9092) -> None:
    server = create_ws_server(host, port)
    server.serve_forever()
