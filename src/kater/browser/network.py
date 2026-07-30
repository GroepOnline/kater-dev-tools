"""Playwright network guard and CDP endpoint SSRF checks for the browser lane."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

from kater.browser.base import BrowserUnavailableError
from kater.browser.policy import (
    BrowserPolicy,
    PolicyViolation,
    _addresses_from_getaddrinfo,
    _is_internal,
    _literal_ip,
)

# Hostnames / literals that are always treated as cloud-metadata SSRF targets.
_METADATA_HOSTS = frozenset(
    {
        "169.254.169.254",
        "metadata.google.internal",
        "metadata",
        "metadata.goog",
    }
)

_CDP_SCHEMES = frozenset({"ws", "wss", "http", "https"})
_BLOCKED_CDP_SCHEMES = frozenset({"file", "javascript", "data", "blob", "chrome", "about"})

PolicySource = BrowserPolicy | Callable[[], BrowserPolicy]


def install_network_guard(page: Any, policy: PolicySource) -> None:
    """Install a request guard that applies the current browser policy to every routed request.

    Parameters:
        page (Any): Playwright page on which to install the guard.
        policy (PolicySource): Static browser policy or callable that provides the current policy.
    """

    def _current() -> BrowserPolicy:
        """Return the current browser policy, evaluating the policy source when callable."""
        return policy() if callable(policy) else policy

    def _on_route(route: Any) -> None:
        req = route.request
        resource_type = getattr(req, "resource_type", "") or ""
        try:
            _current().check_request(req.url, resource_type=resource_type)
        except Exception:
            try:
                route.abort("blockedbyclient")
            except Exception:
                return
            return
        try:
            # Known limitation: policy validation resolves the hostname, but Chromium
            # resolves DNS again for the actual connection, so a rebinding answer can
            # differ from the validated one (TOCTOU). route.continue_() cannot pin the
            # connection to an address; closing this needs --host-resolver-rules at
            # browser launch (or an egress proxy). check_request() still blocks literal
            # non-public targets and hosts whose answers are non-public.
            route.continue_()
        except Exception:
            try:
                route.abort("blockedbyclient")
            except Exception:
                return

    page.route("**/*", _on_route)


def validate_cdp_endpoint(endpoint: str, *, steel_base_url: str | None = None) -> str:
    """
    Validate a CDP endpoint and enforce network access restrictions.

    Parameters:
        steel_base_url (str | None): Base URL used to determine whether loopback or private
            endpoints are permitted.

    Returns:
        str: The stripped endpoint URL.

    Raises:
        BrowserUnavailableError: If the endpoint is empty, malformed, lacks a host or scheme, or
            uses an unsupported scheme.
        PolicyViolation: If the endpoint targets a blocked scheme, metadata address, or disallowed
            network.
    """
    raw = (endpoint or "").strip()
    if not raw:
        raise BrowserUnavailableError("cdp endpoint is empty")

    try:
        parts = urlsplit(raw)
    except ValueError as exc:
        raise BrowserUnavailableError(f"cdp endpoint is not a valid URL: {raw!r}") from exc

    scheme = parts.scheme.lower()
    if not scheme:
        raise BrowserUnavailableError(f"cdp endpoint has no scheme: {raw!r}")
    if scheme in _BLOCKED_CDP_SCHEMES:
        raise PolicyViolation(f"cdp scheme '{scheme}:' is never allowed")
    if scheme not in _CDP_SCHEMES:
        raise BrowserUnavailableError(
            f"cdp endpoint scheme must be ws/wss/http(s), got '{scheme}:'"
        )

    host = (parts.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise BrowserUnavailableError(f"cdp endpoint has no host: {raw!r}")

    if host in _METADATA_HOSTS or host.endswith(".metadata.google.internal"):
        raise PolicyViolation(f"cdp host '{host}' is a metadata endpoint")

    try:
        port = parts.port or _default_port(scheme)
    except ValueError as exc:
        raise BrowserUnavailableError(f"cdp endpoint has an invalid port: {raw!r}") from exc

    endpoint_kind = _host_network_kind(host, port)
    allowed = _allowed_private_kind(steel_base_url)

    if endpoint_kind == "metadata":
        raise PolicyViolation(f"cdp host '{host}' resolves to a metadata address")
    if endpoint_kind == "loopback":
        # Plain CDP (steel_base_url is None) and local Steel both permit loopback.
        if allowed == "public":
            raise PolicyViolation(
                f"cdp host '{host}' is loopback but steel base url is not local"
            )
        return raw
    if endpoint_kind == "private":
        if allowed != "private":
            detail = (
                "local CDP allows loopback only"
                if steel_base_url is None
                else "steel base url is public"
            )
            raise PolicyViolation(f"cdp host '{host}' is non-public; {detail}")
        return raw
    if endpoint_kind == "unresolved":
        if steel_base_url is not None and _hosts_match(host, steel_base_url):
            # Same host as the Steel API (common); DNS may be unavailable in tests.
            return raw
        raise PolicyViolation(f"cdp host '{host}' could not be resolved")
    return raw


def _default_port(scheme: str) -> int:
    """Return the default port for a URL scheme.

    Parameters:
        scheme (str): URL scheme to classify.

    Returns:
        int: 443 for HTTPS or WSS schemes; 80 for all other schemes.
    """
    return 443 if scheme in {"https", "wss"} else 80


def _allowed_private_kind(steel_base_url: str | None) -> str:
    """Return which non-public endpoint kinds the steel/CDP pairing permits.

    * ``None`` (plain CDP) → ``loopback`` only
    * local/private Steel → ``private`` (includes loopback)
    * public Steel → ``public`` (no non-public CDP targets)
    """
    if steel_base_url is None:
        return "loopback"
    try:
        parts = urlsplit(steel_base_url.strip())
    except ValueError:
        return "public"
    host = (parts.hostname or "").strip().lower().rstrip(".")
    if not host:
        return "public"
    try:
        port = parts.port or _default_port(parts.scheme.lower() or "http")
    except ValueError:
        # Malformed port — fail closed and treat the pairing as public.
        return "public"
    kind = _host_network_kind(host, port)
    if kind in {"loopback", "private"}:
        return "private"
    return "public"


def _hosts_match(endpoint_host: str, steel_base_url: str) -> bool:
    """
    Determine whether an endpoint hostname matches the hostname in a Steel base URL.

    Parameters:
        endpoint_host (str): Normalized hostname to compare.
        steel_base_url (str): Steel base URL whose hostname is compared.

    Returns:
        bool: `true` if the hostnames match, `false` otherwise.
    """
    try:
        parts = urlsplit(steel_base_url.strip())
    except ValueError:
        return False
    steel_host = (parts.hostname or "").strip().lower().rstrip(".")
    return bool(steel_host) and steel_host == endpoint_host


def _host_network_kind(host: str, port: int) -> str:
    """
    Classify a hostname or IP address by its network accessibility.

    Parameters:
        host (str): Hostname or IP address to classify.
        port (int): Port used for hostname resolution.

    Returns:
        str: One of `"metadata"`, `"loopback"`, `"private"`, `"public"`, or `"unresolved"`.
    """
    if host in _METADATA_HOSTS:
        return "metadata"
    if host == "localhost" or host.endswith(".localhost"):
        return "loopback"

    literal = _literal_ip(host)
    if literal is not None:
        return _address_kind(literal)

    try:
        infos = socket.getaddrinfo(host, port)
    except OSError:
        return "unresolved"
    addresses = _addresses_from_getaddrinfo(infos)
    if not addresses:
        return "unresolved"
    kinds = {_address_kind(address) for address in addresses}
    if "metadata" in kinds:
        return "metadata"
    if "loopback" in kinds:
        return "loopback"
    if "private" in kinds:
        return "private"
    return "public"


def _address_kind(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
    """
    Classify an IP address by its network accessibility.

    Parameters:
        address (ipaddress.IPv4Address | ipaddress.IPv6Address): The IP address to classify.

    Returns:
        str: One of "metadata", "loopback", "private", or "public".
    """
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    if address == ipaddress.ip_address("169.254.169.254"):
        return "metadata"
    if address.is_loopback:
        return "loopback"
    if _is_internal(address):
        return "private"
    return "public"
