"""Coverage for the automations store, engine, builtins, and REST routes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kater import migrations
from kater.automations import (
    DEFAULT_AUTOMATIONS,
    Automation,
    AutomationEngine,
    AutomationRunResult,
    AutomationStore,
    get_engine,
    reset_engine,
)
from kater.automations import store as automations_store
from kater.automations.builtins import run_kind
from kater.automations.models import new_automation_id
from tests._rest import call


@pytest.fixture(autouse=True)
def _clean_automations(tmp_path, monkeypatch):
    # Isolate the automations store: each test gets its own migrated .kater/kater.db
    # under tmp_path instead of writing to the repository checkout.
    monkeypatch.chdir(tmp_path)
    automations_store.reset_cache()
    migrations.ensure_migrated(tmp_path / ".kater" / "kater.db")
    reset_engine()
    yield
    reset_engine()
    automations_store.reset_cache()


def test_store_crud_round_trip():
    auto = Automation(
        id=new_automation_id(),
        name="Watch",
        kind="doctor_watch",
        enabled=True,
        schedule_seconds=60,
        config={"profile": "core"},
        created_at=1000.0,
        updated_at=1000.0,
    )
    saved = automations_store.upsert(auto)
    assert saved.id == auto.id
    assert automations_store.get_automation(auto.id) == saved
    assert automations_store.count() == 1

    updated = automations_store.set_enabled(auto.id, False)
    assert updated is not None
    assert updated.enabled is False

    ran = automations_store.record_run(
        auto.id, ran_at=2000.0, status="ok", error=None
    )
    assert ran is not None
    assert ran.last_run_at == 2000.0
    assert ran.last_status == "ok"

    assert automations_store.delete(auto.id) is True
    assert automations_store.get_automation(auto.id) is None
    assert automations_store.delete(auto.id) is False


def test_ensure_defaults_seeds_four_rows():
    engine = get_engine()
    seeded = engine.ensure_defaults()
    assert len(seeded) == len(DEFAULT_AUTOMATIONS)
    kinds = {item.kind for item in seeded}
    assert kinds == {
        "doctor_watch",
        "browser_reap",
        "telemetry_prune",
        "credential_nudge",
    }
    # Second call is idempotent and does not duplicate.
    again = engine.ensure_defaults()
    assert len(again) == len(DEFAULT_AUTOMATIONS)
    assert automations_store.count() == len(DEFAULT_AUTOMATIONS)


def test_ensure_defaults_does_not_resurrect_deleted_builtins():
    engine = get_engine()
    seeded = engine.ensure_defaults()
    assert len(seeded) == len(DEFAULT_AUTOMATIONS)

    for item in seeded:
        assert automations_store.delete(item.id) is True
    assert automations_store.count() == 0

    # A fresh engine (as after a restart) must respect the deletions instead of
    # re-seeding just because the table happens to be empty.
    reset_engine()
    assert get_engine().ensure_defaults() == []
    assert automations_store.count() == 0


def test_tick_respects_schedule():
    clock = {"now": 1000.0}

    def _clock() -> float:
        return clock["now"]

    engine = AutomationEngine(clock=_clock)
    engine.upsert(
        id="auto_test_reap",
        name="Reap",
        kind="browser_reap",
        schedule_seconds=120,
        config={},
    )

    with patch(
        "kater.automations.builtins.get_manager"
    ) as manager_factory:
        manager = MagicMock()
        manager.reap_expired.return_value = 2
        manager_factory.return_value = manager

        first = engine.tick()
        assert first == 1
        assert manager.reap_expired.call_count == 1

        # Still inside the schedule window — no second run.
        clock["now"] = 1050.0
        assert engine.tick() == 0
        assert manager.reap_expired.call_count == 1

        # Past schedule — runs again.
        clock["now"] = 1125.0
        assert engine.tick() == 1
        assert manager.reap_expired.call_count == 2

    loaded = engine.get("auto_test_reap")
    assert loaded is not None
    assert loaded.last_status == "ok"
    assert loaded.last_run_at == 1125.0


def test_tick_skips_disabled_and_manual_only():
    clock = {"now": 5000.0}
    engine = AutomationEngine(clock=lambda: clock["now"])
    engine.upsert(
        id="auto_disabled",
        name="Disabled",
        kind="browser_reap",
        enabled=False,
        schedule_seconds=10,
    )
    engine.upsert(
        id="auto_manual",
        name="Manual",
        kind="browser_reap",
        enabled=True,
        schedule_seconds=0,
    )
    with patch(
        "kater.automations.builtins.get_manager"
    ) as manager_factory:
        manager = MagicMock()
        manager.reap_expired.return_value = 0
        manager_factory.return_value = manager
        assert engine.tick() == 0
        manager.reap_expired.assert_not_called()


def test_run_now_records_errors():
    engine = AutomationEngine(clock=lambda: 42.0)
    engine.upsert(
        id="auto_bad",
        name="Bad",
        kind="doctor_watch",
        schedule_seconds=60,
        config={"profile": "core"},
    )
    with patch(
        "kater.automations.builtins.run_doctor",
        side_effect=RuntimeError("boom"),
    ):
        result = engine.run_now("auto_bad")
    assert result.status == "error"
    assert result.error == "boom"
    loaded = engine.get("auto_bad")
    assert loaded is not None
    assert loaded.last_status == "error"
    assert loaded.last_error == "boom"


def test_run_now_refuses_disabled_unless_forced():
    engine = AutomationEngine(clock=lambda: 42.0)
    engine.upsert(
        id="auto_off",
        name="Off",
        kind="browser_reap",
        enabled=False,
        schedule_seconds=60,
    )
    with pytest.raises(ValueError, match="disabled"):
        engine.run_now("auto_off")

    with patch("kater.automations.builtins.get_manager") as manager_factory:
        manager = MagicMock()
        manager.reap_expired.return_value = 0
        manager_factory.return_value = manager
        forced = engine.run_now("auto_off", force=True)
    assert forced.status == "ok"
    manager.reap_expired.assert_called_once()


def test_builtins_do_not_crash_with_mocks():
    with patch("kater.automations.builtins.run_doctor") as doctor:
        report = MagicMock()
        report.findings = []
        doctor.return_value = report
        out = run_kind("doctor_watch", {"profile": "core"})
        assert out["findings"] == 0
        doctor.assert_called_once()

    with patch("kater.automations.builtins.get_manager") as manager_factory:
        manager = MagicMock()
        manager.reap_expired.return_value = 1
        manager_factory.return_value = manager
        assert run_kind("browser_reap", {})["closed"] == 1

    with patch("kater.automations.builtins.get_proxy") as proxy_factory:
        proxy = MagicMock(spec=["started", "heal"])
        proxy.started = False
        proxy_factory.return_value = proxy
        assert run_kind("proxy_heal", {})["skipped"] == "proxy_not_started"
        proxy.heal.assert_not_called()

        proxy.started = True
        proxy.heal.return_value = {"healed": 1, "unhealthy_before": ["github"]}
        out = run_kind("proxy_heal", {})
        assert out["healed"] == 1
        proxy.heal.assert_called_once()

    with patch("kater.automations.builtins.prune_all", return_value=3):
        assert run_kind("telemetry_prune", {})["removed"] == 3

    with patch("kater.automations.builtins.scan_adapters") as scan:
        adapter = MagicMock()
        adapter.source.name = "github"
        adapter.missing_env = ["GITHUB_TOKEN"]
        inventory = MagicMock()
        inventory.sources = [adapter]
        scan.return_value = inventory
        with patch("kater.automations.builtins.record_event") as record:
            out = run_kind("credential_nudge", {"profile": "core"})
            assert out["missing_count"] == 1
            record.assert_called_once()


def test_api_list_seeds_defaults():
    resp = call("GET", "/api/automations")
    assert resp.status == 200
    assert resp.payload is not None
    assert resp.payload["total"] == len(DEFAULT_AUTOMATIONS)
    assert len(resp.payload["automations"]) == len(DEFAULT_AUTOMATIONS)


def test_api_crud_enable_run_delete():
    create = call(
        "POST",
        "/api/automations",
        body={
            "id": "auto_api_test",
            "name": "API test",
            "kind": "browser_reap",
            "schedule_seconds": 30,
            "config": {},
        },
    )
    assert create.status == 200
    assert create.payload is not None
    assert create.payload["id"] == "auto_api_test"

    got = call("GET", "/api/automations/auto_api_test")
    assert got.status == 200

    disabled = call("POST", "/api/automations/auto_api_test/disable")
    assert disabled.status == 200
    assert disabled.payload is not None
    assert disabled.payload["enabled"] is False

    refused = call("POST", "/api/automations/auto_api_test/run")
    assert refused.status == 400
    assert refused.payload is not None
    assert "disabled" in refused.payload["error"]

    patched = call(
        "PATCH",
        "/api/automations/auto_api_test",
        body={"enabled": True},
    )
    assert patched.status == 200
    assert patched.payload is not None
    assert patched.payload["enabled"] is True

    with patch("kater.automations.builtins.get_manager") as manager_factory:
        manager = MagicMock()
        manager.reap_expired.return_value = 0
        manager_factory.return_value = manager
        ran = call("POST", "/api/automations/auto_api_test/run")
    assert ran.status == 200
    assert ran.payload is not None
    assert ran.payload["status"] == "ok"

    deleted = call("DELETE", "/api/automations/auto_api_test")
    assert deleted.status == 200
    missing = call("GET", "/api/automations/auto_api_test")
    assert missing.status == 404


def test_api_rejects_unknown_kind():
    resp = call(
        "POST",
        "/api/automations",
        body={"name": "Nope", "kind": "not_a_real_kind"},
    )
    assert resp.status == 400
    assert resp.payload is not None
    assert "unknown" in resp.payload["error"]


def test_get_engine_singleton_and_reset():
    first = get_engine()
    second = get_engine()
    assert first is second
    reset_engine()
    third = get_engine()
    assert third is not first


class TestModelsToDict:
    def test_automation_to_dict(self):
        auto = Automation(
            id="auto_x",
            name="Watch",
            kind="doctor_watch",
            enabled=True,
            schedule_seconds=60,
            config={"profile": "core"},
            last_run_at=10.0,
            last_status="ok",
            last_error=None,
            created_at=1.0,
            updated_at=2.0,
        )
        as_dict = auto.to_dict()
        assert as_dict == {
            "id": "auto_x",
            "name": "Watch",
            "enabled": True,
            "kind": "doctor_watch",
            "schedule_seconds": 60,
            "config": {"profile": "core"},
            "last_run_at": 10.0,
            "last_status": "ok",
            "last_error": None,
            "created_at": 1.0,
            "updated_at": 2.0,
        }

    def test_automation_to_dict_config_is_a_copy(self):
        # Mutating the returned dict must not affect the Automation's config.
        config = {"profile": "core"}
        auto = Automation(id="auto_y", name="Y", kind="doctor_watch", config=config)
        payload = auto.to_dict()
        payload["config"]["profile"] = "mutated"
        assert auto.config == {"profile": "core"}

    def test_automation_run_result_to_dict_rounds_duration(self):
        result = AutomationRunResult(
            id="auto_z",
            kind="doctor_watch",
            status="ok",
            error=None,
            detail={"findings": 0},
            duration_ms=12.3456,
            ran_at=100.0,
        )
        as_dict = result.to_dict()
        assert as_dict == {
            "id": "auto_z",
            "kind": "doctor_watch",
            "status": "ok",
            "error": None,
            "detail": {"findings": 0},
            "duration_ms": 12.35,
            "ran_at": 100.0,
        }


class TestAutomationStoreFacade:
    def test_facade_delegates_to_module_functions(self):
        store = AutomationStore()
        auto = Automation(
            id=new_automation_id(),
            name="Facade",
            kind="doctor_watch",
            schedule_seconds=30,
            config={},
            created_at=5.0,
            updated_at=5.0,
        )
        saved = store.upsert(auto)
        assert saved.id == auto.id
        assert store.get(auto.id) == saved
        assert store.count() >= 1
        assert saved in store.list()

        updated = store.set_enabled(auto.id, False)
        assert updated is not None
        assert updated.enabled is False

        ran = store.record_run(auto.id, ran_at=6.0, status="ok", error=None)
        assert ran is not None
        assert ran.last_run_at == 6.0

        assert store.delete(auto.id) is True
        assert store.get(auto.id) is None

    def test_facade_reset_cache_does_not_raise(self):
        store = AutomationStore()
        store.reset_cache()
        # The underlying connection is lazily recreated on next use.
        assert store.count() >= 0


def test_run_now_refuses_when_already_in_flight():
    engine = AutomationEngine(clock=lambda: 42.0)
    engine.upsert(
        id="auto_concurrent",
        name="Concurrent",
        kind="browser_reap",
        schedule_seconds=60,
    )
    # Simulate a run already in progress via the engine's internal guard.
    engine._in_flight.add("auto_concurrent")
    try:
        with pytest.raises(ValueError, match="already running"):
            engine.run_now("auto_concurrent")
    finally:
        engine._in_flight.discard("auto_concurrent")


def test_run_now_raises_keyerror_for_missing_automation():
    engine = AutomationEngine(clock=lambda: 42.0)
    with pytest.raises(KeyError):
        engine.run_now("auto_does_not_exist")


def test_proxy_heal_wraps_non_dict_result():
    with patch("kater.automations.builtins.get_proxy") as proxy_factory:
        proxy = MagicMock(spec=["started", "heal"])
        proxy.started = True
        proxy.heal.return_value = 3
        proxy_factory.return_value = proxy
        out = run_kind("proxy_heal", {})
    assert out == {"healed": 3}


def test_api_get_missing_automation_returns_404():
    resp = call("GET", "/api/automations/auto_missing")
    assert resp.status == 404


def test_api_patch_missing_automation_returns_404():
    resp = call(
        "PATCH",
        "/api/automations/auto_missing",
        body={"enabled": False},
    )
    assert resp.status == 404


def test_api_enable_missing_automation_returns_404():
    resp = call("POST", "/api/automations/auto_missing/enable")
    assert resp.status == 404


def test_api_disable_missing_automation_returns_404():
    resp = call("POST", "/api/automations/auto_missing/disable")
    assert resp.status == 404


def test_api_delete_missing_automation_returns_404():
    resp = call("DELETE", "/api/automations/auto_missing")
    assert resp.status == 404


def test_api_run_missing_automation_returns_404():
    resp = call("POST", "/api/automations/auto_missing/run")
    assert resp.status == 404


@pytest.fixture
def ctx_db(tmp_path, monkeypatch):
    """Isolated working directory + reset caches for context-token tests."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KATER_CONTEXT_TOKEN_SECRET", "test-context-secret")
    from kater.control_plane import contexts
    from kater.control_plane import tokens as context_tokens

    context_tokens.reset_token_secret_cache()
    contexts.reset_cache()
    yield tmp_path
    contexts.reset_cache()
    context_tokens.reset_token_secret_cache()


def test_automations_rest_denies_out_of_allowlist(ctx_db):
    from kater.control_plane import contexts
    from kater.control_plane import tokens as context_tokens

    record = contexts.create_context(
        principal_id="agent-automations",
        allowed_capabilities=["kater.profiles.list"],
    )
    token = context_tokens.issue_token(record, ttl_seconds=300)
    headers = {"x-kater-context": token}

    resp = call("GET", "/api/automations", headers=headers)
    assert resp.status == 403
    assert resp.payload is not None
    assert resp.payload["code"] == "capability_denied"
    assert resp.payload["capability_id"] == "kater.automations.list"


def test_automations_rest_allows_dotted_prefix_allowlist(ctx_db):
    from kater.control_plane import contexts
    from kater.control_plane import tokens as context_tokens

    record = contexts.create_context(
        principal_id="agent-automations",
        allowed_capabilities=["kater.automations"],
    )
    token = context_tokens.issue_token(record, ttl_seconds=300)
    headers = {"x-kater-context": token}

    resp = call("GET", "/api/automations", headers=headers)
    assert resp.status == 200
