from __future__ import annotations

import socket

import pytest

from kater.browser.policy import (
    DEFAULT_ACTION_TIMEOUT_MS,
    DEFAULT_MAX_SESSIONS,
    DEFAULT_SESSION_TTL,
    BrowserPolicy,
    PolicyViolation,
    load_policy,
)

PUBLIC_IP = "93.184.216.34"


def resolver_for(*addresses: str):
    """Fake ``getaddrinfo`` returning fixed addresses, so tests never hit DNS."""

    def _resolve(host: str, port: int):
        """
        Resolve a host to the predefined socket addresses for deterministic tests.

        Returns:
            list[tuple]: Socket address records for each configured address.
        """
        del host, port
        return [
            (
                socket.AF_INET6 if ":" in address else socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                (address, 80),
            )
            for address in addresses
        ]

    return _resolve


def failing_resolver(host: str, port: int):
    """
    Raise a DNS resolution error for any host.

    Parameters:
        host (str): The hostname to include in the error message.
        port (int): The ignored service port.
    """
    del port
    raise socket.gaierror(f"cannot resolve {host}")


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "data:text/html,<h1>hi</h1>",
        "javascript:alert(1)",
        "chrome://settings",
        "about:config",
        "blob:https://example.com/abc",
        "view-source:https://example.com",
    ],
)
def test_dangerous_schemes_are_rejected(url):
    policy = BrowserPolicy(resolver=resolver_for(PUBLIC_IP))
    with pytest.raises(PolicyViolation, match="never allowed"):
        policy.check_url(url)


def test_about_blank_is_allowed():
    BrowserPolicy(resolver=failing_resolver).check_url("about:blank")


@pytest.mark.parametrize("url", ["ftp://example.com/x", "ws://example.com/socket"])
def test_non_http_schemes_are_rejected(url):
    policy = BrowserPolicy(resolver=resolver_for(PUBLIC_IP))
    with pytest.raises(PolicyViolation, match="is not allowed"):
        policy.check_url(url)


@pytest.mark.parametrize("url", ["", "   ", "https://", "not-a-url"])
def test_malformed_urls_are_rejected(url):
    policy = BrowserPolicy(resolver=resolver_for(PUBLIC_IP))
    with pytest.raises(PolicyViolation):
        policy.check_url(url)


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.5", "192.168.1.10", "172.16.4.4", "169.254.169.254", "0.0.0.0", "::1"],
)
def test_internal_addresses_are_rejected(address):
    policy = BrowserPolicy(resolver=resolver_for(address))
    with pytest.raises(PolicyViolation, match="non-public address"):
        policy.check_url("https://intranet.test/")


@pytest.mark.parametrize(
    "address", ["100.64.0.0", "100.64.1.1", "100.127.255.255", "::ffff:100.64.1.1", "198.18.0.1"]
)
def test_shared_address_space_is_rejected(address):
    """CGNAT and benchmarking ranges are not private per ``ipaddress`` but are not public."""
    policy = BrowserPolicy(resolver=resolver_for(address))
    with pytest.raises(PolicyViolation, match="non-public address"):
        policy.check_url("https://cgnat.test/")


@pytest.mark.parametrize("address", ["100.63.255.255", "100.128.0.0"])
def test_addresses_outside_shared_address_space_are_allowed(address):
    """Both sides of the ``100.64.0.0/10`` boundary stay reachable."""
    policy = BrowserPolicy(resolver=resolver_for(address))
    policy.check_url("https://public.test/")


def test_every_resolved_address_is_checked():
    """A host that resolves to one public and one internal address is refused."""
    policy = BrowserPolicy(resolver=resolver_for(PUBLIC_IP, "169.254.169.254"))
    with pytest.raises(PolicyViolation, match=r"169\.254\.169\.254"):
        policy.check_url("https://dns-rebind.test/")


def test_ipv4_mapped_ipv6_loopback_is_rejected():
    policy = BrowserPolicy(resolver=resolver_for("::ffff:127.0.0.1"))
    with pytest.raises(PolicyViolation, match="non-public address"):
        policy.check_url("https://mapped.test/")


def test_literal_internal_ip_needs_no_dns():
    policy = BrowserPolicy(resolver=failing_resolver)
    with pytest.raises(PolicyViolation, match="non-public address"):
        policy.check_url("http://127.0.0.1:8080/admin")


def test_unresolvable_host_fails_closed():
    policy = BrowserPolicy(resolver=failing_resolver)
    with pytest.raises(PolicyViolation, match="could not be resolved"):
        policy.check_url("https://nowhere.invalid/")


def test_host_resolving_to_nothing_fails_closed():
    policy = BrowserPolicy(resolver=lambda host, port: [])
    with pytest.raises(PolicyViolation, match="no usable address"):
        policy.check_url("https://empty.test/")


