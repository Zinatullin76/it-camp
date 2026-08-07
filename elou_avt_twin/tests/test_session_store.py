"""
test_session_store.py
=====================
Unit tests for the SQLite SessionStore (AI error-classification corpus).

Covers:
  1.  Session lifecycle (begin -> start -> finish / abort)
  2.  Operator action append + read-back
  3.  State snapshot append + read-back
  4.  Alarm lifecycle (raise / ack / clear)
  5.  Error events + AI classification workflow
  6.  Expected (reference) action seeding
  7.  AI classification audit + human correction
  8.  Full session export
  9.  Persistence across store reopen
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from models.base import OperatorAction, ActionType, Alarm, ErrorEvent, Severity, SimulationState
from persistence.session_store import SessionStore


@pytest.fixture()
def store(tmp_path):
    s = SessionStore(str(tmp_path / "sessions.db"))
    yield s
    s.close()


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
    defaults = dict(
        timestamp=10.0,
        pressure={"discharge": 2.0e5},
        temperature={"outlet": 320.0},
        feed_flow=50.0,
        product_flow=48.0,
        level={"separator": 0.7},
        pump_states={"pump_P102": True},
        valve_positions={"valve_FV101": 0.6},
        active_failures=["pump_P101"],
    )
    defaults.update(kw)
    return SimulationState(**defaults)


def test_session_lifecycle(store):
    sid = store.begin_session(scenario_id="PUMP_FAILURE_001", operator_id="op1")
    s = store.get_session(sid)
    assert s["status"] == "CREATED"
    assert s["scenario_id"] == "PUMP_FAILURE_001"

    store.start_session(sid, sim_start=0.0)
    store.finish_session(sid, sim_end=600.0, score=87.5, qualification="ХОРОШО",
                        ai_verdict={"class": "no_error", "confidence": 0.9})
    s = store.get_session(sid)
    assert s["status"] == "COMPLETED"
    assert s["performance_score"] == 87.5
    assert s["qualification"] == "ХОРОШО"
    assert s["ai_verdict"]["class"] == "no_error"


def test_session_abort(store):
    sid = store.begin_session("PUMP_FAILURE_001", "op1")
    store.abort_session(sid, reason="operator request")
    assert store.get_session(sid)["status"] == "ABORTED"


def test_action_append(store):
    sid = store.begin_session("PUMP_FAILURE_001", "op1")
    aid = store.append_action(sid, _action(), wall_time=1.0, node_type="pump")
    actions = store.get_actions(sid)
    assert len(actions) == 1
    a = actions[0]
    assert a["id"] == aid
    assert a["seq"] == 1
    assert a["equipment_id"] == "pump_P102"
    assert a["action_type"] == "TURN_ON"
    assert a["new_value"] == 1.0
    assert a["old_value"] == 0.0
    assert a["node_type"] == "pump"
    assert a["accepted"] == 1


def test_action_seq_monotonic(store):
    sid = store.begin_session("PUMP_FAILURE_001", "op1")
    store.append_action(sid, _action(timestamp=1.0))
    store.append_action(sid, _action(timestamp=2.0, equipment_id="valve_FV101",
                                     action_type=ActionType.SET_VALUE, new_value=0.6))
    assert [a["seq"] for a in store.get_actions(sid)] == [1, 2]


def test_snapshot_append(store):
    sid = store.begin_session("PUMP_FAILURE_001", "op1")
    aid = store.append_action(sid, _action(), wall_time=1.0)
    snap_id = store.append_snapshot(sid, _state(), reason="action", action_id=aid)
    snaps = store.get_snapshots(sid)
    assert len(snaps) == 1
    sp = snaps[0]
    assert sp["id"] == snap_id
    assert sp["reason"] == "action"
    assert sp["action_id"] == aid
    assert sp["pressure"]["discharge"] == 2.0e5
    assert sp["flows"]["feed_flow"] == 50.0
    assert sp["pump_states"]["pump_P102"] is True
    assert sp["active_failures"] == ["pump_P101"]


def test_alarm_lifecycle(store):
    sid = store.begin_session("PUMP_FAILURE_001", "op1")
    store.append_alarm(sid, _alarm())
    store.update_alarm_event(sid, "A-1", acked_at=65.0, acked_by="op1")
    store.update_alarm_event(sid, "A-1", cleared_at=80.0)
    alarms = store.get_alarms(sid)
    assert len(alarms) == 1
    assert alarms[0]["acked_at"] == 65.0
    assert alarms[0]["acked_by"] == "op1"
    assert alarms[0]["cleared_at"] == 80.0


def test_alarm_replay_idempotent(store):
    sid = store.begin_session("PUMP_FAILURE_001", "op1")
    store.append_alarm(sid, _alarm())
    store.append_alarm(sid, _alarm())
    assert len(store.get_alarms(sid)) == 1


def test_error_and_classification_flow(store):
    sid = store.begin_session("PUMP_FAILURE_001", "op1")
    snap_id = store.append_snapshot(sid, _state(), reason="action")
    eid = store.append_error(sid, _error(), context_snapshot_id=snap_id)

    pending = store.get_unclassified_errors()
    assert len(pending) == 1
    assert pending[0]["ai_status"] == "pending"
    assert pending[0]["context_snapshot_id"] == snap_id

    store.set_error_classification(eid, ai_class="NO_STANDBY_SWITCHOVER",
                                   confidence=0.82, reasoning="P-102 not started")
    classified = store.get_errors(sid)[0]
    assert classified["ai_status"] == "classified"
    assert classified["ai_class"] == "NO_STANDBY_SWITCHOVER"

    cid = store.append_ai_classification(
        sid, predicted_class="NO_STANDBY_SWITCHOVER",
        input_payload={"context": "feed_loss", "action": "none"},
        error_event_id=eid, confidence=0.82, reasoning="timeout", latency_ms=12.3,
    )
    store.correct_classification(cid, correction="DELAYED_ACTION")
    classifications = store.get_classifications(sid)
    assert classifications[0]["human_corrected"] == 1
    assert classifications[0]["human_correction"] == "DELAYED_ACTION"

    assert store.get_unclassified_errors() == []


def test_seed_expected_actions(store):
    refs = [
        {"t": 65.0, "action": "TURN_ON", "equipment": "pump_P102", "weight": 2.0},
        {"t": 70.0, "action": "SET_VALUE", "equipment": "valve_FV101", "value": 0.6},
    ]
    n = store.seed_expected_actions("PUMP_FAILURE_001", refs)
    assert n == 2
    n2 = store.seed_expected_actions("PUMP_FAILURE_001", refs)
    assert n2 == 0
    rows = store.get_expected_actions("PUMP_FAILURE_001")
    assert len(rows) == 2
    assert rows[0]["deadline_t"] == 65.0
    assert rows[1]["value"] == 0.6


def test_export_session(store):
    sid = store.begin_session("PUMP_FAILURE_001", "op1")
    store.append_action(sid, _action(), wall_time=1.0)
    store.append_snapshot(sid, _state(), reason="action")
    store.append_alarm(sid, _alarm())
    store.append_error(sid, _error())

    data = store.export_session(sid)
    assert data is not None
    assert data["session"]["id"] == sid
    assert len(data["actions"]) == 1
    assert len(data["snapshots"]) == 1
    assert len(data["alarms"]) == 1
    assert len(data["error_events"]) == 1


def test_export_missing_session(store):
    assert store.export_session("NO_SUCH") is None


def test_persistence_across_reopen(tmp_path):
    path = str(tmp_path / "persist.db")
    s1 = SessionStore(path)
    sid = s1.begin_session("PUMP_FAILURE_001", "op1")
    s1.append_action(sid, _action(), wall_time=1.0)
    s1.close()

    s2 = SessionStore(path)
    data = s2.export_session(sid)
    s2.close()
    assert data is not None
    assert len(data["actions"]) == 1
    assert data["actions"][0]["equipment_id"] == "pump_P102"


def test_in_memory_store():
    store = SessionStore.in_memory()
    sid = store.begin_session("NORMAL_OPERATION", "demo")
    assert store.get_session(sid)["operator_id"] == "demo"
    store.close()
