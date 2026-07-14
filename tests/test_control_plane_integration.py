from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from kater.control_plane import (
    AccountState,
    ProviderAccount,
    QuotaWindow,
    clear_control_plane_state,
    list_route_candidates,
    prune_control_plane_state,
    query_routing_decisions,
    set_route_affinity,
    upsert_route_candidate,
)
from kater.control_plane import store as control_store
from kater.proxy.base import BackendOperationalError, MockBackend
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


class PreSendFailBackend(MockBackend):
    """Pre-dispatch failure — safe to try another account."""

    def call_tool(self, tool_name, arguments):
        raise BackendOperationalError("backend not started", fallback_safe=True)


class PostSendFailBackend(MockBackend):
    """Post-send / ambiguous failure — must NOT fallback."""

    def call_tool(self, tool_name, arguments):
        raise BackendOperationalError("timeout waiting for response", fallback_safe=False)


class RaisingBackend(MockBackend):
    def call_tool(self, tool_name, arguments):
        raise RuntimeError("transport down")


def _candidate(
    account_id: str,
    backend: str,
    *,
    remaining: int,
    priority: int = 100,
    max_concurrent: int = 2,
) -> ProviderAccount:
    return ProviderAccount(
        account_id=account_id,
        provider="provider",
        backend=backend,
        tool_name="search",
        priority=priority,
        max_concurrent=max_concurrent,
        scopes=frozenset({"web.read"}),
        quota_windows=(QuotaWindow("monthly", 100, 100 - remaining),),
    )


def _search_schema() -> dict:
    return {
        "type": "object",
        "properties": {"query": {"type": "string"}},
    }


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
    primary = PreSendFailBackend(tools=[{"name": "search", "inputSchema": _search_schema()}])
    secondary = TrackingBackend(
        tools=[
            {
                "name": "search",
                "description": "Search the web",
                "inputSchema": _search_schema(),
            }
        ],
        responses={"search": {"answer": "ok"}},
    )
    manager.register_backend("primary", primary)
    manager.register_backend("secondary", secondary)

    tools = {tool["name"]: tool for tool in manager.list_tools()}
    assert "web.search" in tools
    route_meta = tools["web.search"]["inputSchema"]["properties"]["_kater_route"]
    assert route_meta["additionalProperties"] is False
    assert route_meta["properties"]["estimated_units"]["maximum"] == 1_000_000
    assert route_meta["properties"]["required_scopes"]["maxItems"] == 32

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


def test_generic_exception_does_not_fallback(tmp_path, monkeypatch) -> None:
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
    secondary = TrackingBackend(
        tools=[{"name": "search", "inputSchema": _search_schema()}],
        responses={"search": {"answer": "should-not-run"}},
    )
    manager.register_backend(
        "primary",
        RaisingBackend(tools=[{"name": "search", "inputSchema": _search_schema()}]),
    )
    manager.register_backend("secondary", secondary)

    result = manager.call_tool(
        "web.search",
        {"query": "x", "_kater_route": {"required_scopes": ["web.read"]}},
    )
    assert result == {"error": "Backend error: RuntimeError"}
    assert secondary.calls == []
    decisions = query_routing_decisions(capability="web.search")
    assert decisions[0]["outcome"] == "failed"


def test_post_send_operational_error_does_not_fallback(tmp_path, monkeypatch) -> None:
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
    secondary = TrackingBackend(
        tools=[{"name": "search", "inputSchema": _search_schema()}],
        responses={"search": {"answer": "should-not-run"}},
    )
    manager.register_backend(
        "primary",
        PostSendFailBackend(tools=[{"name": "search", "inputSchema": _search_schema()}]),
    )
    manager.register_backend("secondary", secondary)

    result = manager.call_tool(
        "web.search",
        {"query": "x", "_kater_route": {"required_scopes": ["web.read"]}},
    )
    assert result == {"error": "Backend error: BackendOperationalError"}
    assert secondary.calls == []


