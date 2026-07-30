from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from kater.browser import store
from kater.browser.models import (
    ActionKind,
    ActionResult,
    BrowserSession,
    ProviderKind,
    SessionState,
    new_session_id,
)


@pytest.fixture(autouse=True)
def _clean_browser_store(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store.reset_cache()
    yield
    store.reset_cache()


def make_session(**overrides) -> BrowserSession:
    """
    Create a browser session with standard test values and optional overrides.
    
    Parameters:
        overrides: Field values that replace the standard session defaults.
    
    Returns:
        BrowserSession: The constructed browser session.
    """
    defaults = dict(
        session_id=new_session_id(),
        provider=ProviderKind.LOCAL,
        state=SessionState.READY,
        created_at=1000.0,
        last_used_at=1000.0,
        expires_at=1900.0,
        label="lane",
        profile="core",
    )
    defaults.update(overrides)
    return BrowserSession(**defaults)


def make_result(session_id: str, **overrides) -> ActionResult:
    """Build an action result with standard test values and optional overrides.
    
    Parameters:
        session_id (str): Identifier of the session associated with the action.
        overrides: Field values that replace the defaults.
    
    Returns:
        ActionResult: The configured action result.
    """
    defaults = dict(
        ok=True,
        kind=ActionKind.NAVIGATE,
        session_id=session_id,
        started_at=1000.0,
        duration_ms=12.0,
        url="https://example.com/",
    )
    defaults.update(overrides)
    return ActionResult(**defaults)


def test_session_round_trip():
    session = make_session(current_url="https://example.com/", title="Example")
    store.upsert_session(session)
    loaded = store.get_session(session.session_id)
    assert loaded == session


def test_get_session_missing_returns_none():
    assert store.get_session("bsess_" + "0" * 32) is None


def test_upsert_updates_existing_row():
    session = make_session()
    store.upsert_session(session)
    store.upsert_session(session.with_state(SessionState.CLOSED, title="Done", error="boom"))
    loaded = store.get_session(session.session_id)
    assert loaded is not None
    assert loaded.state is SessionState.CLOSED
    assert loaded.title == "Done"
    assert loaded.error == "boom"
    assert len(store.list_sessions()) == 1


def test_list_sessions_is_newest_first_and_bounded():
    for index in range(5):
        store.upsert_session(make_session(created_at=1000.0 + index))
    listed = store.list_sessions()
    assert [s.created_at for s in listed] == [1004.0, 1003.0, 1002.0, 1001.0, 1000.0]
    assert len(store.list_sessions(limit=2)) == 2


def test_delete_session_removes_actions_too():
    session = make_session()
    store.upsert_session(session)
    store.record_action(make_result(session.session_id))
    assert store.delete_session(session.session_id) is True
    assert store.get_session(session.session_id) is None
    assert store.list_actions(session.session_id) == []
    assert store.delete_session(session.session_id) is False


def test_action_log_orders_newest_first_and_keeps_fields():
    session = make_session()
    store.upsert_session(session)
    store.record_action(make_result(session.session_id, kind=ActionKind.NAVIGATE))
    store.record_action(
        make_result(session.session_id, kind=ActionKind.CLICK, ok=False, error="no such element"),
        detail={"selector": "#missing"},
    )
    rows = store.list_actions(session.session_id)
    assert [row["kind"] for row in rows] == ["click", "navigate"]
    assert rows[0]["ok"] is False
    assert rows[0]["error"] == "no such element"
    assert rows[0]["detail"] == {"selector": "#missing"}
    assert rows[1]["detail"] is None
    assert rows[1]["url"] == "https://example.com/"


def test_list_actions_filters_by_session():
    first, second = make_session(), make_session()
    for session in (first, second):
        store.upsert_session(session)
        store.record_action(make_result(session.session_id))
    assert len(store.list_actions()) == 2
    assert len(store.list_actions(first.session_id)) == 1
    assert store.count_actions(second.session_id) == 1
    assert store.count_actions() == 2


def test_prune_actions_drops_oldest():
    session = make_session()
    store.upsert_session(session)
    for index in range(10):
        store.record_action(make_result(session.session_id, started_at=1000.0 + index))
    removed = store.prune_actions(max_rows=4)
    assert removed == 6
    rows = store.list_actions(session.session_id)
    assert len(rows) == 4
    assert [row["started_at"] for row in rows] == [1009.0, 1008.0, 1007.0, 1006.0]
    assert store.prune_actions(max_rows=4) == 0


def test_prune_actions_to_zero_empties_the_log():
    session = make_session()
    store.upsert_session(session)
    store.record_action(make_result(session.session_id))
    assert store.prune_actions(max_rows=0) == 1
    assert store.count_actions() == 0


def test_store_recovers_when_the_kater_dir_is_removed():
    """
    KEEP_EXISTING
    """
    store.upsert_session(make_session())
    shutil.rmtree(Path.cwd() / ".kater")
    session = make_session()
    store.upsert_session(session)
    assert store.get_session(session.session_id) == session


def test_reset_cache_reopens_the_database():
    session = make_session()
    store.upsert_session(session)
    store.reset_cache()
    assert store.get_session(session.session_id) == session


def test_unknown_enum_values_fall_back_safely():
    session = make_session()
    store.upsert_session(session)
    db = store._get_db()
    db.execute(
        "UPDATE browser_sessions SET state = ?, provider = ? WHERE session_id = ?",
        ("gremlin", "quantum", session.session_id),
    )
    db.commit()
    loaded = store.get_session(session.session_id)
    assert loaded is not None
    assert loaded.state is SessionState.FAILED
    assert loaded.provider is ProviderKind.LOCAL
