from __future__ import annotations

from kater.settings import _is_public_deploy, load_settings


def test_public_flag_enables_secure_defaults(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_HOST", "127.0.0.1")
    monkeypatch.delenv("KATER_AUTH_MODE", raising=False)
    settings = load_settings()
    assert settings.auth.mode == "oauth"
    assert settings.rate_limit_per_min == 60


def test_public_apikey_requires_explicit_key(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_AUTH_MODE", "apikey")
    monkeypatch.setenv("KATER_API_KEY", "test-key-abc")
    settings = load_settings()
    assert settings.auth.mode == "apikey"
    assert "test-key-abc" in settings.auth.api_keys


def test_public_env_overrides_persisted_settings(monkeypatch, tmp_path) -> None:
    from kater.settings import AuthConfig, KaterSettings, save_settings

    save_settings(
        KaterSettings(auth=AuthConfig(mode="none")),
        tmp_path,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_AUTH_MODE", "oauth")
    settings = load_settings(tmp_path)
    assert settings.auth.mode == "oauth"


def test_is_public_deploy_loopback_without_flag() -> None:
    assert _is_public_deploy("127.0.0.1") is False


def test_is_public_deploy_with_public_flag(monkeypatch) -> None:
    monkeypatch.setenv("KATER_PUBLIC", "1")
    assert _is_public_deploy("127.0.0.1") is True
