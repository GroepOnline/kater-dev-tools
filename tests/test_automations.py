"""Coverage for the automations store, engine, builtins, and REST routes."""

from __future__ import annotations

import sqlite3
import time
from unittest.mock import MagicMock, patch

import pytest

from kater import migrations
from kater.automations import (
    DEFAULT_AUTOMATIONS,
    Automation,
    AutomationEngine,
    get_engine,
    reset_engine,
)
from kater.automations import store as automations_store
from kater.automations.builtins import run_kind
from kater.automations.models import new_automation_id
from tests._rest import call


@pytest.fixture(autouse=True)
def _clean_automations(tmp_path, monkeypatch):
    # Isolate the store: each test gets its own migrated .kater/kater.db under
    # tmp_path instead of writing to the repository checkout.
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
    """Deleting every built-in must stick; the next list call may not re-seed."""
    engine = get_engine()
    seeded = engine.ensure_defaults()
    assert len(seeded) == len(DEFAULT_AUTOMATIONS)

    for item in seeded:
        assert automations_store.delete(item.id) is True
    assert automations_store.count() == 0

    # A fresh engine (as after a restart) still respects the deletions.
    reset_engine()
    assert get_engine().ensure_defaults() == []
    assert automations_store.count() == 0

    listed = call("GET", "/api/automations")
    assert listed.status == 200
    assert listed.payload is not None
    assert listed.payload["automations"] == []


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


def test_api_list_does_not_seed_defaults():
    """A GET must not create enabled schedules in an uninitialized store."""
    assert automations_store.count() == 0
    assert automations_store.AutomationStore().defaults_seeded() is False

    # Exercise the REST handler itself, not a mock read-only facade.
    with patch("kater.automations.engine.AutomationEngine.ensure_defaults") as seed:
        resp = call("GET", "/api/automations")
    seed.assert_not_called()
    assert resp.status == 200
    assert resp.payload == {"automations": [], "total": 0}
    assert automations_store.count() == 0
    assert automations_store.AutomationStore().defaults_seeded() is False

    # Startup/maintenance explicitly seed defaults, preserving existing UX.
    seeded = get_engine().ensure_defaults()
    assert len(seeded) == len(DEFAULT_AUTOMATIONS)
    populated = call("GET", "/api/automations")
    assert populated.status == 200
    assert populated.payload is not None
    assert populated.payload["total"] == len(DEFAULT_AUTOMATIONS)
    assert len(populated.payload["automations"]) == len(DEFAULT_AUTOMATIONS)


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


def _reap_manager(manager_factory: MagicMock) -> MagicMock:
    manager = MagicMock()
    manager.reap_expired.return_value = 0
    manager_factory.return_value = manager
    return manager


def test_runs_recorded_for_schedule_and_manual_triggers():
    clock = {"now": 1000.0}
    engine = AutomationEngine(clock=lambda: clock["now"])
    engine.upsert(id="auto_hist", name="Hist", kind="browser_reap", schedule_seconds=60)

    with patch("kater.automations.builtins.get_manager") as manager_factory:
        _reap_manager(manager_factory)
        assert engine.tick() == 1
        clock["now"] = 1010.0
        engine.run_now("auto_hist")

    runs = engine.list_runs("auto_hist")
    assert [(r.trigger, r.status, r.started_at) for r in runs] == [
        ("manual", "ok", 1010.0),
        ("schedule", "ok", 1000.0),
    ]
    assert all(r.finished_at is not None and r.error is None for r in runs)
    assert runs[0].to_dict()["duration_ms"] == 0.0


def test_scheduled_runs_record_their_own_start_time():
    clock = {"now": 1000.0}
    engine = AutomationEngine(clock=lambda: clock["now"])
    engine.upsert(id="auto_first", name="First", kind="browser_reap", schedule_seconds=60)
    engine.upsert(id="auto_second", name="Second", kind="browser_reap", schedule_seconds=60)

    def _slow_reap() -> int:
        clock["now"] += 5.0
        return 0

    with patch("kater.automations.builtins.get_manager") as manager_factory:
        manager = _reap_manager(manager_factory)
        manager.reap_expired.side_effect = _slow_reap
        assert engine.tick() == 2

    (first,) = engine.list_runs("auto_first")
    (second,) = engine.list_runs("auto_second")
    assert (first.started_at, first.finished_at) == (1000.0, 1005.0)
    assert (second.started_at, second.finished_at) == (1005.0, 1010.0)
    loaded = engine.get("auto_second")
    assert loaded is not None
    assert loaded.last_run_at == 1000.0


