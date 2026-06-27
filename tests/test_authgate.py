"""Tests for authgate.py — the single authentication gate for all transports.

Covers: authenticate(), should_proxy_to_api(), _is_public_path(), and the
AuthContext/AuthDecision dataclasses.
"""

from __future__ import annotations

import pytest

from kater.authgate import (
    AuthContext,
    authenticate,
    should_proxy_to_api,
)
from kater.settings import KaterSettings


@pytest.fixture
def no_auth_settings():
    return KaterSettings()


@pytest.fixture
def apikey_settings():
    return KaterSettings(
        auth={"mode": "apikey", "api_keys": ["secret-key-123"]},
    )


class TestIsPublicPath:
    def test_health_is_public(self):
        assert should_proxy_to_api("/health") is True

    def test_authorize_is_public(self):
        assert should_proxy_to_api("/authorize") is True

    def test_token_is_public(self):
        assert should_proxy_to_api("/token") is True

    def test_register_is_public(self):
        assert should_proxy_to_api("/register") is True

    def test_revoke_is_public(self):
        assert should_proxy_to_api("/revoke") is True

    def test_well_known_is_public(self):
        assert should_proxy_to_api("/.well-known/openid-configuration") is True

    def test_well_known_jwks_is_public(self):
        assert should_proxy_to_api("/.well-known/jwks.json") is True

    def test_dashboard_root_is_public(self):
        assert should_proxy_to_api("/") is True

    def test_dashboard_path_is_public(self):
        assert should_proxy_to_api("/dashboard") is True

    def test_api_paths_are_public(self):
        assert should_proxy_to_api("/api/tools") is True
        assert should_proxy_to_api("/api/settings") is True

    def test_unknown_path_not_public(self):
        assert should_proxy_to_api("/unknown") is False

    def test_path_normalization(self):
        assert should_proxy_to_api("/health/") is True
        assert should_proxy_to_api("/health") is True


class TestAuthenticate:
    def test_public_path_always_allowed(self, no_auth_settings):
        ctx = AuthContext(
            settings=no_auth_settings,
            path="/health",
        )
        decision = authenticate(ctx)
        assert decision.allowed is True

    def test_public_api_prefix_always_allowed(self, no_auth_settings):
        ctx = AuthContext(
            settings=no_auth_settings,
            path="/.well-known/openid-configuration",
        )
        decision = authenticate(ctx)
        assert decision.allowed is True

    def test_none_mode_allows_everything(self, no_auth_settings):
        ctx = AuthContext(settings=no_auth_settings, path="/api/tools")
        decision = authenticate(ctx)
        assert decision.allowed is True

    def test_apikey_valid(self, apikey_settings):
        ctx = AuthContext(
            settings=apikey_settings,
            authorization_header="Bearer secret-key-123",
            path="/api/tools",
        )
        decision = authenticate(ctx)
        assert decision.allowed is True

    def test_apikey_invalid(self, apikey_settings):
        ctx = AuthContext(
            settings=apikey_settings,
            authorization_header="Bearer wrong-key",
            path="/api/tools",
        )
        decision = authenticate(ctx)
        assert decision.allowed is False
        assert decision.error is not None

    def test_apikey_missing(self, apikey_settings):
        ctx = AuthContext(
            settings=apikey_settings,
            path="/api/tools",
        )
        decision = authenticate(ctx)
        assert decision.allowed is False

    def test_apikey_via_query(self, apikey_settings):
        ctx = AuthContext(
            settings=apikey_settings,
            query_api_key="secret-key-123",
            path="/api/tools",
        )
        decision = authenticate(ctx)
        assert decision.allowed is True

    def test_public_path_bypasses_apikey_check(self, apikey_settings):
        """Even with apikey mode, public paths are always reachable."""
        ctx = AuthContext(
            settings=apikey_settings,
            path="/health",
        )
        decision = authenticate(ctx)
        assert decision.allowed is True

    def test_no_path_allows_when_mode_none(self, no_auth_settings):
        """WebSocket/MCP transports pass path=None; mode=none allows."""
        ctx = AuthContext(settings=no_auth_settings)
        decision = authenticate(ctx)
        assert decision.allowed is True


class TestAuthContext:
    def test_frozen(self):
        ctx = AuthContext(settings=KaterSettings())
        with pytest.raises(AttributeError):
            ctx.path = "/new"  # type: ignore[misc]
