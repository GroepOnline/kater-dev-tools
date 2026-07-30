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
        """
        Validate that a URL is permitted for browser navigation.

        Parameters:
            url (str): The URL to validate.
            resolver (Resolver | None): Optional resolver used for hostname address checks.

        Raises:
            PolicyViolation: If the URL is empty, uses a disallowed scheme, has no host, violates
                domain restrictions, has an invalid port, or resolves to a disallowed address.
        """
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
        """
        Validate a browser navigation or network request against the active policy.

        Document requests use navigation scheme rules; other requests also permit
        `data:` and `blob:` while still enforcing blocked-scheme, domain, and
        private-network restrictions.

        Parameters:
            resource_type (str): Resource classification used to distinguish document
                navigations from subresource requests.
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
        """Validate that a host resolves only to publicly routable addresses.

        Parameters:
            host (str): Hostname or literal IP address to validate.
            port (int): Port used for hostname resolution.
            resolver (Resolver | None): Optional resolver to use for hostname lookup.

        Raises:
            PolicyViolation: If the host is internal, cannot be resolved, or resolves to no usable
                address.
        """
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
        """
        Convert the browser policy configuration to a serializable dictionary.

        Returns:
            dict[str, Any]: A dictionary containing the domain rules, network access setting,
                allowed schemes, and runtime limits.
        """
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
    """
    Return the URL port or a specified default when no port is present.

    Parameters:
        parts (SplitResult): Parsed URL components containing the port.
        default (int): Port to use when the URL does not specify one.

    Returns:
        int: The parsed URL port or the default port.

    Raises:
        PolicyViolation: If the URL contains an invalid port.
    """
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
    """
    Parse a host string as an IP address.

    Parameters:
        host (str): The host string to parse.

    Returns:
        ipaddress.IPv4Address | ipaddress.IPv6Address | None: The parsed IP address, or `None` if
            the host is not a valid IP address.
    """
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def _addresses_from_getaddrinfo(
    infos: Sequence[Any],
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """
    Extract usable IP addresses from getaddrinfo-style resolver results.

    Parameters:
        infos (Sequence[Any]): Resolver results containing socket address data.

    Returns:
        list[ipaddress.IPv4Address | ipaddress.IPv6Address]: Parsed IP addresses found in the
            results.
    """
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
    """
    Reject an address that is not publicly routable.

    Parameters:
        host (str): Hostname associated with the address.
        address (ipaddress.IPv4Address | ipaddress.IPv6Address): Resolved IP address to check.

    Raises:
        PolicyViolation: If the address is internal or otherwise non-public.
    """
    if _is_internal(address):
        raise PolicyViolation(
            f"host '{host}' resolves to non-public address {address} "
            "(set KATER_BROWSER_ALLOW_PRIVATE=1 to permit internal targets)"
        )


def _is_internal(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """
    Determine whether an IP address belongs to a non-public address range.

    Parameters:
        address (IPv4Address | IPv6Address): The IP address to classify.

    Returns:
        bool: `true` if the address is private, loopback, link-local, reserved, multicast, or
            unspecified, `false` otherwise.
    """
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
    """Read and trim a browser policy environment variable.

    Parameters:
        name (str): The environment variable suffix.

    Returns:
        str: The trimmed value, or an empty string if the variable is unset.
    """
    return os.environ.get(f"{ENV_PREFIX}{name}", "").strip()


def _env_truthy(name: str) -> bool:
    """Determine whether an environment variable contains a recognized truthy value.

    Parameters:
        name (str): The environment variable name without the configured prefix.

    Returns:
        bool: `True` if the value is one of the recognized truthy strings, `False` otherwise.
    """
    return _env(name).lower() in _TRUTHY


def _env_domains(name: str) -> tuple[str, ...]:
    """Parse a comma-separated environment value into normalized domain patterns."""
    raw = _env(name)
    if not raw:
        return ()
    return tuple(item.strip().lower() for item in raw.split(",") if item.strip())


def _env_int(name: str, default: int, *, minimum: int) -> int:
    """
    Parse an environment variable as an integer subject to a minimum value.

    Parameters:
        name (str): Environment variable name without the configured prefix.
        default (int): Value returned when the variable is missing, invalid, or below the minimum.
        minimum (int): Smallest accepted integer value.

    Returns:
        int: The parsed value when it meets the minimum; otherwise, the default value.
    """
    raw = _env(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= minimum else default
