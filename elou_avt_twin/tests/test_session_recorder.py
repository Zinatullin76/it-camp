"""
test_session_recorder.py
========================
Unit tests for the SessionRecorder adapter (live-session -> SessionStore).

Covers:
  1.  Inactive recorder is a no-op
  2.  begin() seeds expected actions and starts the session
  3.  record_action / record_snapshot persistence
  4.  sync_alarms deduplication
  5.  sync_errors deduplication + action linkage
  6.  end() / abort() session lifecycle
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from models.base import OperatorAction, ActionType, Alarm, ErrorEvent, Severity, SimulationState
from persistence.session_store import SessionStore
from persistence.session_recorder import SessionRecorder


@pytest.fixture()
def recorder():
    store = SessionStore.in_memory()
    rec = SessionRecorder(store)
    yield rec
    store.close()


def _action(**kw):
    defaults = dict(
        timestamp=10.0, operator_id="op1", equipment_id="pump_P102",
        action_type=ActionType.TURN_ON, old_value=0.0, new_value=1.0,
        source="operator_panel",
    )
    defaults.update(kw)
    return OperatorAction(**defaults)


def _alarm(**kw):
    defaults = dict(
        id="A-1", timestamp=60.0, parameter="feed_flow", actual_value=0.0,
        threshold=20.0, severity=Severity.HIGH, description="Feed loss",
    )
    defaults.update(kw)
    return Alarm(**defaults)


def _error(**kw):
    defaults = dict(
        error_type="MISSED_ACTION", severity=Severity.HIGH, timestamp=70.0,
        operator_action="no action", expected_action="start standby pump",
        cause="pump_P101 failed", consequence="feed loss",
    )
    defaults.update(kw)
    return ErrorEvent(**defaults)


def _state(**kw):
    defaults = dict(timestamp=10.0, feed_flow=50.0, pressure={"discharge": 2.0e5})
    defaults.update(kw)
    return SimulationState(**defaults)


def test_inactive_noop(recorder):
    assert recorder.active is False
    assert recorder.record_action(_action()) is None
    assert recorder.record_snapshot(_state()) is None
    assert recorder.sync_alarms([_alarm()]) == 0
    assert recorder.sync_errors([_error()]) == 0


def test_begin_sets_up_session(recorder):
    refs = [{"t": 65.0, "action": "TURN_ON", "equipment": "pump_P102"}]
    sid = recorder.begin(
        "PUMP_FAILURE_001", "op1", scheme_version="process_elou_avt",
        reference_actions=refs,
    )
    assert recorder.active is True
    session = recorder.store.get_session(sid)
    assert session["status"] == "RUNNING"
    assert session["scheme_version"] == "process_elou_avt"
    assert len(recorder.store.get_expected_actions("PUMP_FAILURE_001")) == 1


def test_record_action_and_snapshot(recorder):
    sid = recorder.begin("PUMP_FAILURE_001", "op1")
    aid = recorder.record_action(_action(), node_type="pump")
    recorder.record_snapshot(_state(), reason="action", action_id=aid)
    data = recorder.store.export_session(sid)
    assert len(data["actions"]) == 1
    assert data["actions"][0]["node_type"] == "pump"
    assert len(data["snapshots"]) == 1
    assert data["snapshots"][0]["action_id"] == aid


def test_sync_alarms_dedup(recorder):
    recorder.begin("PUMP_FAILURE_001", "op1")
    assert recorder.sync_alarms([_alarm()]) == 1
    assert recorder.sync_alarms([_alarm()]) == 0


def test_sync_errors_dedup_and_link(recorder):
    sid = recorder.begin("PUMP_FAILURE_001", "op1")
    aid = recorder.record_action(_action())
    assert recorder.sync_errors([_error()], action_id=aid) == 1
    assert recorder.sync_errors([_error()], action_id=aid) == 0
    err = recorder.store.get_errors(sid)[0]
    assert err["action_id"] == aid


def test_end_finishes_session(recorder):
    sid = recorder.begin("PUMP_FAILURE_001", "op1")
    recorder.end(600.0, score=90.0, qualification="ХОРОШО")
    assert recorder.active is False
    assert recorder.store.get_session(sid)["status"] == "COMPLETED"


def test_abort_marks_aborted(recorder):
    sid = recorder.begin("PUMP_FAILURE_001", "op1")
    recorder.abort(reason="operator request")
    assert recorder.active is False
    assert recorder.store.get_session(sid)["status"] == "ABORTED"
