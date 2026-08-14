"""Catalog Connect: connections, masking, and deny-default OAuth client checks.

No live provider calls. Values are placeholders / env names only.
"""

from __future__ import annotations

from kater.connect import (
    add_connection,
    declared_credential_keys,
    launch_instances,
    oauth_client_configured,
    public_oauth,
    remove_connection,
    resolve_oauth_client,
    source_is_configured,
)
from kater.profiles import OAuthConnectConfig, RiskLevel, ToolSource, Transport
from kater.settings import KaterSettings, ServerConnection, ServerOverride


def _oauth_source() -> ToolSource:
    return ToolSource(
        name="demo-oauth",
        description="test source",
        transport=Transport.HTTP,
        risk=RiskLevel.HIGH,
        profiles={"ops"},
        env=["DEMO_ACCESS_TOKEN"],
        oauth=OAuthConnectConfig(
            provider="slack",
            authorize_url="https://example.test/oauth/authorize",
            token_url="https://example.test/oauth/token",
            client_id_env="DEMO_CLIENT_ID",
            client_secret_env="DEMO_CLIENT_SECRET",
            token_env="DEMO_ACCESS_TOKEN",
            refresh_env="DEMO_REFRESH_TOKEN",
            scopes=["users:read"],
        ),
    )


def test_declared_credential_keys_include_oauth_env_names() -> None:
    keys = declared_credential_keys(_oauth_source())
    assert keys == {
        "DEMO_ACCESS_TOKEN",
        "DEMO_CLIENT_ID",
        "DEMO_CLIENT_SECRET",
        "DEMO_REFRESH_TOKEN",
    }


def test_oauth_client_deny_default_without_client_id(monkeypatch) -> None:
    monkeypatch.delenv("DEMO_CLIENT_ID", raising=False)
    source = _oauth_source()
    settings = KaterSettings()
    assert oauth_client_configured(source, settings) is False
    assert resolve_oauth_client(source, settings) == ("", "")


def test_source_is_configured_from_connection_not_process_env() -> None:
    source = _oauth_source()
    settings = KaterSettings(
        server_overrides={
            "demo-oauth": ServerOverride(
                connections=[
                    ServerConnection(
                        id="acct1",
                        label="workspace-a",
                        env={"DEMO_ACCESS_TOKEN": "kater-test-access-token"},
                    )
                ]
            )
        }
    )
    assert source_is_configured(source, settings) is True
    public = public_oauth(source, settings)
    assert public is not None
    assert public["token_env"] == "DEMO_ACCESS_TOKEN"
    assert public["connections"] == [{"id": "acct1", "label": "workspace-a", "created_at": 0.0}]
    dumped = str(public)
    assert "kater-test-access-token" not in dumped


def test_add_and_remove_connection_roundtrip() -> None:
    settings = KaterSettings()
    conn = add_connection(
        settings,
        "demo-oauth",
        {"DEMO_ACCESS_TOKEN": "kater-test-access-token"},
        label="manual",
    )
    assert conn.id
    assert settings.server_overrides["demo-oauth"].connections[0].label == "manual"
    assert remove_connection(settings, "demo-oauth", conn.id) is True
    assert settings.server_overrides["demo-oauth"].connections == []
    assert remove_connection(settings, "demo-oauth", "missing") is False


def test_launch_instances_uses_per_account_overlay() -> None:
    source = _oauth_source()
    settings = KaterSettings(
        server_overrides={
            "demo-oauth": ServerOverride(
                env={"DEMO_CLIENT_ID": "kater-test-client-id"},
                connections=[
                    ServerConnection(
                        id="one",
                        env={"DEMO_ACCESS_TOKEN": "kater-test-access-one"},
                    ),
                    ServerConnection(
                        id="two",
                        env={"DEMO_ACCESS_TOKEN": "kater-test-access-two"},
                    ),
                ],
            )
        }
    )
    instances = launch_instances(source, settings)
    assert [name for name, _env in instances] == ["demo-oauth", "demo-oauth__two"]
    assert instances[0][1]["DEMO_ACCESS_TOKEN"] == "kater-test-access-one"
    assert instances[1][1]["DEMO_ACCESS_TOKEN"] == "kater-test-access-two"
    assert instances[0][1]["DEMO_CLIENT_ID"] == "kater-test-client-id"


def test_settings_mask_connection_env_values() -> None:
    settings = KaterSettings(
        server_overrides={
            "demo-oauth": ServerOverride(
                env={"DEMO_CLIENT_ID": "kater-test-client-id"},
                connections=[
                    ServerConnection(
                        id="acct1",
                        env={"DEMO_ACCESS_TOKEN": "kater-test-access-token"},
                    )
                ],
            )
        }
    )
    safe = settings.to_safe_dict()
    override = safe["server_overrides"]["demo-oauth"]
    assert override["env"]["DEMO_CLIENT_ID"] == "***"
    assert override["connections"][0]["env"]["DEMO_ACCESS_TOKEN"] == "***"
    assert "kater-test-access-token" not in str(safe)
    assert "kater-test-client-id" not in str(safe)


