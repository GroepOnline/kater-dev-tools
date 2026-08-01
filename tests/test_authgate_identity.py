"""Unit tests for the identity/capability primitives added to authgate.py:

``RequestIdentity``, ``capability_allowed``, ``identity_from_record``,
``_extract_bearer``, ``resolve_identity_from_headers``, and the
context-scoped ``get_request_identity``/``set_request_identity`` accessors.

``authenticate()``'s public-path / apikey-mode behavior is already covered by
test_authgate.py; the context-token binding behavior is covered end-to-end by
test_context_tokens.py. This file focuses on the smaller building blocks in
isolation, including edge cases those integration tests don't exercise.
"""

from __future__ import annotations

import pytest

from kater.authgate import (
    RequestIdentity,
    _extract_bearer,
    capability_allowed,
    get_request_identity,
    identity_from_record,
    resolve_identity_from_headers,
    set_request_identity,
)
from kater.control_plane import contexts
from kater.control_plane import tokens as context_tokens


class TestCapabilityAllowed:
    def test_none_allowlist_is_unrestricted(self):
        assert capability_allowed("anything.goes", None) is True

    def test_exact_match_is_allowed(self):
        assert capability_allowed("kater.profiles.list", frozenset({"kater.profiles.list"}))

    def test_no_match_is_denied(self):
        assert not capability_allowed("web.search", frozenset({"kater.profiles.list"}))

    def test_empty_allowlist_denies_everything(self):
        assert not capability_allowed("kater.profiles.list", frozenset())

    def test_wildcard_suffix_matches_prefix(self):
        allowed = frozenset({"kater_browser_*"})
        assert capability_allowed("kater_browser_providers", allowed)
        assert capability_allowed("kater_browser_sessions", allowed)
        assert not capability_allowed("kater_computer_status", allowed)

    def test_dotted_prefix_matches_subcapabilities(self):
        allowed = frozenset({"kater.automations"})
        assert capability_allowed("kater.automations.list", allowed)
        assert capability_allowed("kater.automations.run", allowed)
        # The entry itself without a trailing separator does not imply a
        # sibling capability that merely shares a string prefix.
        assert not capability_allowed("kater.automationsx", allowed)

    def test_blank_entries_are_ignored(self):
        allowed = frozenset({"", "kater.profiles.list"})
        assert capability_allowed("kater.profiles.list", allowed)
        assert not capability_allowed("kater.profiles.get", allowed)


@pytest.fixture
def ctx_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KATER_CONTEXT_TOKEN_SECRET", "test-context-secret")
    context_tokens.reset_token_secret_cache()
    contexts.reset_cache()
    yield tmp_path
    contexts.reset_cache()
    context_tokens.reset_token_secret_cache()


class TestIdentityFromRecord:
    def test_empty_allowed_capabilities_means_unrestricted(self, ctx_db):
        record = contexts.create_context(principal_id="agent-a")
        identity = identity_from_record(record)
        assert identity.allowed_capabilities is None
        assert identity.principal_id == "agent-a"
        assert identity.context_id == record.context_id

    def test_non_empty_allowed_capabilities_is_enforced(self, ctx_db):
        record = contexts.create_context(
            principal_id="agent-b",
            allowed_capabilities=["kater.profiles.list"],
            scopes=["github.read"],
        )
        identity = identity_from_record(record)
        assert identity.allowed_capabilities == frozenset({"kater.profiles.list"})
        assert identity.scopes == frozenset({"github.read"})


class TestExtractBearer:
    def test_none_header_returns_none(self):
        assert _extract_bearer(None) is None

    def test_empty_header_returns_none(self):
        assert _extract_bearer("") is None

    def test_scheme_only_returns_none(self):
        assert _extract_bearer("Bearer") is None

    def test_non_bearer_scheme_returns_none(self):
        assert _extract_bearer("Basic dXNlcjpwYXNz") is None

    def test_bearer_is_case_insensitive(self):
        assert _extract_bearer("bearer abc123") == "abc123"
        assert _extract_bearer("BEARER abc123") == "abc123"

    def test_extra_whitespace_is_tolerated(self):
        assert _extract_bearer("Bearer   abc123  ") == "abc123"

    def test_bearer_with_blank_token_returns_none(self):
        assert _extract_bearer("Bearer    ") is None


class TestRequestScopedIdentity:
    def test_default_identity_is_empty(self):
        assert get_request_identity() == RequestIdentity()

    def test_set_then_get_round_trips(self):
        identity = RequestIdentity(principal_id="p1", context_id="c1")
        set_request_identity(identity)
        try:
            assert get_request_identity() == identity
        finally:
            set_request_identity(None)

    def test_clearing_returns_default(self):
        set_request_identity(RequestIdentity(principal_id="p1"))
        set_request_identity(None)
        assert get_request_identity() == RequestIdentity()


class TestResolveIdentityFromHeaders:
    def test_no_headers_returns_anonymous(self, ctx_db):
        identity, error = resolve_identity_from_headers(None, None)
        assert identity == RequestIdentity()
        assert error is None

    def test_explicit_context_header_wins_over_bearer(self, ctx_db):
        record = contexts.create_context(
            principal_id="agent-explicit",
            allowed_capabilities=["kater.profiles.list"],
        )
        token = context_tokens.issue_token(record, ttl_seconds=120)
        identity, error = resolve_identity_from_headers(
            token, "Bearer some-unrelated-api-key"
        )
        assert error is None
        assert identity.principal_id == "agent-explicit"

    def test_explicit_invalid_context_header_errors(self, ctx_db):
        identity, error = resolve_identity_from_headers("not-a-real-token", None)
        assert identity == RequestIdentity()
        assert error is not None
        assert "context" in error.lower()

    def test_bearer_with_two_dots_is_never_treated_as_context_token(self, ctx_db):
        # A three-part value (e.g. a JWT-shaped API key) has two dots and must
        # not be mistaken for the single-dot context-token format.
        identity, error = resolve_identity_from_headers(None, "Bearer a.b.c")
        assert identity == RequestIdentity()
        assert error is None

    def test_bearer_with_no_dots_is_never_treated_as_context_token(self, ctx_db):
        identity, error = resolve_identity_from_headers(None, "Bearer plain-api-key")
        assert identity == RequestIdentity()
        assert error is None

    def test_bearer_shaped_like_a_token_but_invalid_falls_back_silently(self, ctx_db):
        # Exactly one dot (context-token shape) but not a real token: this is
        # the convenience fallback path, so an invalid value here does NOT
        # produce an error — it's treated as "no context", not "bad context".
        identity, error = resolve_identity_from_headers(None, "Bearer fake.token")
        assert identity == RequestIdentity()
        assert error is None

    def test_valid_bearer_context_token_is_used_when_no_explicit_header(self, ctx_db):
        record = contexts.create_context(
            principal_id="agent-bearer",
            allowed_capabilities=["web.search"],
        )
        token = context_tokens.issue_token(record, ttl_seconds=120)
        assert token.count(".") == 1
        identity, error = resolve_identity_from_headers(None, f"Bearer {token}")
        assert error is None
        assert identity.principal_id == "agent-bearer"
        assert identity.allowed_capabilities == frozenset({"web.search"})