from __future__ import annotations

import stat
from pathlib import Path

from kater.settings import (
    AuthConfig,
    KaterSettings,
    RateLimiter,
    check_auth,
    load_settings,
    resolve_client_ip,
    save_settings,
)


def test_settings_default():
    settings = KaterSettings()
    assert settings.auth.mode == "none"
    assert settings.is_server_enabled("github") is True


def test_settings_enable_disable():
    settings = KaterSettings()
    settings.set_server_enabled("github", False)
    assert settings.is_server_enabled("github") is False
    settings.set_server_enabled("github", True)
    assert settings.is_server_enabled("github") is True


def test_settings_roundtrip(tmp_path: Path):
    settings = KaterSettings()
    settings.set_server_enabled("sentry", False)
    settings.auth = AuthConfig(mode="apikey", api_keys=["test123"])
    save_settings(settings, tmp_path)

    loaded = load_settings(tmp_path)
    assert loaded.auth.mode == "apikey"
    assert "test123" in loaded.auth.api_keys
    assert loaded.is_server_enabled("sentry") is False


def test_save_settings_uses_owner_only_permissions(tmp_path: Path):
    settings = KaterSettings(auth=AuthConfig(mode="apikey", api_keys=["secret"]))
    path = save_settings(settings, tmp_path)

    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_check_auth_none_mode():
    settings = KaterSettings()
    ok, err = check_auth(settings, None, None)
    assert ok is True
    assert err is None


def test_check_auth_apikey_valid():
    settings = KaterSettings(
        auth=AuthConfig(mode="apikey", api_keys=["secret-key"])
    )
    ok, err = check_auth(settings, "Bearer secret-key", None)
    assert ok is True


def test_check_auth_apikey_invalid():
    settings = KaterSettings(
        auth=AuthConfig(mode="apikey", api_keys=["secret-key"])
    )
    ok, err = check_auth(settings, "Bearer wrong", None)
    assert ok is False
    assert "Invalid" in err


def test_check_auth_apikey_missing():
    settings = KaterSettings(
        auth=AuthConfig(mode="apikey", api_keys=["secret-key"])
    )
    ok, err = check_auth(settings, None, None)
    assert ok is False
    assert "Missing" in err


def test_check_auth_apikey_via_query():
    settings = KaterSettings(
        auth=AuthConfig(mode="apikey", api_keys=["q-key"])
    )
    ok, err = check_auth(settings, None, "q-key")
    assert ok is True


def test_check_auth_apikey_query_disabled_in_public(monkeypatch):
    monkeypatch.setenv("KATER_PUBLIC", "1")
    settings = KaterSettings(
        auth=AuthConfig(mode="apikey", api_keys=["q-key"])
    )
    ok, err = check_auth(settings, None, "q-key")
    assert ok is False
    assert "Missing API key" in err


def test_resolve_client_ip_trusts_xff_only_from_trusted_peer(monkeypatch):
    monkeypatch.delenv("KATER_TRUST_PROXY", raising=False)
    assert resolve_client_ip("198.51.100.1, 10.0.0.2", "127.0.0.1") == "198.51.100.1"
    assert resolve_client_ip("198.51.100.1", "10.0.0.4") == "198.51.100.1"
    assert resolve_client_ip("198.51.100.1", "8.8.8.8") == "8.8.8.8"

    monkeypatch.setenv("KATER_TRUST_PROXY", "1")
    assert resolve_client_ip("198.51.100.1", "8.8.8.8") == "198.51.100.1"


def test_check_auth_oauth_valid_token():
    from kater.oauth import create_token, reset_state

    reset_state()
    token = create_token("client_test", "tools", "core")
    settings = KaterSettings(
        auth=AuthConfig(mode="oauth", oauth_issuer="https://auth.example.com")
    )
    ok, err = check_auth(settings, f"Bearer {token['access_token']}", None)
    assert ok is True
    reset_state()


def test_check_auth_oauth_invalid_token():
    from kater.oauth import reset_state

    reset_state()
    settings = KaterSettings(
        auth=AuthConfig(mode="oauth", oauth_issuer="https://auth.example.com")
    )
    ok, err = check_auth(settings, "Bearer tok_nonexistent", None)
    assert ok is False
    reset_state()


def test_rate_limiter_allows():
    limiter = RateLimiter(max_per_min=3)
    assert limiter.check("client1") is True
    assert limiter.check("client1") is True
    assert limiter.check("client1") is True
    assert limiter.check("client1") is False


def test_rate_limiter_disabled():
    limiter = RateLimiter(max_per_min=0)
    for _ in range(100):
        assert limiter.check("client1") is True


def test_rate_limiter_separate_clients():
    limiter = RateLimiter(max_per_min=1)
    assert limiter.check("client1") is True
    assert limiter.check("client2") is True
    assert limiter.check("client1") is False