def test_history_write_gives_up_fast_on_locked_db_and_restores_timeout(tmp_path):
    db = automations_store._get_db()
    blocker = sqlite3.connect(tmp_path / ".kater" / "kater.db", timeout=0)
    try:
        blocker.execute("BEGIN IMMEDIATE")
        started = time.monotonic()
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            automations_store.start_run("auto_x", started_at=1.0, trigger="manual")
        assert time.monotonic() - started < 2.0
    finally:
        blocker.rollback()
        blocker.close()
    assert (
        db.execute("PRAGMA busy_timeout").fetchone()[0]
        == automations_store._DEFAULT_BUSY_TIMEOUT_MS
    )
    assert not db.in_transaction
    automations_store.start_run("auto_x", started_at=2.0, trigger="manual")
    assert [r.started_at for r in automations_store.list_runs("auto_x")] == [2.0]


def test_tick_survives_locked_last_run_update():
    engine = AutomationEngine(clock=lambda: 1000.0)
    engine.upsert(id="auto_one", name="One", kind="browser_reap", schedule_seconds=60)
    engine.upsert(id="auto_two", name="Two", kind="browser_reap", schedule_seconds=60)
    with (
        patch.object(
            automations_store.AutomationStore,
            "record_run",
            side_effect=sqlite3.OperationalError("database is locked"),
        ),
        patch("kater.automations.builtins.get_manager") as manager_factory,
    ):
        manager = _reap_manager(manager_factory)
        assert engine.tick() == 2
    assert manager.reap_expired.call_count == 2
    assert [r.status for r in engine.list_runs("auto_two")] == ["ok"]


def test_tick_cleanup_keeps_claims_retaken_by_concurrent_run():
    engine = AutomationEngine(clock=lambda: 1000.0)
    engine.upsert(id="auto_one", name="One", kind="browser_reap", schedule_seconds=60)

    class _RetakenClaims(set[str]):
        retaken = False

        def discard(self, item: str) -> None:
            super().discard(item)
            if not self.retaken:
                # Simulates one concurrent run_now claiming the id right after release.
                self.retaken = True
                self.add(item)

    engine._in_flight = _RetakenClaims()
    with patch("kater.automations.builtins.get_manager") as manager_factory:
        _reap_manager(manager_factory)
        assert engine.tick() == 1
    assert "auto_one" in engine._in_flight


def test_non_timeout_error_with_timeout_in_name_is_error():
    class InvalidTimeoutError(Exception):
        pass

    engine = AutomationEngine(clock=lambda: 42.0)
    engine.upsert(id="auto_cfg", name="Cfg", kind="doctor_watch", schedule_seconds=60)
    with patch("kater.automations.builtins.run_doctor", side_effect=InvalidTimeoutError("bad")):
        assert engine.run_now("auto_cfg").status == "error"


def test_history_write_discards_stale_transaction():
    db = automations_store._get_db()
    db.execute("BEGIN")
    db.execute(
        """INSERT INTO automation_runs (automation_id, started_at, status, "trigger")
           VALUES ('auto_stale', 1.0, 'unknown', 'manual')"""
    )
    automations_store.start_run("auto_x", started_at=2.0, trigger="manual")
    assert automations_store.list_runs("auto_stale") == []
    assert len(automations_store.list_runs("auto_x")) == 1


def test_aborted_tick_releases_unreached_claims():
    engine = AutomationEngine(clock=lambda: 1000.0)
    engine.upsert(id="auto_one", name="One", kind="browser_reap", schedule_seconds=60)
    engine.upsert(id="auto_two", name="Two", kind="browser_reap", schedule_seconds=60)
    with (
        patch.object(AutomationEngine, "_execute", side_effect=RuntimeError("boom")),
        pytest.raises(RuntimeError),
    ):
        engine.tick()
    assert engine._in_flight == set()


def test_run_errors_are_recorded_in_history():
    engine = AutomationEngine(clock=lambda: 42.0)
    engine.upsert(id="auto_bad_hist", name="Bad", kind="doctor_watch", schedule_seconds=60)
    with patch("kater.automations.builtins.run_doctor", side_effect=RuntimeError("boom")):
        engine.run_now("auto_bad_hist")
    (run,) = engine.list_runs("auto_bad_hist")
    assert (run.status, run.error, run.trigger) == ("error", "boom", "manual")


def test_timeout_is_recorded_as_unknown():
    engine = AutomationEngine(clock=lambda: 42.0)
    engine.upsert(id="auto_slow", name="Slow", kind="doctor_watch", schedule_seconds=60)
    with patch("kater.automations.builtins.run_doctor", side_effect=TimeoutError("30s")):
        result = engine.run_now("auto_slow")
    assert result.status == "unknown"
    (run,) = engine.list_runs("auto_slow")
    assert run.status == "unknown"
    assert run.error == "timeout: 30s"
    assert run.finished_at is not None
    loaded = engine.get("auto_slow")
    assert loaded is not None
    assert loaded.last_status == "unknown"


