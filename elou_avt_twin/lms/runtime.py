"""
lms/runtime.py
==============
Decoupling bridge between the API server and the LMS content layer.

The content API needs live access to the simulator (physical core) to run
DB-defined scenarios and to evaluate the final process state for practice
scoring. To avoid a circular import (api_server -> lms.content_api ->
api_server) the main server registers its singletons here at startup and
the content layer reads them lazily.

Registered by api_server.configure_runtime(...) after the twin is created:

    twin            -> DigitalTwin instance
    scheme_store    -> current ProcessScheme
    session_store   -> SessionStore (training sessions)
    inputs          -> dict with feed overrides
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("lms.runtime")

_twin: Any = None
_scheme_store: Any = None
_session_store: Any = None
_session_recorder: Any = None
_inputs: Dict[str, float] = {}


def configure(twin: Any, scheme_store: Any, session_store: Any,
              session_recorder: Any = None,
              inputs: Optional[Dict[str, float]] = None) -> None:
    global _twin, _scheme_store, _session_store, _session_recorder, _inputs
    _twin = twin
    _scheme_store = scheme_store
    _session_store = session_store
    _session_recorder = session_recorder
    if inputs is not None:
        _inputs = inputs


def get_twin() -> Any:
    if _twin is None:
        raise RuntimeError("Runtime not configured: twin is not available")
    return _twin


def get_scheme() -> Any:
    return _scheme_store


def get_session_store() -> Any:
    return _session_store


def get_session_recorder() -> Any:
    return _session_recorder


def get_inputs() -> Dict[str, float]:
    return _inputs


def restore_alarm_setpoints() -> None:
    """Re-apply operator-saved alarm overrides from the database.

    ``twin.create_simulation()`` builds a fresh engine whose
    ``_alarm_setpoint_overrides`` are empty, so setpoints saved through
    ``PUT /alarms/setpoints`` would be silently dropped on the next practice
    or scenario start. Call right after every ``create_simulation()``.
    """
    twin = get_twin()
    if twin is None or twin._engine is None:
        return
    try:
        from persistence.session_store import SessionStore
        store = SessionStore()
        try:
            restored = 0
            for sp in store.load_alarm_setpoints():
                if twin._engine.restore_alarm_setpoint(
                    sp["parameter"], sp["low_low"], sp["low"], sp["high"],
                    sp["high_high"], sp["unit"] or "",
                ):
                    restored += 1
            if restored:
                logger.info("Restored %d saved alarm setpoint(s).", restored)
        finally:
            store.close()
    except Exception:
        logger.exception("Failed to restore alarm setpoints")


def node_telemetry() -> Dict[str, Dict[str, Any]]:
    """Per-node live state used by the practice assessment.

    Mirrors api_server._build_node_telemetry but is self-contained so the
    content layer never imports the API server.
    """
    twin = get_twin()
    scheme = get_scheme()
    if scheme is None:
        return {}
    outputs = twin._engine.get_last_outputs()
    streams = twin._engine.get_last_streams()
    equip = twin._engine._equipment
    state = twin.get_state()
    telemetry: Dict[str, Dict[str, Any]] = {}

    for node in scheme.nodes:
        nid, ntype = node.id, node.type
        out = outputs.get(nid, {})
        eq = equip.get(nid)
        s = out.get("outlet_stream")
        if s is None:
            s = streams.get(f"{nid}:out")

        item: Dict[str, Any] = {
            "type": ntype,
            "name": node.name,
            "running": bool(eq.state.running) if eq else None,
            "failed": bool(eq.state.failed) if eq else None,
            "failure_mode": (eq.state.failure_mode or "") if eq else None,
            "params": {},
        }
        p = item["params"]
        if ntype == "pump":
            p["flow_kg_s"] = out.get("flow_out", 0.0)
            p["pressure_bar"] = round(s.pressure / 1e5, 3) if s else None
            p["temperature_c"] = round(s.temperature - 273.15, 2) if s else None
            p["speed_rpm"] = round(eq.speed, 1) if eq else None
            p["power_w"] = out.get("power", 0.0)
        elif ntype == "valve":
            p["position"] = round(out.get("position", 0.0) * 100.0, 2)
            p["flow_kg_s"] = out.get("flow_out", 0.0)
        elif ntype in ("separator", "separator_s1k", "tank"):
            p["level_m"] = out.get("level")
            p["in_flow"] = round(out.get("in_flow", 0.0), 3)
            p["out_flow"] = round(out.get("out_flow", 0.0), 3)
        elif ntype == "mixer":
            p["flow_kg_s"] = round(s.mass_flow, 3) if s else 0.0
        elif ntype == "elou":
            p["level_m"] = state.level.get("elou")
            p["temperature_c"] = round(s.temperature - 273.15, 2) if s else None
            p["pressure_bar"] = round(s.pressure / 1e5, 3) if s else None
        elif ntype == "heat_exchanger":
            p["duty_w"] = out.get("duty", 0.0)
        elif ntype == "heater":
            p["fuel_flow"] = eq.fuel_flow if eq else 0.0
            p["outlet_temp_c"] = round(eq.outlet_temp - 273.15, 2) if eq else None
        elif ntype == "column":
            p["pressure_bar"] = round(dist_flow_pressure(out.get("distillate")) / 1e5, 3)
            p["level_m"] = state.level.get("column")
        elif ntype == "source":
            p["flow_kg_s"] = round(s.mass_flow, 3) if s else 0.0
        elif ntype == "sink":
            for edge in scheme.edges:
                if edge.target == nid:
                    s_in = streams.get(f"{edge.source}:{edge.source_port}")
                    if s_in is not None:
                        break
            else:
                s_in = None
            p["flow_kg_s"] = round(s_in.mass_flow, 3) if s_in else None

        telemetry[nid] = item

    telemetry["_global"] = {
        "feed_flow": state.feed_flow,
        "product_flow": state.product_flow,
        "pressure": {k: v for k, v in state.pressure.items()},
        "temperature": {k: v for k, v in state.temperature.items()},
        "level": {k: v for k, v in state.level.items()},
        "valve_positions": {k: round(v * 100.0, 2) for k, v in state.valve_positions.items()},
        "pump_states": {k: v for k, v in state.pump_states.items()},
        "active_failures": list(state.active_failures or []),
        "simulation_time": twin._simulation_time,
    }
    return telemetry


def dist_flow_pressure(dist: Any) -> float:
    return dist.pressure if dist is not None else 0.0