def test_presend_operational_error_still_fallbacks(tmp_path, monkeypatch) -> None:
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
        PreSendFailBackend(tools=[{"name": "search", "inputSchema": _search_schema()}]),
    )
    secondary = TrackingBackend(
        tools=[{"name": "search", "inputSchema": _search_schema()}],
        responses={"search": {"answer": "ok"}},
    )
    manager.register_backend("secondary", secondary)
    assert manager.call_tool(
        "web.search",
        {"query": "x", "_kater_route": {"required_scopes": ["web.read"]}},
    ) == {"answer": "ok"}
    assert secondary.calls == [("search", {"query": "x"})]


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
    other_context = {"_kater_route": {"context_id": "fresh", "required_scopes": ["web.read"]}}
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
    primary = PreSendFailBackend(
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


def test_strict_route_meta_rejects_unknown_and_bool_units(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    clear_control_plane_state()
    upsert_route_candidate(
        "web.search",
        _candidate("primary-account", "primary", remaining=90),
    )
    manager = ProxyManager()
    backend = TrackingBackend(
        tools=[{"name": "search"}],
        responses={"search": {"ok": True}},
    )
    manager.register_backend("primary", backend)

    unknown = manager.call_tool(
        "web.search",
        {"_kater_route": {"required_scopes": ["web.read"], "extra": True}},
    )
    assert "unknown fields" in unknown["error"]
    assert backend.calls == []

    bool_units = manager.call_tool(
        "web.search",
        {"_kater_route": {"required_scopes": ["web.read"], "estimated_units": True}},
    )
    assert "estimated_units" in bool_units["error"]
    assert backend.calls == []

    bad_meta = manager.call_tool("web.search", {"_kater_route": "nope"})
    assert "_kater_route must be an object" in bad_meta["error"]


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
    assert "error" in manager.call_tool(
        "web.search",
        {"_kater_route": {"required_scopes": ["web.read"]}},
    )
    assert breaker.state == "closed"
    assert breaker._probe_in_flight is False
    assert "error" in manager.call_tool(
        "web.search",
        {"_kater_route": {"required_scopes": ["web.read"]}},
    )


def test_half_open_recovers_when_healthy_latched_false(tmp_path, monkeypatch) -> None:
    """Breaker-authorized probe must run even if a prior call set healthy=False."""
    monkeypatch.chdir(tmp_path)
    clear_control_plane_state()
    upsert_route_candidate(
        "web.search",
        _candidate("solo", "solo", remaining=90, priority=1, max_concurrent=1),
    )
    manager = ProxyManager()
    manager._failure_threshold = 1
    manager._recovery_timeout = 0.01
    backend = TrackingBackend(
        tools=[{"name": "search"}],
        responses={"search": {"ok": True}},
    )
    manager.register_backend("solo", backend)
    backend._status.healthy = False
    assert backend.is_healthy() is False
    assert backend._running is True

    breaker = manager._breakers["solo"]
    for _ in range(2):
        breaker.record_failure()
    import time

    time.sleep(0.02)
    assert manager.call_tool(
        "web.search",
        {"_kater_route": {"required_scopes": ["web.read"]}},
    ) == {"ok": True}
    assert backend.is_healthy() is True
    assert breaker.state == "closed"


def test_max_concurrent_check_and_reserve_is_atomic(tmp_path, monkeypatch) -> None:
    import threading

    monkeypatch.chdir(tmp_path)
    clear_control_plane_state()
    upsert_route_candidate(
        "web.search",
        _candidate("solo", "solo", remaining=90, max_concurrent=1),
    )
    manager = ProxyManager()
    hold = threading.Event()
    entered = threading.Event()
    started = []

    class BlockingBackend(MockBackend):
        def call_tool(self, tool_name, arguments):
            started.append(1)
            entered.set()
            assert hold.wait(timeout=2.0)
            return {"ok": True}

    manager.register_backend(
        "solo",
        BlockingBackend(tools=[{"name": "search"}]),
    )

    def _call():
        return manager.call_tool(
            "web.search",
            {"_kater_route": {"required_scopes": ["web.read"]}},
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(_call) for _ in range(4)]
        assert entered.wait(timeout=2.0)
        # While one call holds the slot, the other three must be rejected.
        # Release only after all futures settle would deadlock; poll briefly.
        import time

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            done = sum(1 for f in futures if f.done())
            if done >= 3:
                break
            time.sleep(0.01)
        hold.set()
        results = [f.result(timeout=2.0) for f in futures]

    successes = [r for r in results if r.get("ok")]
    rejected = [r for r in results if "max_concurrent" in str(r) or "No eligible route" in str(r)]
    assert len(started) == 1
    assert len(successes) == 1
    assert len(rejected) == 3


def test_prune_control_plane_state_expires_affinity_and_caps_rows(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    clear_control_plane_state()
    upsert_route_candidate(
        "web.search",
        _candidate("primary-account", "primary", remaining=90),
    )
    set_route_affinity("web.search", "old-ctx", "primary-account")
    with control_store._lock, control_store._connect() as db:
        db.execute(
            "UPDATE control_route_affinity SET updated_at = ?",
            (0.0,),
        )
        for i in range(5):
            db.execute(
                """
                INSERT INTO control_routing_decisions(
                    timestamp, capability, context_id, account_id, provider, backend,
                    tool_name, estimated_units, score, reasons, outcome, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    float(i),
                    "web.search",
                    f"ctx-{i}",
                    "primary-account",
                    "provider",
                    "primary",
                    "search",
                    1,
                    1.0,
                    "[]",
                    "success",
                    None,
                ),
            )

    monkeypatch.setattr(control_store, "MAX_DECISION_ROWS", 2)
    monkeypatch.setattr(control_store, "MAX_AFFINITY_ROWS", 1)
    deleted = prune_control_plane_state()
    assert deleted["affinity"] >= 1
    assert deleted["decisions"] >= 3
    overview_affinity = 0
    with control_store._lock, control_store._connect() as db:
        overview_affinity = int(
            db.execute("SELECT COUNT(*) AS c FROM control_route_affinity").fetchone()["c"]
        )
        decisions = int(
            db.execute("SELECT COUNT(*) AS c FROM control_routing_decisions").fetchone()["c"]
        )
    assert overview_affinity <= 1
    assert decisions <= 2
