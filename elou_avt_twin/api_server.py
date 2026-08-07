from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import threading
import time
import logging
import traceback
import re
from pathlib import Path

from models.base import SimulationConfig, OperatorAction, ActionType
from models.command import Command, CommandAction
from models.session import TrainingSession
from simulation_core.digital_twin import DigitalTwin
from scheme import ProcessScheme, SchemeNode, SchemeEdge, load_scheme, save_scheme
from equipment.params_spec import editor_spec, coerce, spec_for, NON_EDITABLE_TYPES
from controls import ControlSystem
from scenarios.scenario_registry import SCENARIO_REGISTRY
from persistence.session_store import SessionStore
from persistence.session_recorder import SessionRecorder
from auth.deps import authenticate_websocket, get_auth_service, get_current_user, require_permission
from auth.models import LoginRequest, RoleAssign, UserCreate
from lms.api import router as lms_router
from lms.content_api import router as lms_content_router
from lms import runtime as lms_runtime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("elou_avt.api")

app = FastAPI(title="ELOU-AVT Digital Twin API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(lms_router)
app.include_router(lms_content_router)


def _load_config() -> SimulationConfig:
    """Load SimulationConfig from config/default_config.json when present."""
    default = SimulationConfig(dt=1.0, random_seed=42)
    config_path = Path(__file__).resolve().parent / "config" / "default_config.json"
    if not config_path.exists():
        logger.warning("Config file %s not found; using defaults.", config_path)
        return default
    try:
        import json
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = {
            k: v for k, v in data.items()
            if k in SimulationConfig.model_fields
        }
        return SimulationConfig(**merged)
    except Exception:
        logger.exception("Failed to load config from %s; using defaults.", config_path)
        return default

class ActionRequest(BaseModel):
    equipment_id: str
    action_type: ActionType
    value: Optional[float] = None
    operator_id: str = "demo"

class InputRequest(BaseModel):
    flow_kg_s: Optional[float] = Field(None, ge=0)
    temperature_c: Optional[float] = Field(None, ge=-50, le=1000)
    pressure_bar: Optional[float] = Field(None, gt=0, le=200)

class ScenarioRequest(BaseModel):
    scenario_id: str

class EquipmentParamsRequest(BaseModel):
    equipment_id: str
    params: Dict[str, float] = Field(default_factory=dict)

class CommandRequest(BaseModel):
    tag: str
    action: CommandAction
    value: Optional[float | str] = None
    operator_id: str = "demo"

class StartSessionRequest(BaseModel):
    scenario_id: str = "NORMAL_OPERATION"
    operator_id: str = "demo"

lock = threading.RLock()
twin = DigitalTwin(_load_config())
twin.create_simulation()
twin.load_scenario("NORMAL_OPERATION")
twin.start()

# Unified controller catalogue (Этап 3 contract) — the HMI renders faceplates
# from /controllers and sends changes via /command.
control_system = ControlSystem()

# Active training session (Training Layer, Этап 7 groundwork).
_training_session: Optional[TrainingSession] = None

# Persistent event log for the AI error-classification service. Created
# lazily on the first /training/session call so importing this module does
# not touch the filesystem.
session_store: Optional[SessionStore] = None
session_recorder: Optional[SessionRecorder] = None

# UI-facing input overrides. The underlying engine uses these values as its feed source.
inputs: Dict[str, float] = {"flow_kg_s": 100.0, "temperature_c": 25.0, "pressure_bar": 1.01325}

# P&ID scheme owned by the API layer and pushed into the engine on changes.
_DEFAULT_SCHEME = "process_elou_avt"
scheme_store: ProcessScheme = load_scheme(Path(__file__).resolve().parent / "schemes" / f"{_DEFAULT_SCHEME}.json")
twin._engine.set_scheme(scheme_store)

# The LMS content layer (lms/content_*.py) reads the simulator singletons
# through this bridge; re-configured whenever the session layer is created.
lms_runtime.configure(twin, scheme_store, session_store, session_recorder, inputs)


def ensure_session_layer() -> None:
    """Create the training session store/recorder on demand and repoint the
    LMS content layer at the same instances (one shared recorder for /action,
    /command and the practice runner)."""
    global session_store, session_recorder
    with lock:
        if session_store is None:
            session_store = SessionStore()
        if session_recorder is None:
            session_recorder = SessionRecorder(session_store)
        lms_runtime.configure(twin, scheme_store, session_store, session_recorder, inputs)


def _build_node_telemetry(twin) -> Dict[str, Any]:
    """Per-node live telemetry derived from the last engine step."""
    outputs = twin._engine.get_last_outputs()
    streams = twin._engine.get_last_streams()
    equip = twin._engine._equipment
    state = twin.get_state()
    telemetry: Dict[str, Any] = {}

    for node in scheme_store.nodes:
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
            p["power_w"] = out.get("power", 0.0)
            p["pressure_bar"] = round(s.pressure / 1e5, 3) if s else None
            p["temperature_c"] = round(s.temperature - 273.15, 2) if s else None
            p["efficiency"] = eq.efficiency if eq else None
            p["speed_rpm"] = round(eq.speed, 1) if eq else None
        elif ntype == "valve":
            p["position"] = out.get("position", 0.0)
            p["flow_kg_s"] = out.get("flow_out", 0.0)
            p["pressure_in_bar"] = round(out["inlet_pressure"] / 1e5, 3) if out.get("inlet_pressure") else None
            p["pressure_out_bar"] = round(out["outlet_pressure"] / 1e5, 3) if out.get("outlet_pressure") else None
        elif ntype == "gate_valve":
            p["open"] = bool(eq.is_open) if eq else None
            p["flow_kg_s"] = round(out.get("flow_out", 0.0), 3)
            p["blocked"] = bool(out.get("blocked", False))
        elif ntype in ("separator", "tank"):
            p["level_m"] = out.get("level")
            p["level_setpoint_m"] = out.get("setpoint")
            p["in_flow"] = round(out.get("in_flow", 0.0), 3)
            p["out_flow"] = round(out.get("out_flow", 0.0), 3)
            p["flow_kg_s"] = round(out.get("out_flow", 0.0), 3)
            p["pressure_bar"] = round(s.pressure / 1e5, 3) if s else None
            p["temperature_c"] = round(s.temperature - 273.15, 2) if s else None
            p["volume_m3"] = out.get("volume_m3")
        elif ntype == "elou":
            p["flow_kg_s"] = round(s.mass_flow, 3) if s else 0.0
            p["power_w"] = eq.power_consumption if eq else 0.0
            p["level_m"] = state.level.get("elou")
            p["temperature_c"] = round(s.temperature - 273.15, 2) if s else None
            p["pressure_bar"] = round(s.pressure / 1e5, 3) if s else None
            p["volume_m3"] = out.get("volume_m3")
        elif ntype == "heat_exchanger":
            p["duty_w"] = out.get("duty", 0.0)
            p["t_cold_in_c"] = round(out["t_cold_in"] - 273.15, 2) if out.get("t_cold_in") else None
            p["t_cold_out_c"] = round(out["t_cold_out"] - 273.15, 2) if out.get("t_cold_out") else None
            p["t_hot_in_c"] = round(out["t_hot_in"] - 273.15, 2) if out.get("t_hot_in") else None
            p["t_hot_out_c"] = round(out["t_hot_out"] - 273.15, 2) if out.get("t_hot_out") else None
        elif ntype == "heater":
            p["duty_w"] = out.get("duty", 0.0)
            p["fuel_flow"] = eq.fuel_flow if eq else 0.0
            p["outlet_temp_c"] = round(eq.outlet_temp - 273.15, 2) if eq else None
        elif ntype == "column":
            dist = out.get("distillate")
            bott = out.get("bottoms")
            p["distillate_flow"] = dist.mass_flow if dist else 0.0
            p["bottoms_flow"] = bott.mass_flow if bott else 0.0
            p["flow_kg_s"] = (dist.mass_flow if dist else 0.0) + (bott.mass_flow if bott else 0.0)
            p["top_temp_c"] = round(dist.temperature - 273.15, 2) if dist else None
            p["bottom_temp_c"] = round(bott.temperature - 273.15, 2) if bott else None
            p["pressure_bar"] = round(dist.pressure / 1e5, 3) if dist else None
            p["level_m"] = state.level.get("column")
            p["volume_m3"] = out.get("volume_m3")
            p["converged"] = out.get("converged")
        elif ntype == "source":
            p["flow_kg_s"] = round(s.mass_flow, 3) if s else 0.0
            p["temperature_c"] = round(s.temperature - 273.15, 2) if s else None
            p["pressure_bar"] = round(s.pressure / 1e5, 3) if s else None
        elif ntype == "sink":
            for edge in scheme_store.edges:
                if edge.target == nid:
                    s_in = streams.get(f"{edge.source}:{edge.source_port}")
                    if s_in is not None:
                        break
            else:
                s_in = None
            p["flow_kg_s"] = round(s_in.mass_flow, 3) if s_in else None
            p["temperature_c"] = round(s_in.temperature - 273.15, 2) if s_in else None
            p["pressure_bar"] = round(s_in.pressure / 1e5, 3) if s_in else None

        telemetry[nid] = item

    return telemetry


def _build_history() -> Dict[str, Any]:
    """Time series of key process variables from the engine state history."""
    history = twin.get_history()
    times: list = []
    series: Dict[str, list] = {
        "feed_flow": [],
        "column_pressure_bar": [],
        "column_temp_c": [],
        "furnace_temp_c": [],
        "preheat_temp_c": [],
        "elou_level": [],
        "column_level": [],
        "valve_fv101_position": [],
    }
    for st in history:
        times.append(round(st.timestamp, 1))
        series["feed_flow"].append(round(st.feed_flow, 3))
        series["column_pressure_bar"].append(round(st.pressure.get("column", 0.0) / 1e5, 4))
        series["column_temp_c"].append(round(st.temperature.get("column", 0.0) - 273.15, 2))
        series["furnace_temp_c"].append(round(st.temperature.get("furnace_outlet", 0.0) - 273.15, 2))
        series["preheat_temp_c"].append(round(st.temperature.get("preheat_outlet", 0.0) - 273.15, 2))
        series["elou_level"].append(round(st.level.get("elou", 0.0), 3))
        series["column_level"].append(round(st.level.get("column", 0.0), 3))
        valve_pos = st.valve_positions.get("valve_FV101")
        if valve_pos is None and st.valve_positions:
            valve_pos = next(iter(st.valve_positions.values()))
        series["valve_fv101_position"].append(round(valve_pos or 0.0, 4))
    return {"times": times, "series": series}


def _serialize_state():
    with lock:
        s = twin.get_state()
        return _sanitize({
            "status": twin._status.value,
            "simulation_time": twin._simulation_time,
            "feed": {
                "flow_kg_s": inputs["flow_kg_s"],
                "flow_m3_h": inputs["flow_kg_s"] * 4.235,
                "temperature_c": inputs["temperature_c"],
                "pressure_bar": inputs["pressure_bar"],
            },
            "pressure": {k: v for k, v in s.pressure.items()},
            "temperature": {k: v for k, v in s.temperature.items()},
            "feed_flow": s.feed_flow,
            "product_flow": s.product_flow,
            "feed_flow_kg_s": s.feed_flow,
            "feed_flow_m3_h": s.feed_flow / 850.0 * 3600.0,
            "heat_duty": {k: v for k, v in s.heat_duty.items()},
            "level": s.level,
            "pump_states": s.pump_states,
            "valve_positions": s.valve_positions,
            "equipment_states": s.equipment_states,
            "equipment": _build_node_telemetry(twin),
            "active_failures": s.active_failures,
            "alarms": [a.model_dump() for a in s.alarms],
            "errors": [e.model_dump() for e in s.errors[-20:]],
            "controllers": control_system.snapshot(),
        })


def _sanitize(obj):
    """Replace non-finite floats with None so the JSON response can never fail."""
    if isinstance(obj, float):
        return None if not (obj == obj) or obj in (float("inf"), float("-inf")) else obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj

def _node_type_for(equipment_id: str) -> Optional[str]:
    """Resolve the P&ID node type of an equipment id.

    Falls back to the engine equipment class for ids that are not in the
    current scheme (e.g. demo ids used by scenario reference actions).
    """
    node = scheme_store.node(equipment_id)
    if node is not None:
        return node.type
    eq = twin._engine._equipment.get(equipment_id)
    if eq is not None:
        return {
            "Pump": "pump", "Valve": "valve", "GateValve": "gate_valve",
            "Heater": "heater",
            "ELOU": "elou", "Tank": "tank", "HeatExchanger": "heat_exchanger",
            "DistillationColumn": "column", "Separator": "separator",
        }.get(type(eq).__name__)
    return None


@app.get("/health")
def health():
    return {"ok": True, "service": "elou-avt-digital-twin"}

# ---------------------------------------------------------------------------
# Authentication & RBAC (см. auth/ — ролевая модель из Роли.txt)
# ---------------------------------------------------------------------------

@app.post("/auth/login")
def auth_login(req: LoginRequest):
    resp = get_auth_service().authenticate(req.username, req.password)
    if resp is None:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    return resp

@app.get("/auth/me", dependencies=[Depends(get_current_user)])
def auth_me(current_user=Depends(get_current_user)):
    return current_user.model_dump()

@app.get("/auth/roles", dependencies=[Depends(require_permission("manage_roles"))])
def auth_roles():
    return get_auth_service().list_roles()

@app.get("/auth/permissions", dependencies=[Depends(require_permission("manage_roles"))])
def auth_permissions():
    return get_auth_service().all_permissions()

@app.get("/auth/users", dependencies=[Depends(require_permission("manage_users"))])
def auth_users():
    return get_auth_service().list_users()

@app.post("/auth/users", dependencies=[Depends(require_permission("manage_users"))])
def auth_create_user(req: UserCreate):
    return get_auth_service().create_user(req)

@app.post("/auth/users/{user_id}/roles", dependencies=[Depends(require_permission("manage_roles"))])
def auth_assign_roles(user_id: int, req: RoleAssign):
    return get_auth_service().set_user_roles(user_id, req.role_codes)

@app.post("/auth/users/{user_id}/deactivate", dependencies=[Depends(require_permission("manage_users"))])
def auth_deactivate(user_id: int):
    get_auth_service().set_user_active(user_id, False)
    return {"ok": True}

@app.get("/state", dependencies=[Depends(require_permission("view_scheme"))])
def state():
    return _serialize_state()

@app.get("/alarms", dependencies=[Depends(require_permission("view_scheme"))])
def alarms():
    with lock:
        return [a.model_dump() for a in twin.get_alarms()]

@app.get("/events", dependencies=[Depends(require_permission("view_scheme"))])
def events():
    with lock:
        return [e.model_dump() for e in twin.get_events()]

@app.get("/score", dependencies=[Depends(require_permission("view_scheme"))])
def score():
    with lock:
        return twin.get_score_data()

@app.get("/controllers", dependencies=[Depends(require_permission("view_scheme"))])
def controllers():
    """Faceplate snapshot of every PID loop in the unified catalogue."""
    with lock:
        snap = control_system.snapshot()
        return {"count": len(snap), "controllers": snap}

@app.get("/controllers/{tag}", dependencies=[Depends(require_permission("view_scheme"))])
def controller_detail(tag: str):
    """Faceplate snapshot of one control loop."""
    with lock:
        if tag not in control_system.controllers:
            raise HTTPException(status_code=404, detail=f"Регулятор '{tag}' не найден")
        return control_system.faceplate(tag)

@app.post("/command", dependencies=[Depends(require_permission("send_commands"))])
def command(req: CommandRequest):
    """Apply one operator command to a control loop."""
    with lock:
        cmd = Command(
            tag=req.tag,
            action=req.action,
            value=req.value,
            operator_id=req.operator_id,
            timestamp=twin._simulation_time,
            source="hmi",
        )
        try:
            ctrl = control_system.apply_command(cmd)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        if session_recorder is not None and session_recorder.active:
            op_action = OperatorAction(
                timestamp=twin._simulation_time,
                operator_id=req.operator_id,
                equipment_id=req.tag,
                action_type=ActionType(req.action.value),
                old_value=getattr(ctrl, "sp", None),
                new_value=req.value if isinstance(req.value, (int, float)) else None,
                source="hmi",
            )
            session_recorder.record_action(op_action, node_type="controller")
        return {"ok": True, "controller": control_system.faceplate(ctrl.tag)}

@app.post("/training/session", dependencies=[Depends(require_permission("start_training"))])
def start_training_session(req: StartSessionRequest):
    """Open a training session for a scenario (contract; scoring in Этап 7)."""
    global _training_session
    with lock:
        if req.scenario_id not in SCENARIO_REGISTRY:
            raise HTTPException(status_code=404, detail=f"Сценарий '{req.scenario_id}' не найден")
        ensure_session_layer()
        # If a previous session is still open, close it as aborted first.
        if session_recorder.active:
            session_recorder.abort(reason="superseded by a new session")
        session_id = f"TR-{int(time.time())}"
        session_recorder.begin(
            scenario_id=req.scenario_id,
            operator_id=req.operator_id,
            scheme_version=scheme_store.id,
            reference_actions=SCENARIO_REGISTRY[req.scenario_id].reference_actions,
            sim_start=twin._simulation_time,
            session_id=session_id,
        )
        _training_session = TrainingSession(
            session_id=session_id,
            scenario_id=req.scenario_id,
            operator_id=req.operator_id,
        )
        _training_session.start(twin._simulation_time)
        return _training_session.model_dump()

@app.get("/training/session", dependencies=[Depends(get_current_user)])
def get_training_session():
    """Current training session, if any."""
    with lock:
        if _training_session is None:
            raise HTTPException(status_code=404, detail="Нет активной тренировочной сессии")
        return _training_session.model_dump()

@app.post("/training/session/finish", dependencies=[Depends(require_permission("start_training"))])
def finish_training_session():
    """Complete the current session and persist score + AI verdict."""
    global _training_session
    with lock:
        if _training_session is None or session_recorder is None or not session_recorder.active:
            raise HTTPException(status_code=404, detail="Нет активной тренировочной сессии")
        score_data = twin.get_score_data()
        score = float(score_data.get("performance_score", 0.0))
        session_recorder.end(
            sim_end=twin._simulation_time,
            score=score,
            qualification="",
            ai_verdict={"error_events": score_data.get("error_events", [])},
        )
        _training_session.finish(twin._simulation_time, score)
        return _training_session.model_dump()

@app.get("/training/sessions", dependencies=[Depends(require_permission("view_training_sessions"))])
def list_training_sessions():
    """Persisted training sessions (the AI training corpus)."""
    with lock:
        if session_store is None:
            return []
        return session_store.list_sessions()

@app.get("/training/sessions/{session_id}", dependencies=[Depends(require_permission("view_training_sessions"))])
def export_training_session(session_id: str):
    """Full persisted event log of one session (AI dataset row)."""
    with lock:
        if session_store is None:
            raise HTTPException(status_code=404, detail="Сессия не найдена")
        data = session_store.export_session(session_id)
        if data is None:
            raise HTTPException(status_code=404, detail=f"Сессия '{session_id}' не найдена")
        return data

@app.post("/input", dependencies=[Depends(require_permission("run_simulation"))])
def set_input(req: InputRequest):
    with lock:
        if req.flow_kg_s is not None:
            inputs["flow_kg_s"] = req.flow_kg_s
        if req.temperature_c is not None:
            inputs["temperature_c"] = req.temperature_c
        if req.pressure_bar is not None:
            inputs["pressure_bar"] = req.pressure_bar
        twin._engine.set_feed_override(inputs)
        # Keep the src_feed node params in sync so per-node editing and the
        # global feed override always agree.
        src = scheme_store.node("src_feed")
        if src is not None:
            for key, val in (("flow_kg_s", req.flow_kg_s),
                             ("temperature_c", req.temperature_c),
                             ("pressure_bar", req.pressure_bar)):
                if val is not None:
                    src.params[key] = val
        return _serialize_state()

@app.post("/action", dependencies=[Depends(require_permission("send_commands"))])
def action(req: ActionRequest):
    with lock:
        old = None
        action = OperatorAction(
            timestamp=twin._simulation_time,
            operator_id=req.operator_id,
            equipment_id=req.equipment_id,
            action_type=req.action_type,
            old_value=old,
            new_value=req.value,
            source="operator_panel",
        )
        if session_recorder is not None and session_recorder.active:
            action_id = session_recorder.record_action(
                action, node_type=_node_type_for(req.equipment_id))
            session_recorder.record_snapshot(
                twin.get_state(), reason="action", action_id=action_id)
        twin.apply_operator_action(action)
        # Advance immediately so the UI shows the result without waiting for the loop.
        if twin._status.value != "RUNNING":
            twin.start()
        _safe_step()
        return _serialize_state()

@app.get("/equipment/spec/{node_id}", dependencies=[Depends(require_permission("view_scheme"))])
def equipment_spec(node_id: str):
    """Editable physical-property spec + current values for one node."""
    with lock:
        node = scheme_store.node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
        if node.type in NON_EDITABLE_TYPES or not spec_for(node.type):
            return {"node_id": node_id, "node_type": node.type, "editable": False, "params": []}
        eq = twin._engine._equipment.get(node_id)
        return {
            "node_id": node_id,
            "node_type": node.type,
            "editable": True,
            "params": editor_spec(node.type, eq, node),
        }

@app.post("/equipment/params", dependencies=[Depends(require_permission("manage_twin"))])
def update_equipment_params(req: EquipmentParamsRequest):
    """Apply physical-property corrections to a node and persist them."""
    with lock:
        node = scheme_store.node(req.equipment_id)
        if node is None:
            raise HTTPException(status_code=404, detail=f"Node '{req.equipment_id}' not found")
        if node.type in NON_EDITABLE_TYPES:
            raise HTTPException(status_code=422, detail=f"Тип '{node.type}' не имеет настраиваемых свойств")
        eq = twin._engine._equipment.get(req.equipment_id)
        updates: Dict[str, float] = {}
        for key, display_val in req.params.items():
            stored = coerce(key, float(display_val), node.type)
            if stored is None:
                raise HTTPException(status_code=422, detail=f"Параметр '{key}' не настраивается для типа '{node.type}'")
            updates[key] = stored
        if eq is not None:
            eq.update_params(updates)
        for key, val in updates.items():
            node.params[key] = val
        if req.equipment_id == "src_feed":
            for key, val in updates.items():
                if key in ("flow_kg_s", "temperature_c", "pressure_bar"):
                    inputs[key] = val
                    twin._engine.set_feed_override({key: val})
        _save_current_scheme()
        _safe_step()
        return _serialize_state()

@app.post("/scenario/start", dependencies=[Depends(require_permission("run_simulation"))])
def start_scenario(req: ScenarioRequest):
    with lock:
        try:
            twin.create_simulation()
            twin._engine.set_scheme(scheme_store)
            twin.load_scenario(req.scenario_id)
            twin._engine.set_feed_override(inputs)
            twin.start()
            for _ in range(30):
                _safe_step()
            return _serialize_state()
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

@app.post("/scenario/reset", dependencies=[Depends(require_permission("run_simulation"))])
def reset_scenario():
    with lock:
        twin.reset()
        twin._engine.set_feed_override(inputs)
        return _serialize_state()

@app.post("/scenario/step", dependencies=[Depends(require_permission("run_simulation"))])
def step():
    with lock:
        if twin._status.value not in ("RUNNING", "IDLE"):
            twin.start()
        twin._engine.set_feed_override(inputs)
        _safe_step()
        return _serialize_state()

@app.post("/failure/{equipment_id}", dependencies=[Depends(require_permission("manage_twin"))])
def failure(equipment_id: str):
    with lock:
        twin.inject_failure(equipment_id, "MECHANICAL_FAILURE")
        # Advance one step so the failure's effect is visible immediately.
        if twin._status.value != "RUNNING":
            twin.start()
        _safe_step()
        return _serialize_state()


@app.get("/history", dependencies=[Depends(require_permission("view_scheme"))])
def history(limit: int = 600):
    """Return recent time series for trend charts."""
    data = _build_history()
    if limit > 0:
        data["times"] = data["times"][-limit:]
        for k in data["series"]:
            data["series"][k] = data["series"][k][-limit:]
    return data

@app.get("/scheme", dependencies=[Depends(require_permission("view_scheme"))])
def get_scheme():
    """Return the current P&ID scheme graph (nodes + edges)."""
    with lock:
        return scheme_store.model_dump(mode="json")

SCHEME_DIR = Path(__file__).resolve().parent / "schemes"


def _save_current_scheme() -> None:
    """Persist the current scheme to its own JSON file (not the default)."""
    save_scheme(scheme_store, SCHEME_DIR / f"{scheme_store.id}.json")


@app.get("/schemes", dependencies=[Depends(require_permission("view_scheme"))])
def list_schemes():
    """List available P&ID scheme files (without the .json extension)."""
    with lock:
        return {"current": scheme_store.id,
                "schemes": [p.stem for p in sorted(SCHEME_DIR.glob("*.json"))]}


class SchemeLoadRequest(BaseModel):
    name: str


def _reconfigure(new_scheme: ProcessScheme) -> None:
    """Point the engine at a scheme, reload normal operation and warm it up
    so the returned state reflects the new P&ID layout immediately."""
    global scheme_store
    scheme_store = new_scheme
    twin.create_simulation()
    twin._engine.set_scheme(new_scheme)
    twin._engine.set_feed_override(inputs)
    twin.load_scenario("NORMAL_OPERATION")
    twin.start()
    for _ in range(5):
        _safe_step()


@app.post("/scheme/load", dependencies=[Depends(require_permission("manage_scheme"))])
def load_scheme_endpoint(req: SchemeLoadRequest):
    """Load a P&ID scheme by name and reconfigure the engine on it."""
    with lock:
        path = SCHEME_DIR / f"{req.name}.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Scheme '{req.name}' not found")
        try:
            new_scheme = load_scheme(path)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid scheme: {e}")
        _reconfigure(new_scheme)
        return _serialize_state()