def test_slack_catalog_source_declares_connect_env_names() -> None:
    from kater.profiles import get_source

    slack = get_source("slack")
    assert slack is not None
    assert slack.oauth is not None
    assert slack.oauth.client_id_env == "SLACK_MCP_CLIENT_ID"
    assert slack.oauth.token_env == "SLACK_ACCESS_TOKEN"
    assert slack.transport.value == "http"
    assert "SLACK_BOT_TOKEN" not in slack.env


def test_secret_sink_local_requires_explicit_opt_in(monkeypatch) -> None:
    from kater.connect_policy import connect_secret_decision
    from kater.settings import invalidate_settings_cache

    monkeypatch.delenv("KATER_PUBLIC", raising=False)
    monkeypatch.delenv("KATER_CONNECT_ALLOW_LOCAL_SETTINGS", raising=False)
    monkeypatch.delenv("KATER_CONNECT_SECRET_SINK", raising=False)
    invalidate_settings_cache()
    denied = connect_secret_decision(KaterSettings())
    assert denied.allowed is False
    assert denied.reason == "local_settings_opt_in_required"
    assert denied.persist_local_settings is False

    monkeypatch.setenv("KATER_CONNECT_ALLOW_LOCAL_SETTINGS", "1")
    allowed = connect_secret_decision(KaterSettings())
    assert allowed.allowed is True
    assert allowed.sink == "local-settings"
    assert allowed.persist_local_settings is True


def test_secret_sink_public_deny_default_ignores_local_opt_in(monkeypatch) -> None:
    from kater.connect_policy import connect_secret_decision
    from kater.settings import invalidate_settings_cache

    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_CONNECT_ALLOW_LOCAL_SETTINGS", "1")
    monkeypatch.delenv("KATER_CONNECT_SECRET_SINK", raising=False)
    invalidate_settings_cache()
    denied = connect_secret_decision(KaterSettings())
    assert denied.allowed is False
    assert denied.reason == "secret_sink_required"
    assert denied.persist_local_settings is False


def test_secret_sink_chefvault_is_reference_only(monkeypatch) -> None:
    from kater.connect_policy import connect_secret_decision
    from kater.settings import invalidate_settings_cache

    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_CONNECT_SECRET_SINK", "chefvault")
    invalidate_settings_cache()
    denied = connect_secret_decision(KaterSettings())
    assert denied.allowed is False
    assert denied.reason == "chefvault_persist_unavailable"
    assert "access_token" not in denied.as_error()["message"]


def test_public_origin_requires_https_canonical_url(monkeypatch) -> None:
    from kater.connect_policy import (
        ConnectOriginError,
        resolve_connect_base_url,
        validate_public_https_base,
    )
    from kater.settings import invalidate_settings_cache

    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.delenv("KATER_CONNECT_PUBLIC_BASE_URL", raising=False)
    invalidate_settings_cache()
    settings = KaterSettings()
    try:
        resolve_connect_base_url("https://evil.example", settings)
        raise AssertionError("missing public base must fail closed")
    except ConnectOriginError as exc:
        assert exc.reason == "public_base_url_required"

    monkeypatch.setenv("KATER_CONNECT_PUBLIC_BASE_URL", "http://kater.example.test")
    try:
        resolve_connect_base_url("https://ignored.example", settings)
        raise AssertionError("http public base must fail closed")
    except ConnectOriginError as exc:
        assert exc.reason == "public_base_url_must_be_https"

    for bad in (
        "javascript:alert(1)",
        "https://user:pass@kater.example.test",
        "https://kater.example.test/callback",
        "https://kater.example.test?next=https://evil.example",
    ):
        try:
            validate_public_https_base(bad)
            raise AssertionError(f"accepted hostile base: {bad}")
        except ConnectOriginError:
            pass

    monkeypatch.setenv("KATER_CONNECT_PUBLIC_BASE_URL", "https://kater.example.test")
    assert (
        resolve_connect_base_url("http://evil.example", settings) == "https://kater.example.test"
    )


def test_dev_origin_rejects_hostile_host(monkeypatch) -> None:
    from kater.connect_policy import ConnectOriginError, resolve_connect_base_url
    from kater.settings import invalidate_settings_cache

    monkeypatch.delenv("KATER_PUBLIC", raising=False)
    monkeypatch.delenv("KATER_CONNECT_PUBLIC_BASE_URL", raising=False)
    invalidate_settings_cache()
    settings = KaterSettings()
    assert resolve_connect_base_url("http://127.0.0.1:9091", settings) == "http://127.0.0.1:9091"
    try:
        resolve_connect_base_url("http://evil.example", settings)
        raise AssertionError("hostile host must be rejected in local mode")
    except ConnectOriginError as exc:
        assert exc.reason == "dev_base_url_must_be_loopback"
    recovered = resolve_connect_base_url(
        "http://evil.example",
        settings,
        pending_redirect="http://127.0.0.1:9091/api/mcp/oauth/callback",
    )
    assert recovered == "http://127.0.0.1:9091"