def test_public_host_passes():
    policy = BrowserPolicy(resolver=resolver_for(PUBLIC_IP))
    policy.check_url("https://example.com/path?q=1")


def test_allow_private_networks_opt_in():
    policy = BrowserPolicy(allow_private_networks=True, resolver=failing_resolver)
    policy.check_url("http://127.0.0.1:8123/page")
    policy.check_url("http://localhost:8123/page")


def test_deny_domains_match_subdomains_only_on_label_boundary():
    policy = BrowserPolicy(deny_domains=("evil.com",), resolver=resolver_for(PUBLIC_IP))
    with pytest.raises(PolicyViolation, match="denied domain"):
        policy.check_url("https://evil.com/")
    with pytest.raises(PolicyViolation, match="denied domain"):
        policy.check_url("https://a.evil.com/")
    policy.check_url("https://notevil.com/")


def test_deny_wins_over_allow():
    policy = BrowserPolicy(
        allow_domains=("example.com",),
        deny_domains=("secret.example.com",),
        resolver=resolver_for(PUBLIC_IP),
    )
    policy.check_url("https://docs.example.com/")
    with pytest.raises(PolicyViolation, match="denied domain"):
        policy.check_url("https://secret.example.com/")


def test_allow_list_blocks_everything_else():
    policy = BrowserPolicy(
        allow_domains=("example.com", "*.docs.test"), resolver=resolver_for(PUBLIC_IP)
    )
    policy.check_url("https://example.com/")
    policy.check_url("https://api.example.com/")
    policy.check_url("https://team.docs.test/")
    with pytest.raises(PolicyViolation, match="not in the browser allow-list"):
        policy.check_url("https://other.test/")


def test_host_case_and_trailing_dot_are_normalised():
    policy = BrowserPolicy(deny_domains=("evil.com",), resolver=resolver_for(PUBLIC_IP))
    with pytest.raises(PolicyViolation, match="denied domain"):
        policy.check_url("https://A.EVIL.COM./")


def test_resolver_argument_overrides_policy_field():
    policy = BrowserPolicy(resolver=resolver_for(PUBLIC_IP))
    with pytest.raises(PolicyViolation, match="non-public address"):
        policy.check_url("https://example.com/", resolver=resolver_for("10.1.2.3"))


def test_load_policy_defaults(monkeypatch):
    for name in (
        "ALLOW_DOMAINS",
        "DENY_DOMAINS",
        "ALLOW_PRIVATE",
        "MAX_SESSIONS",
        "SESSION_TTL",
        "ACTION_TIMEOUT_MS",
        "MAX_SCREENSHOT_BYTES",
    ):
        monkeypatch.delenv(f"KATER_BROWSER_{name}", raising=False)
    policy = load_policy()
    assert policy.allow_domains == ()
    assert policy.deny_domains == ()
    assert policy.allow_private_networks is False
    assert policy.max_sessions == DEFAULT_MAX_SESSIONS
    assert policy.session_ttl_seconds == DEFAULT_SESSION_TTL
    assert policy.action_timeout_ms == DEFAULT_ACTION_TIMEOUT_MS


def test_load_policy_reads_env(monkeypatch):
    monkeypatch.setenv("KATER_BROWSER_ALLOW_DOMAINS", "example.com, Docs.Test ")
    monkeypatch.setenv("KATER_BROWSER_DENY_DOMAINS", "evil.com")
    monkeypatch.setenv("KATER_BROWSER_ALLOW_PRIVATE", "yes")
    monkeypatch.setenv("KATER_BROWSER_MAX_SESSIONS", "7")
    monkeypatch.setenv("KATER_BROWSER_SESSION_TTL", "60")
    monkeypatch.setenv("KATER_BROWSER_ACTION_TIMEOUT_MS", "2500")
    policy = load_policy()
    assert policy.allow_domains == ("example.com", "docs.test")
    assert policy.deny_domains == ("evil.com",)
    assert policy.allow_private_networks is True
    assert policy.max_sessions == 7
    assert policy.session_ttl_seconds == 60
    assert policy.action_timeout_ms == 2500


@pytest.mark.parametrize("raw", ["not-a-number", "0", "-3"])
def test_load_policy_ignores_invalid_numbers(monkeypatch, raw):
    monkeypatch.setenv("KATER_BROWSER_MAX_SESSIONS", raw)
    assert load_policy().max_sessions == DEFAULT_MAX_SESSIONS


def test_policy_to_dict_is_json_safe():
    payload = BrowserPolicy(allow_domains=("a.test",)).to_dict()
    assert payload["allow_domains"] == ["a.test"]
    assert payload["allowed_schemes"] == ["http", "https"]
    assert payload["allow_private_networks"] is False
