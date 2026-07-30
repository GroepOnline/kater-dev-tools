"""Fail-closed navigation policy for the browser lane.

Mirrors the gateway's egress invariant: a browser handed to an agent
is an SSRF primitive, so every URL is checked before navigation *and* after it
(redirects), private address space is denied unless explicitly opted into, and
anything the checker cannot resolve is refused rather than allowed.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import SplitResult, urlsplit

from kater.settings import KaterSettings

Resolver = Callable[[str, int], Sequence[Any]]

ENV_PREFIX = "KATER_BROWSER_"

DEFAULT_MAX_SESSIONS = 4
DEFAULT_SESSION_TTL = 900
DEFAULT_ACTION_TIMEOUT_MS = 15_000
DEFAULT_MAX_SCREENSHOT_BYTES = 6_000_000

# Schemes that reach local files, inline payloads or browser internals. These
# are refused even if an operator widens ``allowed_schemes`` by mistake.
BLOCKED_SCHEMES = frozenset(
    {"file", "data", "javascript", "chrome", "about", "blob", "view-source"}
)

# Subresources may use data:/blob: (images, workers); still never file:/js:/chrome:.
_SUBRESOURCE_OK_SCHEMES = frozenset({"data", "blob"})
_SUBRESOURCE_BLOCKED_SCHEMES = frozenset({"file", "javascript", "chrome", "view-source", "about"})

# Playwright resource types treated as top-level navigations for domain policy.
_DOCUMENT_RESOURCE_TYPES = frozenset({"document", "nav", "navigation"})

_TRUTHY = frozenset({"1", "true", "yes", "on"})


class PolicyViolation(Exception):
    """Raised when a URL is not allowed by the active browser policy."""


@dataclass(frozen=True)
class BrowserPolicy:
    allow_domains: tuple[str, ...] = ()
    deny_domains: tuple[str, ...] = ()
    allow_private_networks: bool = False
    allowed_schemes: frozenset[str] = frozenset({"http", "https"})
    max_sessions: int = DEFAULT_MAX_SESSIONS
    session_ttl_seconds: int = DEFAULT_SESSION_TTL
    action_timeout_ms: int = DEFAULT_ACTION_TIMEOUT_MS
    max_screenshot_bytes: int = DEFAULT_MAX_SCREENSHOT_BYTES
    # Injected for tests and for callers that want their own DNS cache.
    resolver: Resolver | None = None

    def check_url(self, url: str, *, resolver: Resolver | None = None) -> None:
        """Raise :class:`PolicyViolation` unless the URL may be navigated to."""
        if not url or not url.strip():
            raise PolicyViolation("empty url")
        candidate = url.strip()
        if candidate.lower() == "about:blank":
            return

        parts = urlsplit(candidate)
        scheme = parts.scheme.lower()
        if not scheme:
            raise PolicyViolation(f"url has no scheme: {candidate!r}")
        if scheme in BLOCKED_SCHEMES:
            raise PolicyViolation(f"scheme '{scheme}:' is never allowed in the browser lane")
        if scheme not in self.allowed_schemes:
            allowed = ", ".join(sorted(self.allowed_schemes))
            raise PolicyViolation(f"scheme '{scheme}:' is not allowed (allowed: {allowed})")

        host = (parts.hostname or "").strip().lower().rstrip(".")
        if not host:
            raise PolicyViolation(f"url has no host: {candidate!r}")

        if _matches_domain(host, self.deny_domains):
            raise PolicyViolation(f"host '{host}' matches a denied domain")
        if self.allow_domains and not _matches_domain(host, self.allow_domains):
            raise PolicyViolation(f"host '{host}' is not in the browser allow-list")

        default_port = 443 if scheme == "https" else 80
        port = _port_or_default(parts, default_port)
        if not self.allow_private_networks:
            self._check_addresses(host, port, resolver)

    def check_request(self, url: str, *, resource_type: str = "") -> None:
        """Network-level check for every request (navigation + subresource).

        Document navigations use the full navigation policy (blocked schemes,
        allow/deny domains, private-network refusal). Subresources still refuse
        file:/javascript:/chrome: and private addresses, and allow ``data:`` /
        ``blob:``. The allow/deny domain lists are an egress boundary, so they
        are enforced for every request: a subresource fetch/XHR to a denied or
        non-allowlisted host is exactly the exfiltration path they must close.
        """
        if not url or not url.strip():
            raise PolicyViolation("empty url")
        candidate = url.strip()
        if candidate.lower() == "about:blank":
            return

        kind = (resource_type or "").strip().lower()
        is_document = kind in _DOCUMENT_RESOURCE_TYPES

        parts = urlsplit(candidate)
        scheme = parts.scheme.lower()
        if not scheme:
            raise PolicyViolation(f"url has no scheme: {candidate!r}")

        if is_document:
            if scheme in BLOCKED_SCHEMES:
                raise PolicyViolation(f"scheme '{scheme}:' is never allowed in the browser lane")
            if scheme not in self.allowed_schemes:
                allowed = ", ".join(sorted(self.allowed_schemes))
                raise PolicyViolation(f"scheme '{scheme}:' is not allowed (allowed: {allowed})")
        else:
            if scheme in _SUBRESOURCE_BLOCKED_SCHEMES:
                raise PolicyViolation(f"scheme '{scheme}:' is never allowed in the browser lane")
            if scheme in _SUBRESOURCE_OK_SCHEMES:
                return
            if scheme not in self.allowed_schemes and scheme not in {"ws", "wss"}:
                allowed = ", ".join(sorted(self.allowed_schemes | {"ws", "wss"}))
                raise PolicyViolation(f"scheme '{scheme}:' is not allowed (allowed: {allowed})")

        host = (parts.hostname or "").strip().lower().rstrip(".")
        if not host:
            raise PolicyViolation(f"url has no host: {candidate!r}")

        # Enforce the allow/deny lists for subresources too, not just documents:
        # otherwise a page could exfiltrate data via fetch/XHR/websocket to any
        # denied or non-allowlisted host, bypassing the egress boundary.
        if _matches_domain(host, self.deny_domains):
            raise PolicyViolation(f"host '{host}' matches a denied domain")
        if self.allow_domains and not _matches_domain(host, self.allow_domains):
            raise PolicyViolation(f"host '{host}' is not in the browser allow-list")

        default_port = 443 if scheme in {"https", "wss"} else 80
        port = _port_or_default(parts, default_port)
        if not self.allow_private_networks:
            self._check_addresses(host, port, None)

    def _check_addresses(self, host: str, port: int, resolver: Resolver | None) -> None:
        literal = _literal_ip(host)
        if literal is not None:
            _reject_internal(host, literal)
            return
        resolve = resolver or self.resolver or socket.getaddrinfo
        try:
            infos = resolve(host, port)
        except OSError as exc:
            raise PolicyViolation(f"host '{host}' could not be resolved: {exc}") from exc
        addresses = _addresses_from_getaddrinfo(infos)
        if not addresses:
            raise PolicyViolation(f"host '{host}' resolved to no usable address")
        for address in addresses:
            _reject_internal(host, address)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allow_domains": list(self.allow_domains),
            "deny_domains": list(self.deny_domains),
            "allow_private_networks": self.allow_private_networks,
            "allowed_schemes": sorted(self.allowed_schemes),
            "max_sessions": self.max_sessions,
            "session_ttl_seconds": self.session_ttl_seconds,
            "action_timeout_ms": self.action_timeout_ms,
            "max_screenshot_bytes": self.max_screenshot_bytes,
        }


def load_policy(settings: KaterSettings | None = None) -> BrowserPolicy:
    """Build the policy from ``KATER_BROWSER_*`` environment variables.

    ``settings`` is accepted so callers can pass an already-loaded
    :class:`~kater.settings.KaterSettings`; the browser lane currently has no
    settings-file fields of its own, and env stays the single source of truth.
    """
    del settings
    return BrowserPolicy(
        allow_domains=_env_domains("ALLOW_DOMAINS"),
        deny_domains=_env_domains("DENY_DOMAINS"),
        allow_private_networks=_env_truthy("ALLOW_PRIVATE"),
        max_sessions=_env_int("MAX_SESSIONS", DEFAULT_MAX_SESSIONS, minimum=1),
        session_ttl_seconds=_env_int("SESSION_TTL", DEFAULT_SESSION_TTL, minimum=1),
        action_timeout_ms=_env_int("ACTION_TIMEOUT_MS", DEFAULT_ACTION_TIMEOUT_MS, minimum=100),
        max_screenshot_bytes=_env_int(
            "MAX_SCREENSHOT_BYTES", DEFAULT_MAX_SCREENSHOT_BYTES, minimum=1024
        ),
    )


def _port_or_default(parts: SplitResult, default: int) -> int:
    try:
        port = parts.port
    except ValueError as exc:
        raise PolicyViolation(f"url has an invalid port: {exc}") from exc
    return default if port is None else port


def _matches_domain(host: str, patterns: tuple[str, ...]) -> bool:
    """Label-wise suffix match: ``evil.com`` matches ``a.evil.com``, not ``notevil.com``."""
    for raw in patterns:
        pattern = raw.strip().lower().lstrip("*.").strip(".")
        if not pattern:
            continue
        if host == pattern or host.endswith(f".{pattern}"):
            return True
    return False


def _literal_ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def _addresses_from_getaddrinfo(
    infos: Sequence[Any],
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        sockaddr = info[4] if len(info) >= 5 else None
        if not sockaddr:
            continue
        raw = str(sockaddr[0]).split("%", 1)[0]
        parsed = _literal_ip(raw)
        if parsed is not None:
            addresses.append(parsed)
    return addresses


def _reject_internal(
    host: str, address: ipaddress.IPv4Address | ipaddress.IPv6Address
) -> None:
    if _is_internal(address):
        raise PolicyViolation(
            f"host '{host}' resolves to non-public address {address} "
            "(set KATER_BROWSER_ALLOW_PRIVATE=1 to permit internal targets)"
        )


def _is_internal(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def _env(name: str) -> str:
    return os.environ.get(f"{ENV_PREFIX}{name}", "").strip()


def _env_truthy(name: str) -> bool:
    return _env(name).lower() in _TRUTHY


def _env_domains(name: str) -> tuple[str, ...]:
    raw = _env(name)
    if not raw:
        return ()
    return tuple(item.strip().lower() for item in raw.split(",") if item.strip())


def _env_int(name: str, default: int, *, minimum: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= minimum else default