class SchemeCreateRequest(BaseModel):
    name: str

@app.post("/scheme/new", dependencies=[Depends(require_permission("manage_scheme"))])
def create_scheme_endpoint(req: SchemeCreateRequest):
    """Create an empty P&ID scheme by name and switch the engine to it."""
    with lock:
        name = req.name.strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise HTTPException(
                status_code=422,
                detail="Invalid scheme name (use latin letters, digits, '_' or '-')",
            )
        path = SCHEME_DIR / f"{name}.json"
        if path.exists():
            raise HTTPException(status_code=409, detail=f"Scheme '{name}' already exists")
        new_scheme = ProcessScheme(id=name, name=f"Схема «{name}»", nodes=[], edges=[])
        save_scheme(new_scheme, path)
        _reconfigure(new_scheme)
        return _serialize_state()

class SchemeRequest(BaseModel):
    nodes: list = []
    edges: list = []

@app.post("/scheme", dependencies=[Depends(require_permission("manage_scheme"))])
def post_scheme(req: SchemeRequest):
    """Replace the P&ID scheme, persist it and reconfigure the engine."""
    with lock:
        global scheme_store
        try:
            new_scheme = ProcessScheme(nodes=[SchemeNode(**n) for n in req.nodes],
                                       edges=[SchemeEdge(**e) for e in req.edges])
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid scheme: {e}")
        scheme_store = new_scheme
        _save_current_scheme()
        _reconfigure(new_scheme)
        return _serialize_state()

