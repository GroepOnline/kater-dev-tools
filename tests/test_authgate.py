"""Tests for authgate.py — the single authentication gate for all transports.

Covers: authenticate(), should_proxy_to_api(), _is_public_path(), and the
AuthContext/AuthDecision dataclasses.

Scoped-context-token integration (identity_from_record, resolve_request_identity
against a live ContextRecord, and REST-level allowlist enforcement) lives in
tests/test_context_tokens.py; this file sticks to the pure, DB-free unit
surface of authgate.py itself.
"""

from __future__ import annotations

import pytest

from kater.authgate import (
    AuthContext,
    RequestIdentity,
    authenticate,
    capability_allowed,
    get_request_identity,
    resolve_identity_from_headers,
    resolve_request_identity,
    set_request_identity,
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

    def test_context_header_defaults_to_none(self):
        ctx = AuthContext(settings=KaterSettings())
        assert ctx.context_header is None


class TestRequestIdentity:
    def test_defaults_are_unrestricted(self):
        identity = RequestIdentity()
        assert identity.principal_id is None
        assert identity.context_id is None
        assert identity.scopes == frozenset()
        assert identity.allowed_capabilities is None

    def test_frozen(self):
        identity = RequestIdentity(principal_id="agent-1")
        with pytest.raises(AttributeError):
            identity.principal_id = "agent-2"  # type: ignore[misc]

    def test_default_scopes_do_not_share_state(self):
        # frozenset() as a dataclass default_factory must not be aliased
        # between instances.
        a = RequestIdentity()
        b = RequestIdentity(scopes=frozenset({"x"}))
        assert a.scopes == frozenset()
        assert b.scopes == frozenset({"x"})


class TestCapabilityAllowed:
    def test_none_allowlist_is_unrestricted(self):
        assert capability_allowed("anything.at.all", None) is True

    def test_empty_allowlist_denies_everything(self):
        assert capability_allowed("web.search", frozenset()) is False

    def test_exact_match_allowed(self):
        assert capability_allowed("web.search", frozenset({"web.search"})) is True

    def test_non_member_denied(self):
        assert capability_allowed("web.search", frozenset({"kater.profiles.list"})) is False

    def test_dotted_prefix_match(self):
        # "kater.profiles" allows "kater.profiles.list" via the implicit
        # dot-boundary rule, but not an unrelated sibling capability.
        allowed = frozenset({"kater.profiles"})
        assert capability_allowed("kater.profiles.list", allowed) is True
        assert capability_allowed("kater.other.list", allowed) is False

    def test_wildcard_suffix_match(self):
        allowed = frozenset({"kater_browser_*"})
        assert capability_allowed("kater_browser_open", allowed) is True
        assert capability_allowed("kater_computer_status", allowed) is False

    def test_dotted_prefix_does_not_match_without_boundary(self):
        # "web" must not match "webhooks.create" — only a real "." boundary
        # (or exact match / explicit "*" wildcard) counts.
        allowed = frozenset({"web"})
        assert capability_allowed("webhooks.create", allowed) is False

    def test_blank_entries_in_allowlist_are_ignored(self):
        allowed = frozenset({"", "web.search"})
        assert capability_allowed("web.search", allowed) is True
        assert capability_allowed("unrelated", allowed) is False


class TestResolveIdentityFromHeaders:
    def test_no_headers_returns_open_identity(self):
        identity, error = resolve_identity_from_headers(None, None)
        assert identity == RequestIdentity()
        assert error is None

    def test_invalid_explicit_context_header_errors(self):
        identity, error = resolve_identity_from_headers("not-a-real-token", None)
        assert identity == RequestIdentity()
        assert error == "Invalid context token."

    def test_bearer_without_two_dots_is_ignored_as_context_token(self):
        # A plain API key (no dots) sent as a Bearer credential must not be
        # mistaken for (or rejected as) a scoped context token.
        identity, error = resolve_identity_from_headers(None, "Bearer plain-api-key-123")
        assert identity == RequestIdentity()
        assert error is None

    def test_bearer_with_three_part_jwt_is_ignored_as_context_token(self):
        # A JWT-shaped bearer (two dots) is not a context token either;
        # only the "payload.sig" (one dot) shape is attempted.
        identity, error = resolve_identity_from_headers(None, "Bearer a.b.c")
        assert identity == RequestIdentity()
        assert error is None

    def test_malformed_authorization_header_is_ignored(self):
        identity, error = resolve_identity_from_headers(None, "not-a-bearer-header")
        assert identity == RequestIdentity()
        assert error is None

    def test_context_header_takes_precedence_over_authorization(self):
        # An invalid explicit X-Kater-Context header must still error even
        # when a syntactically bearer-token-shaped Authorization header is
        # also present.
        identity, error = resolve_identity_from_headers("bad.token", "Bearer ignored")
        assert identity == RequestIdentity()
        assert error == "Invalid context token."


class TestRequestIdentityContextVar:
    def test_get_defaults_to_open_identity(self):
        set_request_identity(None)
        assert get_request_identity() == RequestIdentity()

    def test_set_and_get_round_trip(self):
        identity = RequestIdentity(principal_id="agent-x", context_id="rctx_x")
        set_request_identity(identity)
        try:
            assert get_request_identity() == identity
        finally:
            set_request_identity(None)

    def test_authenticate_binds_open_identity_when_no_context_header(self, no_auth_settings):
        set_request_identity(RequestIdentity(principal_id="stale"))
        try:
            decision = authenticate(AuthContext(settings=no_auth_settings, path="/api/tools"))
            assert decision.allowed is True
            assert get_request_identity() == RequestIdentity()
        finally:
            set_request_identity(None)


class TestResolveRequestIdentity:
    class _FakeRequest:
        def __init__(self, headers: dict[str, str]) -> None:
            self._headers = headers

        def header(self, name: str) -> str | None:
            return self._headers.get(name.lower())

    def test_resolves_via_header_method(self):
        req = self._FakeRequest({})
        assert resolve_request_identity(req) == RequestIdentity()

    def test_object_without_header_method_yields_open_identity(self):
        class _NoHeader:
            pass

        assert resolve_request_identity(_NoHeader()) == RequestIdentity()


class TestAuthenticateContextHeader:
    def test_invalid_context_header_denies_public_path(self, no_auth_settings):
        ctx = AuthContext(
            settings=no_auth_settings,
            path="/health",
            context_header="garbage",
        )
        decision = authenticate(ctx)
        assert decision.allowed is False
        assert decision.error == "Invalid context token."

    def test_invalid_context_header_denies_non_public_path_even_with_mode_none(
        self, no_auth_settings
    ):
        # mode=none normally allows everything; an explicit-but-invalid
        # context token must still fail closed.
        ctx = AuthContext(
            settings=no_auth_settings,
            path="/api/tools",
            context_header="garbage",
        )
        decision = authenticate(ctx)
        assert decision.allowed is False
        assert decision.error == "Invalid context token."

    def test_apikey_invalid_credential_rejected_before_context_header_checked(
        self, apikey_settings
    ):
        ctx = AuthContext(
            settings=apikey_settings,
            authorization_header="Bearer wrong-key",
            path="/api/tools",
            context_header="garbage",
        )
        decision = authenticate(ctx)
        assert decision.allowed is False
        # The credential failure is reported, not the (unreached) context error.
        assert decision.error != "Invalid context token."

    def test_no_context_header_binds_open_identity_on_public_path(self, no_auth_settings):
        decision = authenticate(AuthContext(settings=no_auth_settings, path="/health"))
        assert decision.allowed is True
        assert decision.identity == RequestIdentity()
