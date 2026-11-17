from __future__ import annotations

import os
import stat
import threading
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


def test_load_settings_serializes_cache_publish_with_save(tmp_path: Path, monkeypatch):
    import kater.settings as settings_module

    initial = KaterSettings()
    updated = KaterSettings()
    updated.set_server_enabled("github", False)
    save_settings(initial, tmp_path)
    settings_module.invalidate_settings_cache(tmp_path)

    reader_paused = threading.Event()
    allow_publish = threading.Event()
    writer_started = threading.Event()
    writer_done = threading.Event()
    errors: list[BaseException] = []
    apply_security_overrides = settings_module._apply_env_security_overrides

    def pause_before_cache_publish(settings):
        if threading.current_thread().name == "settings-reader":
            reader_paused.set()
            if not allow_publish.wait(timeout=5):
                raise TimeoutError("reader was not released")
        return apply_security_overrides(settings)

    monkeypatch.setattr(
        settings_module, "_apply_env_security_overrides", pause_before_cache_publish
    )

    def read_settings():
        try:
            load_settings(tmp_path)
        except BaseException as exc:
            errors.append(exc)

    def write_settings():
        writer_started.set()
        try:
            save_settings(updated, tmp_path)
        except BaseException as exc:
            errors.append(exc)
        finally:
            writer_done.set()

    reader = threading.Thread(target=read_settings, name="settings-reader")
    writer = threading.Thread(target=write_settings, name="settings-writer")
    reader.start()
    assert reader_paused.wait(timeout=5)
    writer.start()
    assert writer_started.wait(timeout=5)
    try:
        assert not writer_done.wait(timeout=0.5)
    finally:
        allow_publish.set()
        reader.join(timeout=5)
        writer.join(timeout=5)

    assert not reader.is_alive()
    assert not writer.is_alive()
    assert not errors
    assert load_settings(tmp_path).is_server_enabled("github") is False


def test_explicit_local_auth_env_overrides_persisted_mode(tmp_path: Path, monkeypatch):
    """A loopback fleet unit must be able to override stale persisted auth."""
    save_settings(KaterSettings(auth=AuthConfig(mode="oauth")), tmp_path)
    monkeypatch.setenv("KATER_HOST", "127.0.0.1")
    monkeypatch.setenv("KATER_PUBLIC", "0")
    monkeypatch.setenv("KATER_AUTH_MODE", "none")

    loaded = load_settings(tmp_path)

    assert loaded.auth.mode == "none"
    assert os.environ["KATER_AUTH_MODE"] == "none"


def test_public_deploy_does_not_inherit_persisted_none_auth(tmp_path: Path, monkeypatch):
    """Persisted local state must not silently disable auth after public exposure."""
    save_settings(KaterSettings(auth=AuthConfig(mode="none")), tmp_path)
    monkeypatch.setenv("KATER_HOST", "0.0.0.0")
    monkeypatch.setenv("KATER_PUBLIC", "0")
    monkeypatch.delenv("KATER_AUTH_MODE", raising=False)

    loaded = load_settings(tmp_path)

    assert loaded.auth.mode == "oauth"


def test_public_tunnel_does_not_inherit_persisted_none_auth(tmp_path: Path, monkeypatch):
    """KATER_PUBLIC also makes loopback-backed tunnel deployments fail closed."""
    save_settings(KaterSettings(auth=AuthConfig(mode="none")), tmp_path)
    monkeypatch.setenv("KATER_HOST", "127.0.0.1")
    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.delenv("KATER_AUTH_MODE", raising=False)

    loaded = load_settings(tmp_path)

    assert loaded.auth.mode == "oauth"


def test_explicit_public_none_auth_remains_operator_authoritative(tmp_path: Path, monkeypatch):
    """An explicit runtime auth mode remains authoritative even for public mode."""
    save_settings(KaterSettings(auth=AuthConfig(mode="oauth")), tmp_path)
    monkeypatch.setenv("KATER_HOST", "127.0.0.1")
    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_AUTH_MODE", "none")

    loaded = load_settings(tmp_path)

    assert loaded.auth.mode == "none"


def test_save_settings_uses_owner_only_permissions(tmp_path: Path):
    import os

    import pytest

    if os.name == "nt":
        pytest.skip("Windows does not support POSIX permission modes")

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
    settings = KaterSettings(auth=AuthConfig(mode="apikey", api_keys=["secret-key"]))
    ok, err = check_auth(settings, "Bearer secret-key", None)
    assert ok is True


def test_check_auth_apikey_invalid():
    settings = KaterSettings(auth=AuthConfig(mode="apikey", api_keys=["secret-key"]))
    ok, err = check_auth(settings, "Bearer wrong", None)
    assert ok is False
    assert "Invalid" in err


def test_check_auth_apikey_missing():
    settings = KaterSettings(auth=AuthConfig(mode="apikey", api_keys=["secret-key"]))
    ok, err = check_auth(settings, None, None)
    assert ok is False
    assert "Missing" in err


def test_check_auth_apikey_via_query():
    settings = KaterSettings(auth=AuthConfig(mode="apikey", api_keys=["q-key"]))
    ok, err = check_auth(settings, None, "q-key")
    assert ok is True


def test_check_auth_apikey_query_disabled_in_public(monkeypatch):
    monkeypatch.setenv("KATER_PUBLIC", "1")
    settings = KaterSettings(auth=AuthConfig(mode="apikey", api_keys=["q-key"]))
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
    settings = KaterSettings(auth=AuthConfig(mode="oauth", oauth_issuer="https://auth.example.com"))
    ok, err = check_auth(settings, f"Bearer {token['access_token']}", None)
    assert ok is True
    reset_state()


def test_check_auth_oauth_invalid_token():
    from kater.oauth import reset_state

    reset_state()
    settings = KaterSettings(auth=AuthConfig(mode="oauth", oauth_issuer="https://auth.example.com"))
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
