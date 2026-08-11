"""
lms/scenario_service.py
=======================
Converts a DB-defined scenario (lms_scenarios, «Обуч.txt» §15-§19) into the
engine's `Scenario` object and executes it on the physical core.

Event type mapping (instructor writes only the cause):

    fault  -> INJECT_FAILURE  (H-1 отказал — consequences computed by physics)
    param  -> SET_PARAM
    state  -> SET_STATE
    alarm  -> RAISE_ALARM
    mode   -> SET_PARAM (нагрузка)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from models.scenario import Scenario, ScenarioEvent

EVENT_TYPE_MAP = {
    "fault": "INJECT_FAILURE",
    "param": "SET_PARAM",
    "state": "SET_STATE",
    "alarm": "RAISE_ALARM",
    "mode": "SET_PARAM",
}


def to_engine_event(e: Dict[str, Any]) -> ScenarioEvent:
    et = str(e.get("event_type", "fault")).lower()
    target = e.get("object_id", "")
    value = e.get("value")
    t = float(e.get("time", 0.0))
    engine_type = EVENT_TYPE_MAP.get(et, "INJECT_FAILURE")

    if engine_type == "INJECT_FAILURE":
        params = {"failure_mode": value or "MECHANICAL_FAILURE"}
    elif engine_type == "SET_STATE":
        state = "TURN_ON" if value in (True, "on", "ON", 1, "1", "running", True) else "TURN_OFF"
        params = {"state": state, "value": value if isinstance(value, (int, float)) else None}
    elif engine_type == "RAISE_ALARM":
        params = {
            "param": e.get("param") or f"{target}_alarm",
            "value": value if isinstance(value, (int, float)) else 1.0,
            "threshold": float(e.get("threshold", 0.0)),
            "severity": str(e.get("severity", "HIGH")),
            "description": str(e.get("message", "") or f"Авария: {target}"),
        }
    else:  # SET_PARAM / mode
        params = {"flow": value} if value is not None else {}

    return ScenarioEvent(timestamp=t, event_type=engine_type,
                         target_id=target, parameters=params)


def to_engine_scenario(defn: Dict[str, Any], reference_actions: Optional[List[Dict[str, Any]]] = None) -> Scenario:
    events = [to_engine_event(e) for e in defn.get("events", [])]
    duration_s = max(1, int(defn.get("duration_min", 10))) * 60.0
    # Действия без явно заданного срока (deadline_t) не регистрируются в
    # ErrorTracker (digital_twin._register_reference_actions пропускает их):
    # контроль по сроку применяется только когда инструктор задал время.
    # Раньше здесь стоял фолбэк «seq * 5 с», из-за которого невыполненное
    # действие почти всегда помечалось как просроченное.
    ref = reference_actions if reference_actions is not None else [
        {
            "t": a.get("deadline_t"),
            "action": a.get("action_type", ""),
            "equipment": a.get("object_id", ""),
            "attribute": a.get("attribute", ""),
            "value": a.get("value"),
            "description": a.get("description", ""),
            "weight": a.get("weight", 1.0),
        }
        for a in defn.get("expected_actions", [])
    ]
    return Scenario(
        id=f"LMS-{defn.get('id')}",
        name=defn.get("title", ""),
        description=defn.get("description", ""),
        initial_state=defn.get("initial_state", {}) or {},
        events=events,
        start_conditions={},
        end_conditions={"simulation_time": duration_s},
        success_criteria={},
        failure_criteria={},
        reference_actions=ref,
    )