def test_http_client_timeout_is_recorded_as_unknown():
    class ReadTimeout(Exception):
        pass

    engine = AutomationEngine(clock=lambda: 42.0)
    engine.upsert(id="auto_http", name="Http", kind="doctor_watch", schedule_seconds=60)
    with patch("kater.automations.builtins.run_doctor", side_effect=ReadTimeout("read")):
        result = engine.run_now("auto_http")
    assert result.status == "unknown"
    (run,) = engine.list_runs("auto_http")
    assert (run.status, run.error) == ("unknown", "timeout: read")


def test_crash_mid_run_leaves_unknown_unfinished_run():
    engine = AutomationEngine(clock=lambda: 42.0)
    engine.upsert(id="auto_crash", name="Crash", kind="doctor_watch", schedule_seconds=60)
    with (
        patch("kater.automations.builtins.run_doctor", side_effect=KeyboardInterrupt),
        pytest.raises(KeyboardInterrupt),
    ):
        engine.run_now("auto_crash")
    (run,) = engine.list_runs("auto_crash")
    assert run.status == "unknown"
    assert run.finished_at is None
    assert run.to_dict()["duration_ms"] is None


def test_skipped_run_status():
    engine = AutomationEngine(clock=lambda: 42.0)
    engine.upsert(id="auto_heal", name="Heal", kind="proxy_heal", schedule_seconds=60)
    with patch("kater.automations.builtins.get_proxy") as proxy_factory:
        proxy = MagicMock(spec=["started", "heal"])
        proxy.started = False
        proxy_factory.return_value = proxy
        result = engine.run_now("auto_heal")
    assert result.status == "skipped"
    (run,) = engine.list_runs("auto_heal")
    assert run.status == "skipped"


def test_history_write_failure_does_not_block_run():
    engine = AutomationEngine(clock=lambda: 42.0)
    engine.upsert(id="auto_nohist", name="NoHist", kind="browser_reap", schedule_seconds=60)
    with (
        patch.object(
            automations_store.AutomationStore,
            "start_run",
            side_effect=sqlite3.OperationalError("database is locked"),
        ),
        patch("kater.automations.builtins.get_manager") as manager_factory,
    ):
        _reap_manager(manager_factory)
        result = engine.run_now("auto_nohist")
    assert result.status == "ok"
    assert engine.list_runs("auto_nohist") == []


def test_store_rejects_unknown_status_and_trigger():
    with pytest.raises(ValueError, match="trigger"):
        automations_store.start_run("auto_x", started_at=1.0, trigger="cron")
    run_id = automations_store.start_run("auto_x", started_at=1.0, trigger="manual")
    with pytest.raises(ValueError, match="status"):
        automations_store.finish_run(run_id, finished_at=2.0, status="cancelled", error=None)


def test_prune_runs_keeps_newest_per_automation_and_drops_orphans():
    engine = AutomationEngine(clock=lambda: 1.0)
    engine.upsert(id="auto_a", name="A", kind="browser_reap", schedule_seconds=60)
    engine.upsert(id="auto_b", name="B", kind="browser_reap", schedule_seconds=60)
    for i in range(5):
        automations_store.start_run("auto_a", started_at=float(i), trigger="schedule")
    automations_store.start_run("auto_b", started_at=1.0, trigger="schedule")
    automations_store.start_run("auto_gone", started_at=1.0, trigger="manual")

    assert automations_store.prune_runs(keep=2) == 4
    assert [r.started_at for r in engine.list_runs("auto_a")] == [4.0, 3.0]
    assert len(engine.list_runs("auto_b")) == 1
    assert engine.list_runs("auto_gone") == []

    deleted = engine.delete("auto_b")
    assert deleted is True
    assert engine.list_runs("auto_b") == []


def test_api_runs_endpoint():
    get_engine().upsert(id="auto_api_runs", name="Runs", kind="browser_reap", schedule_seconds=0)
    for i in range(3):
        automations_store.start_run("auto_api_runs", started_at=float(i), trigger="manual")

    resp = call("GET", "/api/automations/auto_api_runs/runs", query={"limit": ["2"]})
    assert resp.status == 200
    assert resp.payload is not None
    assert resp.payload["automation_id"] == "auto_api_runs"
    assert resp.payload["total"] == 2
    assert [r["started_at"] for r in resp.payload["runs"]] == [2.0, 1.0]
    assert resp.payload["runs"][0]["status"] == "unknown"
    assert resp.payload["runs"][0]["trigger"] == "manual"

    for bad in ("nope", "0", "-3"):
        rejected = call("GET", "/api/automations/auto_api_runs/runs", query={"limit": [bad]})
        assert rejected.status == 400, bad
    assert call("GET", "/api/automations/auto_missing/runs").status == 404


def test_get_engine_singleton_and_reset():
    first = get_engine()
    second = get_engine()
    assert first is second
    reset_engine()
    third = get_engine()
    assert third is not first
