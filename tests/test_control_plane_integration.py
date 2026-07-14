from kater.control_plane import (
    AccountState,
    ProviderAccount,
    QuotaWindow,
    clear_control_plane_state,
    list_route_candidates,
    query_routing_decisions,
    upsert_route_candidate,
)
from kater.proxy.base import MockBackend
from kater.proxy.manager import ProxyManager


class TrackingBackend(MockBackend):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calls = []

    def call_tool(self, tool_name, arguments):
        self.calls.append((tool_name, arguments))
        responses = getattr(self, "_responses", getattr(self, "responses", {}))
        if tool_name in responses:
            return responses[tool_name]
        return {
            "content": [
                {"type": "text", "text": f"mock result for {tool_name}"},
            ]
        }


class RaisingBackend(MockBackend):
    def call_tool(self, tool_name, arguments):
        raise RuntimeError("transport down")


def _candidate(
    account_id: str,
    backend: str,
    *,
    remaining: int,
    priority: int = 100,
) -> ProviderAccount:
    return ProviderAccount(
        account_id=account_id,
        provider="provider",
        backend=backend,
        tool_name="search",
        priority=priority,
        max_concurrent=2,
        scopes=frozenset({"web.read"}),
        quota_windows=(QuotaWindow("monthly", 100, 100 - remaining),),
    )


def test_persistent_pool_routes_live_mcp_alias_with_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    clear_control_plane_state()
    upsert_route_candidate(
        "web.search",
        _candidate("primary-account", "primary", remaining=90, priority=1),
    )
    upsert_route_candidate(
        "web.search",
        _candidate("secondary-account", "secondary", remaining=80, priority=2),
    )

    manager = ProxyManager()
    primary = RaisingBackend(
        tools=[
            {
                "name": "search",
                "inputSchema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                },
            }
        ]
    )
    secondary = TrackingBackend(
        tools=[
            {
                "name": "search",
                "description": "Search the web",
                "inputSchema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                },
            }
        ],
        responses={"search": {"answer": "ok"}},
    )
    manager.register_backend("primary", primary)
    manager.register_backend("secondary", secondary)

    tools = {tool["name"]: tool for tool in manager.list_tools()}
    assert "web.search" in tools
    assert "_kater_route" in tools["web.search"]["inputSchema"]["properties"]

    result = manager.call_tool(
        "web.search",
        {
            "query": "Utrecht",
            "_kater_route": {
                "context_id": "ctx-1",
                "required_scopes": ["web.read"],
                "estimated_units": 3,
            },
        },
    )

    assert result == {"answer": "ok"}
    assert secondary.calls == [("search", {"query": "Utrecht"})]
    decisions = list(reversed(query_routing_decisions(capability="web.search")))
    assert [row["outcome"] for row in decisions] == ["fallback", "success"]
    refreshed = {
        binding.account.account_id: binding.account
        for binding in list_route_candidates("web.search")
    }
    assert refreshed["primary-account"].state == AccountState.COOLDOWN
    assert refreshed["secondary-account"].quota_windows[0].used == 23


