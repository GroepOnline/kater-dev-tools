"""Ephemeral localhost ports for API fixture servers.

Self-hosted CI runs unit (matrix) and coverage concurrently on the same
pr-isolated host; fixed ports like 9912 collide across jobs. Bind 0 instead.
"""

from __future__ import annotations

import socket


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