@app.get("/scheme/templates", dependencies=[Depends(require_permission("view_scheme"))])
def scheme_templates():
    """Return the palette of object types available to the scheme editor."""
    return {
        "types": [
            {"type": "source", "label": "Источник сырья", "category": "boundary"},
            {"type": "sink", "label": "Продукт / отбор", "category": "boundary"},
            {"type": "pump", "label": "Насос", "category": "equipment"},
            {"type": "valve", "label": "Регулирующий клапан", "category": "equipment"},
            {"type": "gate_valve", "label": "Задвижка", "category": "equipment"},
            {"type": "elou", "label": "ЭЛОУ (электродегидратор)", "category": "equipment"},
            {"type": "heat_exchanger", "label": "Теплообменник", "category": "equipment"},
            {"type": "heater", "label": "Печь", "category": "equipment"},
            {"type": "column", "label": "Колонна ректификации", "category": "equipment"},
            {"type": "separator", "label": "Сепаратор", "category": "equipment"},
        ]
    }

@app.websocket("/ws/simulation")
async def websocket_simulation(websocket: WebSocket):
    principal = authenticate_websocket(websocket.query_params.get("token", ""))
    if principal is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    try:
        while True:
            with lock:
                payload = _serialize_state()
            await websocket.send_json(payload)
            await __import__("asyncio").sleep(1.0)
    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception("WebSocket connection error")
        try:
            await websocket.close()
        except Exception:
            pass


def _sync_recorder(action_id: Optional[int] = None) -> None:
    """Persist the latest step context into the active training session."""
    if session_recorder is None or not session_recorder.active:
        return
    session_recorder.record_snapshot(twin.get_state(), reason="step")
    session_recorder.sync_alarms(twin._engine._alarm_system.get_alarm_history())
    session_recorder.sync_errors(twin._engine.get_events(), action_id=action_id)


def _safe_step() -> None:
    """Step the simulation, logging any exception instead of swallowing it."""
    try:
        twin._engine.set_feed_override(inputs)
        twin.step(1.0)
        _sync_recorder()
    except Exception:
        logger.error("Simulation step failed:\n%s", traceback.format_exc())


def simulation_loop():
    while True:
        time.sleep(1.0)
        with lock:
            if twin._status.value == "RUNNING":
                _safe_step()

threading.Thread(target=simulation_loop, daemon=True).start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=False)