def test_context_affinity_wins_while_candidate_remains_eligible(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    clear_control_plane_state()
    upsert_route_candidate(
        "web.search",
        _candidate("primary-account", "primary", remaining=90, priority=1),
    )
    upsert_route_candidate(
        "web.search",
        _candidate("secondary-account", "secondary", remaining=80, priority=2),
    )
    manager = ProxyManager()
    primary = MockBackend(
        tools=[{"name": "search"}],
        responses={"search": {"selected": "primary"}},
    )
    secondary = MockBackend(
        tools=[{"name": "search"}],
        responses={"search": {"selected": "secondary"}},
    )
    manager.register_backend("primary", primary)
    manager.register_backend("secondary", secondary)

    route_meta = {"_kater_route": {"context_id": "sticky", "required_scopes": ["web.read"]}}
    assert manager.call_tool("web.search", route_meta) == {"selected": "primary"}

    upsert_route_candidate(
        "web.search",
        _candidate("primary-account", "primary", remaining=1, priority=100),
    )
    assert manager.call_tool("web.search", route_meta) == {"selected": "primary"}
    other_context = {
        "_kater_route": {"context_id": "fresh", "required_scopes": ["web.read"]}
    }
    assert manager.call_tool("web.search", other_context) == {"selected": "secondary"}


def test_tool_level_error_does_not_repeat_side_effect_on_fallback(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    clear_control_plane_state()
    upsert_route_candidate(
        "github.issue.create",
        ProviderAccount(
            account_id="primary-account",
            provider="github",
            backend="primary",
            tool_name="create_issue",
        ),
    )
    upsert_route_candidate(
        "github.issue.create",
        ProviderAccount(
            account_id="secondary-account",
            provider="github",
            backend="secondary",
            tool_name="create_issue",
            priority=200,
        ),
    )
    manager = ProxyManager()
    primary = TrackingBackend(
        tools=[{"name": "create_issue"}],
        responses={"create_issue": {"error": "validation failed"}},
    )
    secondary = TrackingBackend(
        tools=[{"name": "create_issue"}],
        responses={"create_issue": {"created": True}},
    )
    manager.register_backend("primary", primary)
    manager.register_backend("secondary", secondary)

    for _ in range(6):
        assert manager.call_tool("github.issue.create", {"title": "x"}) == {
            "error": "validation failed"
        }
    assert len(primary.calls) == 6
    assert secondary.calls == []


def test_schema_incompatible_candidate_is_not_used_for_fallback(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    clear_control_plane_state()
    upsert_route_candidate(
        "web.search",
        _candidate("primary-account", "primary", remaining=90, priority=1),
    )
    upsert_route_candidate(
        "web.search",
        _candidate("secondary-account", "secondary", remaining=80, priority=2),
    )
    manager = ProxyManager()
    primary = RaisingBackend(
        tools=[
            {
                "name": "search",
                "inputSchema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                },
            }
        ]
    )
    secondary = TrackingBackend(
        tools=[
            {
                "name": "search",
                "inputSchema": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                },
            }
        ],
        responses={"search": {"answer": "unsafe fallback"}},
    )
    manager.register_backend("primary", primary)
    manager.register_backend("secondary", secondary)

    result = manager.call_tool("web.search", {"query": "Utrecht"})

    assert result["error"].startswith("All routes failed")
    assert secondary.calls == []


def test_consuming_expired_quota_clears_stale_reset_boundary(tmp_path, monkeypatch) -> None:
    from datetime import UTC, datetime, timedelta

    monkeypatch.chdir(tmp_path)
    clear_control_plane_state()
    upsert_route_candidate(
        "web.search",
        ProviderAccount(
            account_id="reset-account",
            provider="provider",
            backend="primary",
            tool_name="search",
            scopes=frozenset({"web.read"}),
            quota_windows=(
                QuotaWindow(
                    "daily",
                    limit=10,
                    used=10,
                    resets_at=datetime.now(UTC) - timedelta(seconds=1),
                ),
            ),
        ),
    )
    manager = ProxyManager()
    manager.register_backend(
        "primary",
        MockBackend(tools=[{"name": "search"}], responses={"search": {"ok": True}}),
    )

    assert manager.call_tool(
        "web.search",
        {"_kater_route": {"required_scopes": ["web.read"], "estimated_units": 3}},
    ) == {"ok": True}

    refreshed = list_route_candidates("web.search")[0].account.quota_windows[0]
    assert refreshed.used == 3
    assert refreshed.resets_at is None
    assert refreshed.remaining_at(datetime.now(UTC)) == 7


def test_oversized_context_id_is_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    clear_control_plane_state()
    upsert_route_candidate(
        "web.search",
        _candidate("primary-account", "primary", remaining=90),
    )
    manager = ProxyManager()
    manager.register_backend(
        "primary",
        MockBackend(tools=[{"name": "search"}], responses={"search": {"ok": True}}),
    )
    result = manager.call_tool(
        "web.search",
        {
            "_kater_route": {
                "context_id": "x" * 200,
                "required_scopes": ["web.read"],
            }
        },
    )
    assert "error" in result
    assert "128" in result["error"]


def test_business_error_clears_half_open_probe(tmp_path, monkeypatch) -> None:
    """A tool-level error must release the half-open probe so later calls work."""
    monkeypatch.chdir(tmp_path)
    clear_control_plane_state()
    upsert_route_candidate(
        "web.search",
        ProviderAccount(
            account_id="solo",
            provider="provider",
            backend="solo",
            tool_name="search",
            max_concurrent=1,
            scopes=frozenset({"web.read"}),
            quota_windows=(QuotaWindow("monthly", 100, 0),),
        ),
    )
    manager = ProxyManager()
    # Force the breaker open, then into half-open with a short recovery.
    manager._failure_threshold = 1
    manager._recovery_timeout = 0.01
    backend = TrackingBackend(
        tools=[{"name": "search"}],
        responses={"search": {"error": "validation failed"}},
    )
    manager.register_backend("solo", backend)
    breaker = manager._breakers["solo"]
    for _ in range(2):
        breaker.record_failure()
    assert breaker.state == "open"
    import time

    time.sleep(0.02)
    # First call after recovery reserves half-open; business error must clear it.
    assert "error" in manager.call_tool(
        "web.search",
        {"_kater_route": {"required_scopes": ["web.read"]}},
    )
    assert breaker.state == "closed"
    assert breaker._probe_in_flight is False
    # Second call still allowed (probe was released).
    assert "error" in manager.call_tool(
        "web.search",
        {"_kater_route": {"required_scopes": ["web.read"]}},
    )


def test_operational_error_dict_path_still_fallbacks(tmp_path, monkeypatch) -> None:
    """BackendOperationalError from transport must fallback like raised RuntimeError."""
    from kater.proxy.base import BackendOperationalError

    class OpsFailBackend(MockBackend):
        def call_tool(self, tool_name, arguments):
            raise BackendOperationalError("timeout waiting for response")

    monkeypatch.chdir(tmp_path)
    clear_control_plane_state()
    upsert_route_candidate(
        "web.search",
        _candidate("primary-account", "primary", remaining=90, priority=1),
    )
    upsert_route_candidate(
        "web.search",
        _candidate("secondary-account", "secondary", remaining=80, priority=2),
    )
    manager = ProxyManager()
    manager.register_backend(
        "primary",
        OpsFailBackend(
            tools=[
                {
                    "name": "search",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                    },
                }
            ]
        ),
    )
    secondary = TrackingBackend(
        tools=[
            {
                "name": "search",
                "inputSchema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                },
            }
        ],
        responses={"search": {"answer": "ok"}},
    )
    manager.register_backend("secondary", secondary)
    assert manager.call_tool(
        "web.search",
        {"query": "x", "_kater_route": {"required_scopes": ["web.read"]}},
    ) == {"answer": "ok"}
    assert secondary.calls == [("search", {"query": "x"})]
