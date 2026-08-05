"""
test_training_session.py
=========================
Unit tests for the TrainingSession domain model (Training Layer skeleton).

Covers:
  1.  Default lifecycle state
  2.  Start transition + event recording
  3.  Arbitrary event recording
  4.  Finish with score and qualification
  5.  Abort transition
  6.  Serialization round-trip
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from models.session import TrainingSession, SessionStatus


def _session() -> TrainingSession:
    return TrainingSession(
        session_id="S-001", scenario_id="PUMP_FAILURE_001", operator_id="op1",
    )


def test_default_state():
    """A new session is CREATED with empty event log."""
    s = _session()
    assert s.status == SessionStatus.CREATED
    assert s.events == []
    assert s.performance_score is None


def test_start_transition():
    """start() moves to RUNNING and records a START event."""
    s = _session()
    s.start(at=0.0)
    assert s.status == SessionStatus.RUNNING
    assert s.started_at == 0.0
    assert s.events[0].kind == "START"


def test_record_event():
    """record() appends structured events."""
    s = _session()
    s.start(at=0.0)
    s.record("FAULT", at=60.0, equipment_id="pump_P101", failure_mode="MECHANICAL_FAILURE")
    assert len(s.events) == 2
    assert s.events[1].kind == "FAULT"
    assert s.events[1].detail["equipment_id"] == "pump_P101"


def test_finish_sets_score():
    """finish() completes the session with a clamped score."""
    s = _session()
    s.start(at=0.0)
    s.finish(at=600.0, score=87.5, qualification="ХОРОШО")
    assert s.status == SessionStatus.COMPLETED
    assert s.finished_at == 600.0
    assert s.performance_score == 87.5
    assert s.qualification == "ХОРОШО"
    assert s.events[-1].kind == "END"


def test_finish_clamps_score():
    """Score must be clamped to [0, 100]."""
    s = _session()
    s.start(at=0.0)
    s.finish(at=10.0, score=150.0)
    assert s.performance_score == 100.0
    s2 = _session()
    s2.start(at=0.0)
    s2.finish(at=10.0, score=-20.0)
    assert s2.performance_score == 0.0


def test_abort_transition():
    """abort() moves to ABORTED with a reason."""
    s = _session()
    s.start(at=0.0)
    s.abort(at=30.0, reason="operator request")
    assert s.status == SessionStatus.ABORTED
    assert s.events[-1].detail["reason"] == "operator request"


def test_round_trip():
    """TrainingSession must survive model_dump -> model_validate."""
    s = _session()
    s.start(at=0.0)
    s.record("ACTION", at=5.0, tag="valve_FV1", value=0.6)
    s2 = TrainingSession.model_validate(s.model_dump())
    assert s2.status == SessionStatus.RUNNING
    assert len(s2.events) == 2
