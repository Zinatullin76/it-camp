"""
session_recorder.py
===================
SessionRecorder — high-level adapter between the DigitalTwin / API layer
and the persistent SessionStore.

It turns the live simulation into an immutable event log for the AI
error-classification service. While a training session is active, the
recorder persists, on every step:
  - the current process snapshot (context before / after each action),
  - every operator action (and the error event it triggered, if any),
  - every new alarm,
  - every rule-detected operator error.

Usage (driven from the API layer):
    recorder = SessionRecorder(store)
    recorder.begin(scenario_id, operator_id, reference_actions=[...])
    ... run the simulation, calling record_snapshot / sync_alarms / sync_errors ...
    recorder.end(sim_end, score, qualification)

The recorder is a no-op while no session is active, so logging can be
safely invoked from shared code paths (e.g. every simulation step).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from models.base import ErrorEvent, OperatorAction, SimulationState
from persistence.session_store import SessionStore


class SessionRecorder:
    """Log a live training session into a SessionStore."""

    def __init__(self, store: SessionStore):
        self._store = store
        self._session_id: Optional[str] = None
        self._logged_alarm_keys: set = set()
        self._logged_error_keys: set = set()

    @property
    def store(self) -> SessionStore:
        return self._store

    @property
    def session_id(self) -> Optional[str]:
        return self._session_id

    @property
    def active(self) -> bool:
        return self._session_id is not None

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def begin(
        self,
        scenario_id: str,
        operator_id: str,
        scheme_version: str = "",
        reference_actions: Optional[List[Dict[str, Any]]] = None,
        sim_start: float = 0.0,
        wall_time: Optional[float] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Open a new persisted session and (re)arm the dedup sets."""
        self._session_id = self._store.begin_session(
            scenario_id, operator_id,
            session_id=session_id,
            scheme_version=scheme_version, sim_start=sim_start, wall_time=wall_time,
        )
        if reference_actions:
            self._store.seed_expected_actions(scenario_id, reference_actions)
        self._store.start_session(self._session_id, sim_start=sim_start, wall_time=wall_time)
        self._logged_alarm_keys.clear()
        self._logged_error_keys.clear()
        return self._session_id

    def end(
        self,
        sim_end: float,
        score: Optional[float] = None,
        qualification: str = "",
        ai_verdict: Optional[Dict[str, Any]] = None,
        wall_time: Optional[float] = None,
    ) -> None:
        """Complete the active session and detach the recorder."""
        if not self.active:
            return
        self._store.finish_session(
            self._session_id, sim_end, score=score, qualification=qualification,
            ai_verdict=ai_verdict, wall_time=wall_time,
        )
        self._session_id = None

    def abort(self, sim_end: Optional[float] = None, reason: str = "", wall_time: Optional[float] = None) -> None:
        if not self.active:
            return
        self._store.abort_session(self._session_id, reason=reason, wall_time=wall_time)
        self._session_id = None

    # ------------------------------------------------------------------
    # Event logging
    # ------------------------------------------------------------------

    def record_action(
        self,
        action: OperatorAction,
        wall_time: Optional[float] = None,
        accepted: bool = True,
        reject_reason: str = "",
        node_type: Optional[str] = None,
    ) -> Optional[int]:
        """Persist one operator action; returns the action row id or None."""
        if not self.active:
            return None
        return self._store.append_action(
            self._session_id, action,
            wall_time=wall_time, accepted=accepted,
            reject_reason=reject_reason, node_type=node_type,
        )

    def record_snapshot(
        self,
        state: SimulationState,
        reason: str = "step",
        action_id: Optional[int] = None,
        wall_time: Optional[float] = None,
    ) -> Optional[int]:
        """Persist the process context at the current moment."""
        if not self.active:
            return None
        return self._store.append_snapshot(
            self._session_id, state, reason=reason, action_id=action_id, wall_time=wall_time,
        )

    def sync_alarms(self, alarm_history: List) -> int:
        """Persist any alarms not seen yet (idempotent per (id, time))."""
        if not self.active:
            return 0
        count = 0
        for alarm in alarm_history:
            key = (alarm.id, round(alarm.timestamp, 4))
            if key in self._logged_alarm_keys:
                continue
            self._store.append_alarm(self._session_id, alarm)
            self._logged_alarm_keys.add(key)
            count += 1
        return count

    def sync_errors(self, error_events: List[ErrorEvent], action_id: Optional[int] = None) -> int:
        """Persist new rule-detected errors; link a single new event to its action."""
        if not self.active:
            return 0
        count = 0
        new_ids: List[int] = []
        for error in error_events:
            key = (
                error.error_type,
                round(error.timestamp, 4),
                error.operator_action,
                error.expected_action,
            )
            if key in self._logged_error_keys:
                continue
            self._logged_error_keys.add(key)
            row_id = self._store.append_error(self._session_id, error)
            new_ids.append(row_id)
            count += 1
        if action_id is not None and len(new_ids) == 1:
            self._store.link_error_action(new_ids[0], action_id)
        return count
