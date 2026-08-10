"""
engine.py
=========
SimulationEngine — the core integration loop for the ELOU-AVT digital twin.

Responsibilities:
  - Advance simulation state by dt seconds
  - Apply operator actions to equipment
  - Collect equipment outputs into SimulationState
  - Evaluate alarms
  - Track operator errors
  - Maintain state history
"""

import copy
import logging
import math
from typing import Callable, Dict, List, Optional, Any, Tuple

from models.base import (
    SimulationState,
    SimulationConfig,
    OperatorAction,
    Alarm,
    ErrorEvent,
    Severity,
)
from models.scenario import Scenario, ScenarioEvent
from equipment import (
    Pump, Valve, AngleValve, GateValve, Heater, HeatExchanger, DistillationColumn, ELOU, Tank,
    Mixer, Splitter, SeparatorS1K,
)
from equipment.columns import AtmosphericColumnK1, column_class_for
from calculation_core.hydraulics.pressure_drop import calculate_pipe_pressure_drop
from scheme import ProcessScheme, SchemeNode, load_scheme
from safety.alarm_system import AlarmSystem
from events.error_tracker import ErrorTracker, ExpectedAction

logger = logging.getLogger("elou_avt.engine")

# Node types that behave as adjustable control valves (position throttling).
_CONTROL_VALVE_TYPES = ("valve", "angle_valve")

# Equipment that legitimately receives several incoming streams on different
# ports (or as a boundary) and must NOT be treated as an implicit mixer:
# multi-feed columns, multi-pass furnaces, exchangers, inventory vessels and
# the explicit mixer/splitter/sink/source primitives.
_MULTI_IN_BOUNDARY_TYPES = frozenset({
    "elou", "heat_exchanger", "heater", "column", "separator",
    "tank", "separator_s1k", "mixer", "splitter", "sink",
})


class SimulationEngine:
    """
    Main simulation integration loop.

    Contains all equipment instances and advances the process model
    step-by-step.

    Equipment layout (DEMO/MVP):
        pump_P101        — main feed pump
        pump_P102        — standby feed pump
        valve_FV101      — feed flow control valve
        valve_PV201      — column pressure control valve
        elou_E001        — desalting unit
        hx_E101          — crude preheat exchanger
        furnace_F101     — atmospheric furnace
        column_C101      — atmospheric distillation column
    """

    def __init__(self, config: SimulationConfig):
        self.config = config
        self._time = 0.0
        self._history: List[SimulationState] = []
        self._alarm_system = AlarmSystem()
        self._error_tracker = ErrorTracker()
        self._active_failures: List[str] = []

        # Water-hammer surge detection (ТЗ section 36): previous valve
        # positions and the per-valve surge alerts already raised, so a fast
        # closure is measured against the flow it actually cut.
        self._prev_valve_positions: Dict[str, float] = {}
        self._last_surge_alerts: Dict[str, float] = {}
        self._surge_close_threshold = 0.5

        self._hyd_tau = float(getattr(config, "hydraulics_tau", 8.0))
        self._hyd_state: Dict[str, Dict[str, float]] = {}
        self._vessel_state: Dict[str, Dict[str, Any]] = {}
        self._vessel_q: Dict[str, Dict[str, float]] = {}
        self._vessel_q_in: Dict[str, float] = {}
        self._vessel_q_out: Dict[str, float] = {}
        self._vessel_active: set = set()

        # Build equipment
        self._equipment: Dict[str, Any] = self._build_equipment()

        # Initial state
        self._state = self._build_initial_state()
        self._feed_override = {"flow_kg_s": 100.0, "temperature_c": 25.0, "pressure_bar": 1.01325}

        # Scheme-driven topology: the engine walks the P&ID graph instead of
        # relying on a hardcoded equipment sequence.
        self._scheme: ProcessScheme = load_scheme()
        self._node_map: Dict[str, SchemeNode] = {}
        self._edges = []
        self._topo_order: List[str] = []
        # Recycle loops (e.g. column -> furnace -> column) cannot be ordered by
        # Kahn's algorithm.  Cycle nodes are torn: the broken edges are listed
        # here and fed from the previous step's streams each step so the loop
        # converges across steps.
        self._tear_edges: List[str] = []
        self._last_outputs: Dict[str, Any] = {}
        self._last_streams: Dict[str, Any] = {}
        self._alarm_setpoints: Dict[str, Any] = {}
        self._alarm_setpoint_overrides: Dict[str, Any] = {}
        self._measured_params: Dict[str, int] = {}
        self._has_scheme_limits = False
        self._extend_equipment_from_scheme(self._scheme)
        self._rebuild_topology(self._scheme)
        self._configure_alarm_setpoints(self._scheme)

    # ------------------------------------------------------------------
    # Equipment factory
    # ------------------------------------------------------------------

    def _build_equipment(self) -> Dict[str, Any]:
        ep = self.config.equipment_parameters
        return {
            "pump_P101": Pump("pump_P101", ep.get("pump_P101", {})),
            "pump_P102": Pump("pump_P102", ep.get("pump_P102", {})),
            "valve_FV101": Valve("valve_FV101", ep.get("valve_FV101", {})),
            "valve_PV201": Valve("valve_PV201", ep.get("valve_PV201", {})),
            "elou_E001": ELOU("elou_E001", ep.get("elou_E001", {})),
            "hx_E101": HeatExchanger("hx_E101", ep.get("hx_E101", {})),
            "furnace_F101": Heater("furnace_F101", ep.get("furnace_F101", {})),
            "column_C101": AtmosphericColumnK1("column_C101", ep.get("column_C101", {})),
        }

    def _build_initial_state(self) -> SimulationState:
        from calculation_core.thermodynamics.pr_eos import PengRobinsonThermodynamics
        from calculation_core.thermodynamics.fractions import FRACTION_COMPONENTS
        self.thermo = PengRobinsonThermodynamics(FRACTION_COMPONENTS)
        
        pump_states = {"pump_P101": False, "pump_P102": False}
        valve_positions = {"valve_FV101": 0.0, "valve_PV201": 0.5}
        levels: Dict[str, float] = {"elou": 2.0, "column": 2.0}
        for nid, node in getattr(self, "_node_map", {}).items():
            if node.type == "pump":
                pump_states.setdefault(nid, False)
            elif node.type in _CONTROL_VALVE_TYPES:
                valve_positions.setdefault(nid, 0.0)
            elif node.type in ("column", "elou", "separator", "tank", "separator_s1k"):
                levels.setdefault(nid, float(node.params.get("initial_level", 2.0)))

        return SimulationState(
            timestamp=0.0,
            pressure={"feed_line": 101325.0, "column": 101325.0},
            temperature={"feed": 298.15, "column": 298.15},
            feed_flow=0.0,
            product_flow=0.0,
            level=levels,
            heat_duty={"furnace": 0.0, "hx_E101": 0.0},
            pump_states=pump_states,
            valve_positions=valve_positions,
            equipment_states={},
            alarms=[],
            active_failures=[],
            errors=[],
        )

    # ------------------------------------------------------------------
    # Core step
    # ------------------------------------------------------------------

    def step(
        self,
        state: SimulationState,
        operator_actions: Optional[List[OperatorAction]] = None,
        dt: Optional[float] = None,
    ) -> SimulationState:
        """
        Advance simulation by dt seconds.

        Parameters:
            state            : current SimulationState
            operator_actions : list of OperatorAction to apply this step
            dt               : time step [s], defaults to config.dt

        Returns:
            new SimulationState
        """
        dt = dt if dt is not None else self.config.dt
        self._time += dt

        # 1. Apply operator actions
        new_errors: List[ErrorEvent] = []
        if operator_actions:
            for action in operator_actions:
                logger.info("Operator action: %s on %s = %s",
                            action.action_type, action.equipment_id, action.new_value)
                error = self._apply_action(action, state)
                if error:
                    new_errors.append(error)

        # 2. Check missed actions
        missed = self._error_tracker.check_missed_actions(self._time)
        new_errors.extend(missed)

        # 3. Step all equipment
        eq_outputs = self._step_equipment(state, dt)
        # 3b. Water-hammer check: a valve that closes fast enough cuts the flow
        # abruptly -> Joukowsky surge against the pipe MAOP (ТЗ section 36).
        new_errors.extend(self._check_water_hammer(eq_outputs))

        # 4. Build new state
        new_state = self._build_state(state, eq_outputs, dt)
        new_state.timestamp = self._time
        new_state.errors = list(state.errors) + new_errors
        new_state.active_failures = list(self._active_failures)

        # 5. Evaluate alarms
        alarm_values: Dict[str, float] = {}
        if not self._has_scheme_limits:
            # Demo/deprecated aggregates, used when a scheme carries no limits
            # but still has the matching equipment. Skipped for empty/minimal
            # schemes so demo alarms do not hang on a bare canvas.
            node_types = {nd.type for nd in self._node_map.values()}
            if "elou" in node_types or "pump" in node_types:
                alarm_values["feed_flow"] = new_state.feed_flow
            if "column" in node_types:
                alarm_values["column_pressure"] = new_state.pressure.get("column", 0.0)
                alarm_values["column_temperature"] = new_state.temperature.get("column", 0.0)
            if "heater" in node_types:
                alarm_values["furnace_temperature"] = new_state.temperature.get("furnace_outlet", 0.0)
        self._fill_alarm_values(alarm_values, eq_outputs, new_state)
        new_alarms = self._alarm_system.evaluate(self._time, alarm_values)
        self._bind_alarm_nodes(new_alarms)
        new_state.alarms = self._alarm_system.get_active_alarms()

        # 6. Save history (bounded to avoid unbounded memory growth)
        self._history.append(copy.deepcopy(new_state))
        limit = max(1, self.config.history_limit)
        if len(self._history) > limit:
            del self._history[: len(self._history) - limit]
        self._state = new_state

        return new_state

    # ------------------------------------------------------------------
    # Equipment stepping
    # ------------------------------------------------------------------

    def set_feed_override(self, values: Dict[str, float]) -> None:
        """Set operator-adjustable feed boundary conditions used by the digital twin."""
        self._feed_override.update({k: float(v) for k, v in values.items() if v is not None})

    def _step_equipment(self, state: SimulationState, dt: float) -> Dict[str, Any]:
        """Step all equipment by walking the scheme graph.

        Streams propagate along edges from sources through equipment to sinks.
        A node's output streams are stored under '<node_id>:<port>' keys so that
        multi-output devices (heat exchanger, column) can route correctly.
        """
        from models.stream import Stream
        outputs: Dict[str, Any] = {}
        streams: Dict[str, Stream] = {}
        # Tear edges (cycle back-edges) have no upstream value ready this step:
        # reuse the previous step's stream so recycle loops converge across
        # steps instead of being dropped from the calculation entirely.
        if self._tear_edges and self._last_streams:
            for key in self._tear_edges:
                prev = self._last_streams.get(key)
                if prev is not None:
                    streams[key] = prev
        # Downstream valves limit the flow of their exclusive upstream line
        # (previous step's valve throughput). The source itself is a fixed
        # flow boundary and is never clamped; restrictions make the equipment
        # upstream hold back flow (levels/pressures respond instead).
        flow_limits = self._compute_flow_limits(self._last_outputs)
        hyd = self._solve_line_hydraulics()
        if self._hyd_tau > 0.0 and hyd:
            factor = 1.0 - math.exp(-dt / self._hyd_tau)
            for nid, h in hyd.items():
                prev = self._hyd_state.get(nid)
                if prev is None:
                    self._hyd_state[nid] = {"flow": h["flow"], "p_in": h["p_in"], "p_out": h["p_out"]}
                    continue
                h["flow"] = prev["flow"] + (h["flow"] - prev["flow"]) * factor
                h["p_in"] = prev["p_in"] + (h["p_in"] - prev["p_in"]) * factor
                h["p_out"] = prev["p_out"] + (h["p_out"] - prev["p_out"]) * factor
                self._hyd_state[nid] = {"flow": h["flow"], "p_in": h["p_in"], "p_out": h["p_out"]}
        self._integrate_levels(dt)

        for nid in self._topo_order:
            node = self._node_map.get(nid)
            if node is None:
                continue
            ntype = node.type

            if ntype == "source":
                # A source supplies its configured flow, but the flow that
                # actually leaves the node is limited by what its line can
                # carry: the tightest downstream valve opening and the pump's
                # capacity at its current rotation speed.  This makes the feed
                # flow follow the FV-1 control valve instead of being a fixed
                # manual boundary condition.
                src = self._make_source_stream(node)
                h = hyd.get(nid)
                if h is not None:
                    src = src.copy_with(mass_flow=max(0.0, h["flow"]), pressure=h["p_out"])
                else:
                    cap = flow_limits.get(nid)
                    if cap is not None and src.mass_flow > cap:
                        src = src.copy_with(mass_flow=max(0.0, cap))
                streams[f"{nid}:out"] = src
                continue
            if ntype == "sink":
                continue

            # Collect incoming streams grouped by target port. When one source
            # port feeds several downstream nodes (a fork), split the flow
            # equally among the consumers instead of copying it into each
            # branch (which would duplicate the flow).
            consumers: Dict[str, int] = {}
            for edge in self._edges:
                key = f"{edge.source}:{edge.source_port}"
                if key in streams:
                    consumers[key] = consumers.get(key, 0) + 1
            incoming: Dict[str, List[Stream]] = {}
            for edge in self._edges:
                if edge.target != nid:
                    continue
                key = f"{edge.source}:{edge.source_port}"
                if key in streams:
                    base = streams[key]
                    n_cons = consumers.get(key, 1)
                    if n_cons > 1:
                        branch_flow = base.mass_flow / n_cons
                        # Use the hydraulic branch flow when available so a fork
                        # splits according to each branch's resistance instead
                        # of dividing the incoming stream evenly.
                        h_br = hyd.get(edge.target) or hyd.get(
                            f"{edge.target}:{edge.target_port or 'in'}"
                        )
                        if h_br is not None:
                            branch_flow = max(0.0, h_br["flow"])
                        branch = base.copy_with(
                            name=f"{base.name}:{edge.target}",
                            mass_flow=branch_flow,
                        )
                    else:
                        branch = base
                    incoming.setdefault(edge.target_port or "in", []).append(branch)
            if not incoming:
                continue  # isolated node or upstream data not ready

            eq = self._equipment.get(nid)
            out: Dict[str, Any] = {}
            if eq is None:
                # Unknown equipment types act as pass-through: merge EVERY
                # incoming stream regardless of its port name (a node whose
                # ports are not literally 'in'/'cold_in' must still pass its
                # flow through, never silently drop it).
                inlet = self._merge_streams(
                    [s for lst in incoming.values() for s in lst]
                )
                if inlet is not None:
                    out = {"outlet_stream": inlet}
            elif nid in self._junction_nodes:
                # Implicit mixer: the node collects EVERY incoming stream (not
                # only the port 'in') and passes the well-mixed stream through
                # at the junction back-pressure.  Mass and energy are conserved
                # by _merge_streams (Σṁ, mass-weighted composition/enthalpy);
                # the outlet flow is the sum of the feeds, so the junction never
                # creates or destroys mass.  Feeding line flows were solved by
                # the hydraulic network down to this junction pressure.
                inlets = [s for lst in incoming.values() for s in lst]
                if not inlets:
                    continue
                inlet = self._merge_streams(inlets)
                if inlet is None:
                    continue
                bp = self._mixer_back_pressure(nid, hyd)
                if bp is not None:
                    inlet = inlet.copy_with(pressure=float(bp))
                out = {"outlet_stream": inlet, "flow_out": inlet.mass_flow}
            elif ntype == "pump":
                inlet = self._merge_streams(incoming.get("in"))
                if inlet is None:
                    continue
                out = eq.step(dt, inlet_stream=inlet, delta_p=node.params.get("delta_p", 5e5))
            elif ntype in _CONTROL_VALVE_TYPES:
                inlet = self._merge_streams(incoming.get("in"))
                if inlet is None:
                    continue
                out = eq.step(dt, inlet_stream=inlet)
            elif ntype == "gate_valve":
                inlet = self._merge_streams(incoming.get("in"))
                if inlet is None:
                    continue
                out = eq.step(dt, inlet_stream=inlet)
            elif ntype == "elou":
                inlet = self._merge_streams(incoming.get("in"))
                if inlet is None:
                    continue
                out = eq.step(dt, inlet_stream=inlet, thermo=self.thermo)
            elif ntype == "heat_exchanger":
                hot = self._merge_streams(incoming.get("hot_in"))
                cold = self._merge_streams(incoming.get("cold_in"))
                if hot is None or cold is None:
                    continue
                out = eq.step(dt, hot_in=hot, cold_in=cold, thermo=self.thermo)
            elif ntype == "heater":
                inlets = {
                    port: self._merge_streams(incoming.get(port))
                    for port in self._FURNACE_PORT_PAIRS
                    if incoming.get(port)
                }
                if not inlets:
                    continue
                out = eq.step(dt, thermo=self.thermo, **inlets)
            elif ntype == "column":
                feed = self._merge_streams(
                    [s for lst in incoming.values() for s in lst]
                )
                if feed is None:
                    continue
                out = eq.step(dt, feed_stream=feed, thermo=self.thermo)
            elif ntype in ("separator", "tank"):
                inlet = self._merge_streams(incoming.get("in"))
                if inlet is None:
                    continue
                vs = self._vessel_state.get(nid)
                out = eq.step(
                    dt, inlet_stream=inlet, max_out=flow_limits.get(nid),
                    vessel_pressure=vs["p_out"] if vs else None,
                )
            elif ntype == "mixer":
                inlets = [s for lst in incoming.values() for s in lst]
                if not inlets:
                    continue
                out = eq.step(
                    dt, inlet_streams=inlets, thermo=self.thermo,
                    back_pressure=self._mixer_back_pressure(nid, hyd),
                )
            elif ntype == "splitter":
                # Разъединитель: один вход, n выходов.  Каждая ветвь решена
                # линиевым солвером как отдельное ответвление с общей
                # (junction) давлением на выходе узла, так что распределение
                # масс между выходами берётся из гидравлики downstream.
                inlet = self._merge_streams(incoming.get("in"))
                if inlet is None:
                    continue
                h_spl = hyd.get(nid)
                branch_flows = None
                if h_spl is not None:
                    flows: Dict[str, float] = {}
                    for edge in self._edges:
                        if edge.source != nid:
                            continue
                        bh = hyd.get(edge.target)
                        if bh is not None:
                            flows[edge.source_port] = max(0.0, bh["flow"])
                    if flows:
                        branch_flows = flows
                out = eq.step(
                    dt, inlet_stream=inlet, thermo=self.thermo,
                    branch_flows=branch_flows,
                    junction_pressure=h_spl["p_out"] if h_spl is not None else None,
                )
                for i, s in enumerate(out.get("outlet_streams") or []):
                    out[f"out{i}"] = s
            elif ntype == "separator_s1k":
                inlets = [s for lst in incoming.values() for s in lst]
                if not inlets:
                    continue
                vs = self._vessel_state.get(nid)
                out = eq.step(
                    dt, inlet_streams=inlets, thermo=self.thermo,
                    max_out=flow_limits.get(nid),
                    vessel_pressure=vs["p_out"] if vs else None,
                )
            else:
                inlet = self._merge_streams(incoming.get("in"))
                if inlet is not None:
                    out = {"outlet_stream": inlet}

            if not out:
                continue
            # Serial-line hydraulics override: equipment in a line takes the
            # physically consistent flow and pressure from the line solver
            # (one shared mass flow, pressure dropping along the chain).
            h = hyd.get(nid)
            if h is not None and ntype not in ("mixer", "splitter") and nid not in self._junction_nodes:
                if ntype == "elou":
                    # An ELOU splits the feed into desalted oil (right port) and
                    # brine (bottom port).  Both streams leave the vessel; the
                    # model already divides the feed mass between them, so the
                    # line solver only anchors their common outlet pressure
                    # (static head + flow back-pressure).
                    brine = out.get("brine_stream")
                    if brine is not None:
                        out["brine_stream"] = brine.copy_with(pressure=h["p_out"])
                    os_ = out.get("outlet_stream")
                    if os_ is not None:
                        out["outlet_stream"] = os_.copy_with(pressure=h["p_out"])
                else:
                    os_ = out.get("outlet_stream")
                    if os_ is not None:
                        out["outlet_stream"] = os_.copy_with(
                            mass_flow=max(0.0, h["flow"]), pressure=h["p_out"]
                        )
                out["flow_out"] = h["flow"]
                if ntype in _CONTROL_VALVE_TYPES:
                    out["inlet_pressure"] = h["p_in"]
                    out["outlet_pressure"] = h["p_out"]
                    out["dp"] = max(0.0, h["p_in"] - h["p_out"])
                    out["blocked"] = h["flow"] <= 1e-9
                elif ntype == "pump":
                    inlet = self._merge_streams(incoming.get("in"))
                    dp_hyd = max(0.0, h["p_out"] - (inlet.pressure if inlet else 0.0))
                    if inlet is not None:
                        out["power"] = (h["flow"] / max(inlet.density, 1e-6)) * dp_hyd / max(eq.efficiency, 1e-6)
                        eq.power = out["power"]
            if ntype == "elou":
                # The ELOU is a dehydrator stage: its oil outlet is a physical
                # drain driven by the static head of the liquid level through
                # the outlet-line resistance, clamped by the tightest valve on
                # the oil line -- like a buffer tank, NOT a feed-following
                # split.  The outflow therefore does not track the feed:
                #   - cutting the feed drains the level down (Q_out > Q_in);
                #   - throttling the outlet valve lets the level build up
                #     (Q_in > Q_out);
                #   - opening the outlet valve draws the level down again.
                # The level is a consequence of the mass balance and can be
                # moved in both directions (asymmetric behaviour removed).
                s_out = out.get("outlet_stream")
                b_out = out.get("brine_stream")
                brine = b_out.mass_flow if b_out is not None else 0.0
                vs = self._vessel_state.get(nid)
                cap = self._outlet_line_capacity(nid, "oil_out")
                if h is not None and h["flow"] > 0.0:
                    # The oil drain line is solved hydraulically (a single-outlet
                    # ELOU builds a drain tree): the real flow through the outlet
                    # valve comes from the level static head across the drain and
                    # valve resistances, so the line solver's answer is used.  A
                    # multi-outlet ELOU builds no drain tree (h is None) and keeps
                    # the level-drain fallback below.
                    oil_q = max(0.0, h["flow"])
                    if cap is not None:
                        oil_q = max(0.0, min(oil_q, cap))
                elif vs is not None:
                    rho = s_out.density if s_out is not None and s_out.density > 0 else 850.0
                    if vs["level"] > 1e-9:
                        head = max(rho * 9.81 * vs["level"], 0.0)
                        oil_q = math.sqrt(head / max(vs.get("k_drain", 1e-9), 1e-12))
                    else:
                        oil_q = 0.0
                    if cap is not None:
                        oil_q = max(0.0, min(oil_q, cap))
                else:
                    model_out = s_out.mass_flow if s_out is not None else 0.0
                    oil_q = max(0.0, min(model_out, cap)) if cap is not None else model_out
                if s_out is not None:
                    out["outlet_stream"] = s_out.copy_with(mass_flow=oil_q)
                self._vessel_q_out[nid] = oil_q + brine
            if ntype == "column":
                # The MESH bottoms product is the inflow to the bottoms sump:
                # the level integrates (bottoms_in - bottoms_drawn), so a bigger
                # feed builds more sump inflow and a wider bottoms valve draws
                # the level down.
                b = out.get("bottoms")
                if b is not None:
                    self._vessel_q_in[nid] = b.mass_flow
            if ntype == "heat_exchanger":
                # Each channel (hot / cold) is its own hydraulic line: apply
                # the per-channel solved flow and outlet pressure to the
                # corresponding outlet stream.  The exchanger itself never
                # changes the flow of either pass.
                for ch_port, out_port, label in (
                    ("hot_in", "hot_out", "hot"),
                    ("cold_in", "cold_out", "cold"),
                ):
                    hch = hyd.get(f"{nid}:{ch_port}")
                    if hch is None or out.get(out_port) is None:
                        continue
                    out[out_port] = out[out_port].copy_with(
                        mass_flow=max(0.0, hch["flow"]), pressure=hch["p_out"]
                    )
                    out[f"flow_{label}"] = hch["flow"]
                    out[f"p_{label}_in"] = hch["p_in"]
                    out[f"p_{label}_out"] = hch["p_out"]
                    out[f"dp_{label}"] = max(0.0, hch["p_in"] - hch["p_out"])
            elif ntype == "heater":
                # A multi-pass furnace is several independent hydraulic lines
                # (one per section inlet -> outlet pair), exactly like an
                # exchanger channel.  The furnace never changes the flow of a
                # pass; it only raises the temperature.
                for in_port, out_port in self._FURNACE_PORT_PAIRS.items():
                    hch = hyd.get(f"{nid}:{in_port}")
                    if hch is None or out.get(out_port) is None:
                        continue
                    out[out_port] = out[out_port].copy_with(
                        mass_flow=max(0.0, hch["flow"]), pressure=hch["p_out"]
                    )
                main_out = out.get("out")
                if main_out is not None:
                    out["flow_out"] = main_out.mass_flow
            elif ntype == "column":
                # The column is a pass-through node in the line solver: its
                # branches share the junction pressure, so the solved outlet
                # pressure anchors both the distillate and the bottoms stream.
                hcol = hyd.get(nid)
                if hcol is not None:
                    for port in ("distillate", "side_draw", "bottoms"):
                        if out.get(port) is not None:
                            out[port] = out[port].copy_with(pressure=hcol["p_out"])
            # Restriction clamp: a downstream valve caps the flow this node may
            # deliver (dead-headed line). Applied AFTER step so level-bearing
            # equipment still reflects the hold-back through max_out above;
            # pass-through nodes (pump, heater, ...) simply carry no more than
            # the tightest downstream valve.
            cap = flow_limits.get(nid)
            if cap is not None and nid not in hyd:
                os_ = out.get("outlet_stream")
                if os_ is not None and os_.mass_flow > cap:
                    out["outlet_stream"] = os_.copy_with(mass_flow=max(0.0, cap))
            outputs[nid] = out

            # A sink is a strict pressure boundary: a stream delivered to it
            # must carry at least the sink's own pressure, or the sink could
            # not physically accept it (e.g. a bottoms valve that drops the
            # pressure below the receiving tank).  Anchor any outgoing stream
            # to the sink pressure so the boundary is never violated.
            for edge in self._edges:
                if edge.source != nid:
                    continue
                t_node = self._node_map.get(edge.target)
                if t_node is None or t_node.type != "sink":
                    continue
                s = out.get(edge.source_port)
                if s is None or not hasattr(s, "copy_with"):
                    s = out.get("outlet_stream")
                if s is None or not hasattr(s, "copy_with"):
                    continue
                sink_p = float(t_node.params.get("pressure_bar", 1.01325)) * 1e5
                if s.pressure < sink_p:
                    s = s.copy_with(pressure=sink_p)
                    if edge.source_port in out and hasattr(out[edge.source_port], "copy_with"):
                        out[edge.source_port] = s
                    os_ = out.get("outlet_stream")
                    if os_ is not None and hasattr(os_, "copy_with"):
                        out["outlet_stream"] = s
                    if "outlet_pressure" in out:
                        out["outlet_pressure"] = s.pressure

            # The bottoms of a column leave through its level control valve.
            # The draw is set by the valve opening (an opened valve draws the
            # sump down, a throttled one lets the inflow build it up) and by the
            # liquid available in the sump - an empty sump cannot be drawn.
            # This is what the level integrates against in _integrate_levels.
            # The valve may sit directly on the bottoms line (sump head drives
            # the draw) or behind a bottom pump (the pump + valve set the line
            # capacity); both cases feed the sump inventory balance here.
            if ntype in _CONTROL_VALVE_TYPES:
                os_ = out.get("outlet_stream")
                if os_ is None:
                    continue
                col, pumps = self._column_of_bottoms_valve(nid)
                if col is not None:
                    vs = self._vessel_state.get(col)
                    lvl = vs["level"] if vs else 0.0
                    draw = 0.0
                    out_p = None
                    for e2 in self._edges:
                        if e2.source != nid:
                            continue
                        t2 = self._node_map.get(e2.target)
                        if t2 is not None and t2.type == "sink":
                            out_p = float(t2.params.get("pressure_bar", 1.01325)) * 1e5
                            break
                    if lvl > 1e-9:
                        if pumps:
                            # Pumped bottoms: the pump moves whatever the line can
                            # take, so the draw is the line capacity - the tightest
                            # of the pump throughputs and the valve's own opening.
                            draw = os_.mass_flow
                            if hasattr(eq, "current_capacity"):
                                draw = float(eq.current_capacity(os_.density))
                            pump_cap = None
                            for p in pumps:
                                peq = self._equipment.get(p)
                                if peq is not None and hasattr(peq, "current_capacity"):
                                    c = float(peq.current_capacity(os_.density))
                                    pump_cap = c if pump_cap is None else min(pump_cap, c)
                            if pump_cap is not None:
                                draw = min(max(draw, 0.0), pump_cap)
                        elif hasattr(eq, "draw_capacity"):
                            # Direct sump valve: real hydraulics, the pressure
                            # upstream is the column pressure plus the static head
                            # rho*g*h of the liquid above the draw point; the flow
                            # is set by the true dp down to the receiving sink.  An
                            # empty sump (level ~ 0) cannot be drawn.
                            p_col = vs["p_base"] if vs else 1.01325e5
                            dp_extra = p_col - (out_p if out_p is not None else p_col)
                            draw = eq.draw_capacity(lvl, os_.density, dp_extra=dp_extra)
                        else:
                            draw = os_.mass_flow
                        if vs is not None:
                            max_draw = lvl * vs["area"] * os_.density / max(dt, 1e-9)
                            draw = min(max(draw, 0.0), max_draw)
                    if out_p is not None:
                        out["inlet_pressure"] = os_.pressure
                        out["outlet_pressure"] = out_p
                        out["dp"] = max(0.0, os_.pressure - out_p)
                        os_ = os_.copy_with(pressure=out_p)
                    out["outlet_stream"] = os_.copy_with(mass_flow=draw)
                    out["flow_out"] = draw
                    self._vessel_q_out[col] = draw

            self._attach_level(state, nid, node, incoming, out, dt)
            self._register_node_outputs(streams, nid, ntype, out)

        # A column without a bottoms level valve has no controlled draw: the
        # level is a pure integrator of (MESH bottoms inflow - actual draw), so
        # it accumulates until the operator opens a bottoms valve.  Only a real
        # bottoms valve (recorded above) writes _vessel_q_out for its column.

        # Back-pressure feedback: a throttling valve raises the pressure on its
        # inlet (dead-heading). Propagate that rise to the equipment feeding it
        # so the upstream shows the raised pressure instead of the nominal one.
        # The rise travels all the way back up the train (pumps, heaters, ...)
        # to the source, so the whole line responds to one valve change.
        for nid, out in outputs.items():
            node = self._node_map.get(nid)
            if node is None or node.type not in _CONTROL_VALVE_TYPES:
                continue
            if nid in hyd:
                continue  # pressures already set by the line hydraulic solver
            p_in = out.get("inlet_pressure")
            if p_in is None:
                continue
            visited: set = set()

            def raise_upstream(target_nid: str) -> None:
                if target_nid in visited:
                    return
                visited.add(target_nid)
                for edge in self._edges:
                    if edge.target != target_nid:
                        continue
                    up = edge.source
                    up_node = self._node_map.get(up)
                    # Sources and pumps set their own discharge pressure, so a
                    # throttling valve's back-pressure must not overwrite them;
                    # they are the upstream boundary of the dead-headed line.
                    if up_node is not None and up_node.type in ("source", "pump"):
                        continue
                    # A node solved by the line hydraulics already carries the
                    # authoritative pressure at that point; a legacy valve's
                    # back-pressure must not clobber it (and must not travel
                    # past it), or every solved line upstream would show the
                    # valve's dead-head pressure instead of its own.
                    if up in hyd:
                        continue
                    key = f"{up}:{edge.source_port}"
                    s = streams.get(key)
                    if s is not None:
                        s.pressure = max(s.pressure, float(p_in))
                    if up in visited:
                        continue
                    raise_upstream(up)

            raise_upstream(nid)

        self._last_outputs = outputs
        self._last_streams = streams
        return outputs

    # ------------------------------------------------------------------
    # Scheme topology helpers
    # ------------------------------------------------------------------

    def set_scheme(self, scheme: ProcessScheme) -> None:
        """Apply a new scheme topology to the engine (runtime reconfiguration)."""
        self._scheme = scheme
        self._hyd_state.clear()
        self._vessel_state.clear()
        self._vessel_q.clear()
        self._vessel_q_in.clear()
        self._vessel_q_out.clear()
        self._vessel_active.clear()
        self._tear_edges = []
        self._extend_equipment_from_scheme(scheme)
        self._rebuild_topology(scheme)
        self._configure_alarm_setpoints(scheme)
        # Rebuild the initial state so per-node params (initial_level, ...)
        # from the new scheme take effect.
        self._state = self._build_initial_state()
        logger.info("Scheme updated: %d nodes, %d edges.", len(scheme.nodes), len(scheme.edges))

    def _configure_alarm_setpoints(self, scheme: ProcessScheme) -> None:
        """Build per-equipment alarm setpoints from the scheme node 'limits'.

        Keeps the global demo setpoints (feed_flow, ...) and adds one
        AlarmSetpoint per measurable physical limit of each node, keyed by
        '<node_id>_<parameter>' (e.g. 'column_K1_pressure').
        """
        from copy import deepcopy
        from safety.alarm_system import AlarmSetpoint, DEFAULT_SETPOINTS
        setpoints: Dict[str, AlarmSetpoint] = {
            k: deepcopy(v) for k, v in DEFAULT_SETPOINTS.items()
        }
        measured: Dict[str, int] = {}
        # Bare defaults for every measurable node so the operator can arm a
        # threshold on any equipment even when the scheme carries no limits.
        node_defaults = {
            "column": ("pressure", "level", "temperature_top", "temperature_bottom"),
            "elou": ("pressure", "temperature", "level"),
            "separator": ("pressure", "temperature", "level"),
            "separator_s1k": ("pressure", "temperature", "level"),
            "tank": ("pressure", "temperature", "level"),
            "heater": ("temperature",),
        }
        for node in scheme.nodes:
            if node.type not in node_defaults:
                continue
            for quantity in node_defaults[node.type]:
                name = f"{node.id}_{quantity}"
                if name in setpoints:
                    continue
                unit = "Pa" if quantity == "pressure" else ("K" if "temperature" in quantity else "m")
                setpoints[name] = AlarmSetpoint(parameter=name, unit=unit)
        for node in scheme.nodes:
            # Column/tank defaults (K-1..K-4 presets, level limits) live on the
            # equipment params, not on the scheme node. Fall back to them so a
            # bare 'default' scheme still gets real alarm limits.
            limits = node.params.get("limits")
            if not isinstance(limits, dict) or not limits:
                eq = self._equipment.get(node.id)
                eq_limits = eq.params.get("limits") if eq is not None else None
                limits = eq_limits if isinstance(eq_limits, dict) else None
            if not isinstance(limits, dict) or not limits:
                continue
            nid = node.id
            def sp(name: str) -> AlarmSetpoint:
                if name not in setpoints:
                    setpoints[name] = AlarmSetpoint(parameter=name)
                return setpoints[name]
            # pressure
            if "pressure_high" in limits or "pressure_high_high" in limits or "pressure_low" in limits or "pressure_low_low" in limits:
                s = sp(f"{nid}_pressure")
                s.high = limits.get("pressure_high", s.high)
                s.high_high = limits.get("pressure_high_high", s.high_high)
                s.low = limits.get("pressure_low", s.low)
                s.low_low = limits.get("pressure_low_low", s.low_low)
                s.unit = "Pa"
                measured[f"{nid}_pressure"] = 1
            # single temperature (elou, separator, heater)
            if "temperature_high" in limits or "temperature_high_high" in limits or "temperature_low" in limits:
                s = sp(f"{nid}_temperature")
                s.high = limits.get("temperature_high", s.high)
                s.high_high = limits.get("temperature_high_high", s.high_high)
                s.low = limits.get("temperature_low", s.low)
                s.unit = "K"
                measured[f"{nid}_temperature"] = 1
            # column top / bottom temperatures
            if "temperature_top_high" in limits:
                s = sp(f"{nid}_temperature_top")
                s.high = limits["temperature_top_high"]
                s.unit = "K"
                measured[f"{nid}_temperature_top"] = 1
            if "temperature_bottom_high" in limits:
                s = sp(f"{nid}_temperature_bottom")
                s.high = limits["temperature_bottom_high"]
                s.unit = "K"
                measured[f"{nid}_temperature_bottom"] = 1
            # liquid level (columns, tanks, ELOU)
            if "level_low" in limits or "level_low_low" in limits or "level_high" in limits:
                s = sp(f"{nid}_level")
                s.low = limits.get("level_low", s.low)
                s.low_low = limits.get("level_low_low", s.low_low)
                s.high = limits.get("level_high", s.high)
                s.unit = "m"
                measured[f"{nid}_level"] = 1
        # Manually set operator limits win over the scheme/equipment defaults.
        for name, override in self._alarm_setpoint_overrides.items():
            if name in setpoints:
                setpoints[name] = override
        self._alarm_setpoints = setpoints
        self._measured_params = measured
        self._has_scheme_limits = any(
            isinstance(n.params.get("limits"), dict) for n in scheme.nodes
        )
        self._alarm_system.configure(setpoints)

    def get_alarm_setpoints(self) -> Dict[str, Dict[str, Any]]:
        """Return the active alarm setpoints (scheme defaults + manual overrides)."""
        return {
            name: {
                "parameter": sp.parameter,
                "low_low": sp.low_low,
                "low": sp.low,
                "high": sp.high,
                "high_high": sp.high_high,
                "unit": sp.unit,
            }
            for name, sp in self._alarm_setpoints.items()
        }

    def update_alarm_setpoint(
        self,
        parameter: str,
        low_low: Optional[float] = None,
        low: Optional[float] = None,
        high: Optional[float] = None,
        high_high: Optional[float] = None,
        unit: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Override the alarm limits of one parameter (manual operator setting).

        Only parameters that already produce alarm values can be edited.  The
        change survives scheme reloads via ``_alarm_setpoint_overrides`` and is
        applied immediately to the active alarm table.
        """
        from safety.alarm_system import AlarmSetpoint
        sp = self._alarm_setpoints.get(parameter)
        if sp is None:
            raise KeyError(parameter)
        if low_low is not None:
            sp.low_low = low_low
        if low is not None:
            sp.low = low
        if high is not None:
            sp.high = high
        if high_high is not None:
            sp.high_high = high_high
        if unit is not None:
            sp.unit = unit
        self._alarm_setpoint_overrides[parameter] = sp
        self._alarm_setpoints[parameter] = sp
        self._alarm_system.configure(self._alarm_setpoints)
        return self.get_alarm_setpoints()[parameter]

    def restore_alarm_setpoint(
        self,
        parameter: str,
        low_low: Optional[float],
        low: Optional[float],
        high: Optional[float],
        high_high: Optional[float],
        unit: str,
    ) -> bool:
        """Restore a persisted override, assigning every field exactly.

        Unlike ``update_alarm_setpoint`` (which only changes non-None fields)
        this also clears limits to None, so a saved "no low_low" setting is
        faithfully reproduced. Returns False when the parameter does not exist
        in the current scheme (its override is then dropped).
        """
        from safety.alarm_system import AlarmSetpoint
        if parameter not in self._alarm_setpoints:
            return False
        sp = AlarmSetpoint(
            parameter=parameter,
            low_low=low_low,
            low=low,
            high=high,
            high_high=high_high,
            unit=unit,
        )
        self._alarm_setpoint_overrides[parameter] = sp
        self._alarm_setpoints[parameter] = sp
        self._alarm_system.configure(self._alarm_setpoints)
        return True

    def reset_alarm_setpoints(self) -> None:
        """Discard manual overrides and restore scheme/equipment defaults."""
        self._alarm_setpoint_overrides.clear()
        self._configure_alarm_setpoints(self._scheme)

    def _extend_equipment_from_scheme(self, scheme: ProcessScheme) -> None:
        """Create equipment instances for scheme nodes of supported types."""
        for node in scheme.nodes:
            if node.id in self._equipment or node.type in ("source", "sink"):
                continue
            if node.type == "pump":
                self._equipment[node.id] = Pump(node.id, node.params)
            elif node.type == "valve":
                self._equipment[node.id] = Valve(node.id, node.params)
            elif node.type == "angle_valve":
                self._equipment[node.id] = AngleValve(node.id, node.params)
            elif node.type == "gate_valve":
                self._equipment[node.id] = GateValve(node.id, node.params)
            elif node.type == "elou":
                self._equipment[node.id] = ELOU(node.id, node.params)
            elif node.type == "heat_exchanger":
                self._equipment[node.id] = HeatExchanger(node.id, node.params)
            elif node.type == "heater":
                self._equipment[node.id] = Heater(node.id, node.params)
            elif node.type == "column":
                self._equipment[node.id] = column_class_for(node.id, node.params)(node.id, node.params)
            elif node.type == "separator":
                self._equipment[node.id] = Tank(node.id, node.params)
            elif node.type == "tank":
                self._equipment[node.id] = Tank(node.id, node.params)
            elif node.type == "mixer":
                self._equipment[node.id] = Mixer(node.id, node.params)
            elif node.type == "splitter":
                self._equipment[node.id] = Splitter(node.id, node.params)
            elif node.type == "separator_s1k":
                self._equipment[node.id] = SeparatorS1K(node.id, node.params)

    def _rebuild_topology(self, scheme: ProcessScheme) -> None:
        """Rebuild the node map, edge list and topological order."""
        self._node_map = scheme.node_map()
        self._edges = list(scheme.edges)
        indeg: Dict[str, int] = {nid: 0 for nid in self._node_map}
        for edge in self._edges:
            if edge.target in indeg:
                indeg[edge.target] += 1
        self._in_degree = indeg
        # Simple nodes (valves, pumps, pass-throughs) that collect SEVERAL
        # incoming streams are implicit mixers: they form a shared junction
        # in the hydraulic network instead of breaking the tree.  Equipment
        # with multi-port feeds stays a boundary (see _MULTI_IN_BOUNDARY_TYPES).
        self._junction_nodes = {
            nid for nid, d in indeg.items()
            if d > 1 and self._node_map[nid].type not in _MULTI_IN_BOUNDARY_TYPES
        }
        queue: List[str] = [nid for nid, d in indeg.items() if d == 0]
        order: List[str] = []
        while queue:
            nid = queue.pop(0)
            order.append(nid)
            for edge in self._edges:
                if edge.source == nid and edge.target in indeg:
                    indeg[edge.target] -= 1
                    if indeg[edge.target] == 0:
                        queue.append(edge.target)
        # Cycles (recycle loops): nodes never reached by Kahn stay with a
        # positive residual in-degree.  Process them too by tearing: pick the
        # leftover node with the fewest unsatisfied in-edges, cut those edges
        # (they become "tear edges" fed from the previous step's streams), and
        # repeat.  The cut makes the remaining edges acyclic, so the whole
        # recycle loop runs every step and converges across steps.
        leftover = {nid for nid, d in indeg.items() if d > 0}
        order_index = {nid: i for i, nid in enumerate(self._node_map)}
        tear_edges: List[str] = []
        while leftover:
            pending: Dict[str, int] = {}
            for edge in self._edges:
                if edge.source in leftover and edge.target in leftover:
                    pending[edge.target] = pending.get(edge.target, 0) + 1
            nid = min(leftover, key=lambda n: (pending.get(n, 0), order_index.get(n, 0)))
            for edge in self._edges:
                if edge.source in leftover and edge.target == nid:
                    tear_edges.append(f"{edge.source}:{edge.source_port}")
            leftover.remove(nid)
            order.append(nid)
        self._tear_edges = tear_edges
        self._topo_order = order

    def _compute_flow_limits(self, outputs: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """Max flow each node may carry, derived from downstream valves.

        A control valve limits the flow of its entire exclusive upstream line:
        a node's limit is the tightest valve throughput downstream of it, or
        None when it has any live (unrestricted) exit. Closed valves yield a
        limit of zero, so their upstream train dead-heads. Uses the valve
        throughput of the previous step (sources run before valves).
        """
        valve_cap: Dict[str, float] = {}
        for nid, node in self._node_map.items():
            if node.type not in _CONTROL_VALVE_TYPES:
                continue
            eq = self._equipment.get(nid)
            if eq is None or not hasattr(eq, "current_capacity"):
                continue
            prev_out = (self._last_outputs.get(nid) or {}).get("outlet_stream")
            density = prev_out.density if prev_out is not None else 850.0
            valve_cap[nid] = float(eq.current_capacity(density))
        memo: Dict[str, Optional[float]] = {}
        visiting: set = set()

        def cap_of(nid: str) -> Optional[float]:
            if nid in memo:
                return memo[nid]
            if nid in visiting:
                return None  # cycle -> keep live
            visiting.add(nid)
            node = self._node_map.get(nid)
            if node is None or node.type == "sink":
                res: Optional[float] = None
            elif node.type in _CONTROL_VALVE_TYPES:
                own = valve_cap.get(nid)
                out_edges = [e for e in self._edges if e.source == nid]
                child_caps = [cap_of(e.target) for e in out_edges]
                valid = [c for c in child_caps if c is not None]
                downstream = min(valid) if valid else None
                if downstream is None:
                    res = own
                elif own is None:
                    res = downstream
                else:
                    res = min(own, downstream)
            elif node.type == "pump":
                # A stopped / failed pump isolates its line (dead-heads), so
                # upstream equipment holds back and levels respond.  A running
                # pump additionally throttles its whole line to the capacity of
                # its current rotation speed (affinity law Q ~ n), and to the
                # tightest valve downstream of it.
                eq = self._equipment.get(nid)
                if eq is None or not (eq.state.running and not eq.state.failed):
                    res = 0.0
                else:
                    pump_cap = float(eq.current_capacity(850.0))
                    out_edges = [e for e in self._edges if e.source == nid]
                    child_caps = [cap_of(e.target) for e in out_edges]
                    valid = [c for c in child_caps if c is not None]
                    downstream = min(valid) if valid else None
                    res = pump_cap if downstream is None else min(pump_cap, downstream)
            elif node.type == "gate_valve":
                # A closed задвижка dead-heads its whole upstream line, an
                # open one passes the flow through without restricting it.
                eq = self._equipment.get(nid)
                if eq is None or not getattr(eq, "is_open", True):
                    res = 0.0
                else:
                    out_edges = [e for e in self._edges if e.source == nid]
                    if not out_edges:
                        res = None
                    else:
                        child_caps = [cap_of(e.target) for e in out_edges]
                        res = None if any(c is None for c in child_caps) else min(child_caps)
            else:
                out_edges = [e for e in self._edges if e.source == nid]
                if not out_edges:
                    res = None
                else:
                    child_caps = [cap_of(e.target) for e in out_edges]
                    res = None if any(c is None for c in child_caps) else min(child_caps)
            visiting.discard(nid)
            memo[nid] = res
            return res

        return {nid: cap_of(nid) for nid in self._node_map}

    # ------------------------------------------------------------------
    # Branched-line hydraulics
    # ------------------------------------------------------------------

    # Heat exchanger channels: an inlet port pairs with its own outlet, so a
    # two-stream exchanger is two independent hydraulic lines (hot and cold)
    # that share one node but never mix their flows.
    _HX_PORT_PAIRS = {"hot_in": "hot_out", "cold_in": "cold_out", "in": "out"}
    # Furnace sections: a multi-pass furnace heats several independent tube
    # passes, each with its own inlet -> outlet port pair (5 passes: main oil,
    # side streams and the superheated-steam ПП channel).  Each pass is its own
    # hydraulic line, exactly like an exchanger channel.
    _FURNACE_PORT_PAIRS = {
        "in": "out", "in2": "out2", "in3": "out3", "in4": "out4",
        "pp_in": "pp_out", "pp1_in": "pp1_out", "pp2_in": "pp2_out",
    }
    # Fallback per-channel resistance of a heat exchanger when the scheme
    # carries no delta_p: 0.1 atm (Pa) at the reference flow.
    _HX_DEFAULT_DP = 10132.5
    # Hard cap on the pressure drop of one exchanger channel regardless of the
    # flow through it (ТЗ: the exchanger never throttles more than 0.5 atm).
    _HX_MAX_DP = 0.5 * 101325.0
    # In-line vessels with a single oil outlet: transparent for the line solver
    # (no own resistance), so the pump head stays anchored at the sink pressure
    # instead of the full curve head riding through to the sink.
    _TRANSIT_NODE_TYPES = ("elou", "separator", "tank")

    def _vessel_boundary(self, nid: str) -> Dict[str, Any]:
        """Per-vessel buffer state (level, pressure, drain resistance).

        A separator / tank / ELOU is treated as an inventory boundary: its
        pressure (base + hydrostatic head) anchors the upstream line as a sink
        and the downstream line as a source, so the inflow and outflow are
        decoupled and the level integrates their difference (alive levels).
        """
        vs = self._vessel_state.get(nid)
        if vs is not None:
            return vs
        node = self._node_map.get(nid)
        p = node.params if node is not None else {}
        if node is not None and node.type in ("column", "elou"):
            # A column and an ELOU (dehydrator) are live inventory boundaries.
            # Their operating pressure is set by the elements downstream of
            # them (the product sinks), so the feeding lines push against the
            # same pressure the products leave at -- the vessel never holds an
            # arbitrary preset pressure.  For the ELOU the downstream sink
            # pressure is the pressure "after" the dehydrator, so any change of
            # the outlet line propagates into the vessel pressure.
            p_base = self._column_downstream_pressure(nid, p)
        else:
            # Vessel operating pressure: the explicit nominal_pressure (Pa) when
            # present, otherwise the pressure_bar param, otherwise atmospheric.
            # Must match what the vessel model itself pushes at its outlet, or
            # the upstream line would push against a different pressure than
            # the vessel's own outlet carries (pressure discontinuity).
            p_nom = p.get("nominal_pressure")
            p_base = float(p_nom) if p_nom else float(p.get("pressure_bar", 1.01325)) * 1e5
        height = float(p.get("height_m", 6.0))
        initial = float(p.get("initial_level", 2.0))
        level = max(0.0, min(initial, height))
        area = float(p.get("vessel_area") or p.get("sump_area") or 10.0)
        diameter = p.get("diameter_m")
        if diameter:
            area = 3.141592653589793 * (float(diameter) / 2.0) ** 2
        q_nom = float(p.get("nominal_flow") or p.get("flow_kg_s") or 100.0)
        head_nom = 850.0 * 9.81 * max(level, 0.2)
        k_drain = max(head_nom, 1.0) / max(q_nom * q_nom, 1e-6)
        # Static head of the liquid column; p_src drives the downstream drain
        # line, p_out may add a flow-dependent back-pressure (ELOU) on top.
        static_head = 0.0 if node is not None and node.type in ("column", "elou") else 850.0 * 9.81 * level
        vs = {
            "level": level,
            "area": area,
            "height": height,
            "p_base": p_base,
            "p_src": p_base + static_head,
            "p_out": p_base + static_head,
            "k_drain": k_drain,
            # A fully filled vessel is a rigid, incompressible boundary: it can
            # accept no more mass than its outflow removes.  Once the level
            # reaches the rim the feeding line dead-heads (inlet flow -> 0)
            # until the level drops back below the rim (see _integrate_levels).
            "full": False,
            # Barrier pressure for a full vessel: far above anything any pump or
            # source in the model can deliver, so the inlet line dead-heads and
            # the inflow is truly zero instead of being silently absorbed.
            "p_block": p_base + 1e9,
        }
        self._vessel_state[nid] = vs
        return vs

    def _column_of_bottoms_valve(self, valve_nid: str):
        """Column whose bottoms line feeds a control valve, with the pumps on it.

        Walks upstream from the valve (through pumps and pass-through
        equipment) until it reaches a column whose 'bottoms' port starts the
        path.  Returns (column_id, [pump_ids on the path]) or (None, []) when
        the valve does not belong to a column bottoms line (e.g. a reflux or
        product line).  The pumps matter because a pumped bottoms line draws at
        the tightest of the pump throughput and the valve opening, while a
        direct sump valve draws from the static head.
        """
        def walk(cur: str, pumps: list) -> tuple:
            for edge in self._edges:
                if edge.target != cur:
                    continue
                up = edge.source
                up_node = self._node_map.get(up)
                if up_node is None:
                    continue
                if up_node.type == "column":
                    if edge.source_port == "bottoms":
                        return up, pumps
                    return None, pumps
                if up_node.type == "pump":
                    res, acc = walk(up, pumps + [up])
                elif up_node.type in _CONTROL_VALVE_TYPES:
                    continue
                elif up_node.type == "sink":
                    continue
                elif up_node.type in ("heat_exchanger", "heater"):
                    # A heat exchanger / furnace has several independent passes
                    # with their own supply sources, so a valve sitting after one
                    # of them is on that pass, not on the column bottoms line.
                    continue
                else:
                    res, acc = walk(up, pumps)
                if res is not None:
                    return res, acc
            return None, pumps

        return walk(valve_nid, [])

    def _column_downstream_pressure(
        self, nid: str, params: Dict[str, Any], _seen: Optional[set] = None
    ) -> float:
        """Pressure a column / ELOU holds, taken from the elements downstream.

        The product lines (distillate / side draw / bottoms, and for an ELOU the
        oil outlet into a downstream column) run into sink nodes, each with its
        own fixed pressure.  The vessel must sit at the highest of those so every
        product can flow out, otherwise a product would have to run uphill
        against a higher sink pressure.  Falls back to the vessel preset when no
        downstream sink is connected.
        """
        node = self._node_map.get(nid)
        ntype = node.type if node is not None else ""
        seen = set() if _seen is None else _seen

        def _walk(cur: str, cur_seen: set) -> Optional[float]:
            best: Optional[float] = None
            for e in self._edges:
                if e.source != cur or e.target in cur_seen:
                    continue
                t = self._node_map.get(e.target)
                if t is None:
                    continue
                if t.type == "sink":
                    p = float(t.params.get("pressure_bar", 1.01325)) * 1e5
                elif t.type in ("column", "elou"):
                    p = self._column_downstream_pressure(
                        e.target, t.params, cur_seen | {e.target}
                    )
                elif t.type in ("separator", "tank"):
                    p_nom = t.params.get("nominal_pressure")
                    p = float(p_nom) if p_nom else float(t.params.get("pressure_bar", 1.01325)) * 1e5
                else:
                    p = _walk(e.target, cur_seen | {e.target})
                if p is not None and (best is None or p > best):
                    best = p
            return best

        if ntype == "elou":
            # The ELOU sits between the upstream line and the downstream plant:
            # its oil outlet may feed a column running under its own pressure, so
            # walk every product path to the farthest pressure holder instead of
            # anchoring only to the brine sink at the bottom port.
            p = _walk(nid, seen | {nid})
            if p is not None:
                return p
        else:
            # A column anchors to its direct product sinks only.
            sink_pressures: List[float] = []
            for e in self._edges:
                if e.source != nid:
                    continue
                target_node = self._node_map.get(e.target)
                if target_node is None or target_node.type != "sink":
                    continue
                sink_pressures.append(
                    float(target_node.params.get("pressure_bar", 1.01325)) * 1e5
                )
            if sink_pressures:
                return max(sink_pressures)
        col_eq = self._equipment.get(nid)
        return float(getattr(col_eq, "pressure", None) or (params.get("pressure_bar", 1.01325) * 1e5))

    def _outlet_line_capacity(self, nid: str, port: str, density: float = 850.0) -> Optional[float]:
        """Physical throughput of a vessel's outlet line starting at ``port``.

        Walks the downstream elements (valves, pumps, pass-throughs) up to the
        receiving sink and returns the tightest capacity of the line; None when
        nothing restricts the flow (no throttling element on the path).  This is
        the real drain capacity of an ELOU oil outlet whose line carries no
        solved hydraulics (a multi-outlet vessel builds no downstream tree), so
        a closed outlet valve holds the oil back instead of vanishing.
        """
        seen: set = {nid}
        queue = [
            e.target
            for e in self._edges
            if e.source == nid and e.source_port == port
        ]
        cap: Optional[float] = None
        while queue:
            nxt = queue.pop(0)
            if nxt in seen or nxt not in self._node_map:
                continue
            seen.add(nxt)
            node = self._node_map[nxt]
            if node.type == "sink":
                continue
            if node.type in _CONTROL_VALVE_TYPES:
                eq = self._equipment.get(nxt)
                if eq is not None and hasattr(eq, "current_capacity"):
                    c = float(eq.current_capacity(density))
                    cap = c if cap is None else min(cap, c)
            # Pumps and pass-through elements do not restrict a drain line;
            # pipe resistance is secondary to the control valve here.
            queue.extend(
                e.target for e in self._edges if e.source == nxt
            )
        return cap

    def _integrate_levels(self, dt: float) -> None:
        """Advance each buffer vessel's level: dL/dt = (Q_in - Q_out)/(rho*A)."""
        for nid, vs in self._vessel_state.items():
            q = self._vessel_q.get(nid)
            if q is None:
                continue
            node = self._node_map.get(nid)
            if node is not None and node.type == "column":
                # A column's level is the bottoms sump: it integrates the
                # inflow to the sump (the MESH bottoms product) against the
                # real bottoms draw through the level valve.
                qi = max(0.0, self._vessel_q_in.get(nid, 0.0))
            else:
                qi = max(0.0, q.get("in", 0.0))
            qo = max(0.0, self._vessel_q_out.get(nid, 0.0))
            lvl = vs["level"] + (qi - qo) / max(850.0 * vs["area"], 1e-6) * dt
            deadband = max(0.01 * vs["height"], 0.02)
            if lvl >= vs["height"]:
                # Overflow: a fully filled vessel cannot accept more mass than
                # its outflow drains (incompressible liquid).  If the inflow
                # still exceeds the drain there is nowhere for the liquid to
                # go, so the feeding line dead-heads: the effective inflow is
                # capped at the outflow and the level stays on the rim.  The
                # blocked excess is never created (mass-conserving) -- the
                # upstream hydraulics reflect it as a pressure rise instead.
                lvl = vs["height"]
                vs["full"] = True
                if node is not None and node.type == "column":
                    # A column's inflow is the MESH bottoms product, not a
                    # solved tree flow, so the dead-heading p_block cannot cut
                    # it -- cap the effective inflow at the draw explicitly.
                    self._vessel_q_in[nid] = qo
            elif vs.get("full") and lvl >= vs["height"] - deadband:
                # Hysteresis: a vessel that has just reached the rim stays
                # "full" (inlet line dead-headed) until its level drops a
                # little below the rim, otherwise a level resting exactly on
                # the rim would flip full/not-full every step and the inlet
                # flow would oscillate between the full line capacity and
                # zero while the vessel can accept no mass at all.
                vs["full"] = True
            elif lvl < 0.0:
                lvl = 0.0
                vs["full"] = False
            else:
                vs["full"] = False
            vs["level"] = lvl
            node = self._node_map.get(nid)
            if node is not None and node.type in ("column", "elou"):
                # Column / ELOU discharge pressure is anchored to the downstream
                # product sinks, not to their liquid level (see _vessel_boundary).
                vs["p_src"] = vs["p_base"]
                vs["p_out"] = vs["p_base"]
            else:
                vs["p_src"] = vs["p_base"] + 850.0 * 9.81 * vs["level"]
                vs["p_out"] = vs["p_src"]

    def _build_line_trees(self) -> List[Dict[str, Any]]:
        """Split the scheme into branched hydraulic trees source -> ... -> sinks.

        A tree starts at a 'source' (or a buffer vessel acting as a source) and
        fans out through simple elements (pump, valve, pass-through).  Complex
        multi-stream devices (heat exchanger, column) and merge points (in-degree
        > 1) break the tree.  A separator / tank / ELOU is an inventory
        boundary: it ends the upstream tree as a sink at its own pressure and
        starts a NEW tree as a source with a drain resistance, so its level can
        accumulate.  A tree is usable only when it reaches at least one sink
        through at least one element; a branch with no resistance has no
        definable flow and is left to the legacy stream propagation.
        """
        from calculation_core.hydraulics.line_hydraulics import valve_resistance, _K_EPS
        indeg: Dict[str, int] = {nid: 0 for nid in self._node_map}
        for edge in self._edges:
            indeg[edge.target] = indeg.get(edge.target, 0) + 1
        by_source: Dict[str, List[Any]] = {}
        for edge in self._edges:
            by_source.setdefault(edge.source, []).append(edge)
        density = 850.0
        trees: List[Dict[str, Any]] = []
        claimed: set = set()
        column_sink_nodes: set = set()
        shared_sink_nodes: set = set()
        queue: List[str] = []

        def claim(nodes: Dict[str, Any]) -> None:
            # A multi-feed column / two-phase separator is a shared inventory
            # boundary: each feeding line builds its own tree to it, so the
            # shared sink is never claimed by any single tree.
            claimed.update(
                k for k in nodes
                if k not in column_sink_nodes and k not in shared_sink_nodes
            )

        def lookahead_sink(cur: str, seen: set, via_port: Optional[str] = None) -> bool:
            for edge in by_source.get(cur, []):
                if via_port is not None and edge.source_port != via_port:
                    continue
                nxt = edge.target
                if nxt in seen or nxt not in self._node_map or nxt in claimed:
                    continue
                nt = self._node_map[nxt].type
                if nt == "heat_exchanger":
                    pair = self._HX_PORT_PAIRS.get(edge.target_port)
                    if pair and lookahead_sink(nxt, seen | {nxt}, pair):
                        return True
                    continue
                if nt == "heater":
                    # A multi-pass furnace is a stack of independent sections:
                    # a feeding line continues only if the matching section
                    # outlet leads to a sink.
                    pair = self._FURNACE_PORT_PAIRS.get(edge.target_port)
                    if pair and lookahead_sink(nxt, seen | {nxt}, pair):
                        return True
                    continue
                if nt == "column":
                    if indeg.get(nxt, 0) > 1:
                        # A multi-feed column is a live inventory boundary: any
                        # feed line (feed/reflux/steam/circ/main in) terminates
                        # the tree as a sink at the column's operating pressure.
                        return True
                    if lookahead_sink(nxt, seen | {nxt}):
                        return True
                    continue
                if nt == "separator_s1k":
                    # С-1К is an inventory boundary: any feed line terminates
                    # here at the vessel's operating pressure (the flash split
                    # and the level-controlled outflow are model-side, the
                    # engine only anchors the pressures).
                    return True
                if nt == "mixer":
                    # A mixer is a junction at its downstream sink pressure:
                    # every feeding line terminates here as a sink, and each
                    # valve upstream must drop to the junction pressure.
                    return True
                if nxt in self._junction_nodes:
                    # Implicit mixer: a junction terminates every feeding line
                    # as a sink at its downstream pressure, so any upstream
                    # path that reaches it has found its sink.
                    return True
                if nt in self._TRANSIT_NODE_TYPES:
                    # An inventory vessel (ELOU / separator / tank) is a live
                    # inventory boundary: every feeding line terminates here as
                    # a sink at the vessel's own pressure, whatever its
                    # in-degree (an ELOU can be fed by several lines at once,
                    # e.g. through parallel preheat trains).
                    return True
                if indeg.get(nxt, 0) > 1:
                    continue
                if nt == "sink":
                    return True
                if lookahead_sink(nxt, seen | {nxt}):
                    return True
            return False

        def build_tree(
            root_nid: str,
            is_vessel: bool = False,
        ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[str]], List[str], List[str]]:
            tree_nodes: Dict[str, Dict[str, Any]] = {}
            children: Dict[str, List[str]] = {}
            sink_ids: List[str] = []
            vessel_roots: List[str] = []
            element_count = 0
            tree_nodes[root_nid] = {"type": "source"}

            def visit(cur: str, seen: set, edges: List[Any], via_port: Optional[str] = None) -> None:
                nonlocal element_count
                for edge in edges:
                    if via_port is not None and edge.source_port != via_port:
                        continue
                    nxt = edge.target
                    if nxt in seen or nxt not in self._node_map or nxt in claimed:
                        continue
                    nxt_node = self._node_map[nxt]
                    ntype = nxt_node.type
                    if ntype == "heat_exchanger":
                        # Two independent channels (hot / cold), each its own
                        # line from the paired inlet to the paired outlet.  The
                        # channel node is keyed by port so the two streams never
                        # collide and each keeps its own flow and pressure drop.
                        pair = self._HX_PORT_PAIRS.get(edge.target_port)
                        if pair is None or not lookahead_sink(nxt, {nxt}, pair):
                            continue
                        ch_key = f"{nxt}:{edge.target_port}"
                        children.setdefault(cur, []).append(ch_key)
                        tree_nodes[ch_key] = self._hx_channel_info(nxt)
                        element_count += 1
                        visit(ch_key, seen | {ch_key}, by_source.get(nxt, []), pair)
                        continue
                    if ntype == "column":
                        if indeg.get(nxt, 0) > 1:
                            # Multi-feed column: every feed line (feed/reflux/
                            # steam/circ/main in) ends here as a live inventory
                            # boundary -- the column absorbs each feed at its own
                            # operating pressure, which follows the product
                            # sinks downstream.  Product flows stay MESH-derived;
                            # the solved outlet pressure anchors the distillate /
                            # side draw / bottoms streams.
                            vs = self._vessel_boundary(nxt)
                            children.setdefault(cur, []).append(nxt)
                            tree_nodes[nxt] = {"type": "sink", "sink_p": vs["p_block"] if vs.get("full") else vs["p_out"], "vessel": nxt, "absorb": True}
                            sink_ids.append(nxt)
                            # The column is shared by all its feeding lines, so
                            # it must never be claimed by a single tree.
                            column_sink_nodes.add(nxt)
                            continue
                        # A column is a single-inlet vessel: the line passes
                        # through it (no own resistance) and fans out into the
                        # distillate / bottoms branches like any fork.
                        if not lookahead_sink(nxt, {nxt}):
                            continue
                        children.setdefault(cur, []).append(nxt)
                        tree_nodes[nxt] = {"type": "pass"}
                        element_count += 1
                        visit(nxt, seen | {nxt}, by_source.get(nxt, []))
                        continue
                    if ntype == "separator_s1k":
                        # С-1К is an inventory boundary: the feeding line ends
                        # here as a sink at the vessel's operating pressure
                        # (base + hydrostatic head).  The node is shared (never
                        # claimed), so every feed line builds its own tree to it
                        # and each pump/valve upstream pushes against the same
                        # pressure the separator's outlets carry.
                        vs = self._vessel_boundary(nxt)
                        children.setdefault(cur, []).append(nxt)
                        tree_nodes[nxt] = {"type": "sink", "sink_p": vs["p_block"] if vs.get("full") else vs["p_out"]}
                        sink_ids.append(nxt)
                        shared_sink_nodes.add(nxt)
                        continue
                    if ntype == "mixer":
                        # A mixer is a junction at its downstream sink pressure
                        # (the element first after it, or a direct sink).  Every
                        # feeding line terminates here as a sink at that pressure,
                        # so each upstream valve drops to the junction pressure
                        # and the whole line is solved in one network.  The mixer
                        # is shared (never claimed), like a multi-feed separator.
                        p_mix = self._mixer_back_pressure(nxt, {})
                        children.setdefault(cur, []).append(nxt)
                        tree_nodes[nxt] = {
                            "type": "sink",
                            "sink_p": float(p_mix if p_mix is not None else 1.01325e5),
                        }
                        sink_ids.append(nxt)
                        shared_sink_nodes.add(nxt)
                        continue
                    if ntype == "heater":
                        # A multi-pass furnace: each section inlet -> outlet is
                        # its own hydraulic line (like an exchanger channel).
                        # The section node is keyed by the inlet port so the
                        # passes never share flow; the furnace node itself is
                        # never claimed, so every feeding line builds its own
                        # channel tree through the matching outlet.
                        pair = self._FURNACE_PORT_PAIRS.get(edge.target_port)
                        if pair is None or not lookahead_sink(nxt, {nxt}, pair):
                            continue
                        ch_key = f"{nxt}:{edge.target_port}"
                        children.setdefault(cur, []).append(ch_key)
                        tree_nodes[ch_key] = {"type": "pass"}
                        element_count += 1
                        visit(ch_key, seen | {ch_key}, by_source.get(nxt, []), pair)
                        continue
                    if nxt in self._junction_nodes:
                        # Implicit mixer: several streams enter a simple node
                        # (a valve, pump or pass-through).  The node behaves as
                        # a junction at the pressure of the first element
                        # downstream of it, and every feeding line terminates
                        # here as a sink at that pressure.  The node is shared
                        # (never claimed), so each upstream valve drops to the
                        # junction pressure and all feeding branches are solved
                        # in one network -- exactly like an explicit mixer.
                        p_mix = self._mixer_back_pressure(nxt, {})
                        children.setdefault(cur, []).append(nxt)
                        tree_nodes[nxt] = {
                            "type": "sink",
                            "sink_p": float(p_mix if p_mix is not None else 1.01325e5),
                        }
                        sink_ids.append(nxt)
                        shared_sink_nodes.add(nxt)
                        continue
                    if ntype in self._TRANSIT_NODE_TYPES:
                        vs = self._vessel_boundary(nxt)
                        children.setdefault(cur, []).append(nxt)
                        if lookahead_sink(nxt, {nxt}):
                            # Inventory boundary: absorb the upstream flow here
                            # and continue downstream from a NEW tree.  A vessel
                            # with several outlet streams (e.g. an ELOU with oil
                            # and brine) splits them with fixed model fractions;
                            # the hydraulic solver must not re-divide them, so no
                            # downstream tree is built and the outlet streams
                            # propagate as model-driven pass-throughs.
                            tree_nodes[nxt] = {"type": "sink", "sink_p": vs["p_block"] if vs.get("full") else vs["p_out"], "vessel": nxt, "absorb": True}
                            sink_ids.append(nxt)
                            if len(by_source.get(nxt, [])) <= 1:
                                vessel_roots.append(nxt)
                        else:
                            # No downstream line -> keep the legacy pass-through.
                            tree_nodes[nxt] = {"type": "pass"}
                            visit(nxt, seen | {nxt}, by_source.get(nxt, []))
                        continue
                    if ntype == "sink":
                        children.setdefault(cur, []).append(nxt)
                        tree_nodes[nxt] = {
                            "type": "sink",
                            "sink_p": float(nxt_node.params.get("pressure_bar", 1.01325)) * 1e5,
                        }
                        sink_ids.append(nxt)
                        continue
                    if ntype in _CONTROL_VALVE_TYPES:
                        eq = self._equipment.get(nxt)
                        if eq is None:
                            continue
                        fully_open = eq.position >= 1.0
                        k = valve_resistance(density, eq.cv, eq.position)
                        children.setdefault(cur, []).append(nxt)
                        tree_nodes[nxt] = {
                            "type": "valve",
                            "k": _K_EPS if (k <= 0.0 or fully_open) else k,
                            "closed": eq.position <= 1e-6,
                            "passthrough": fully_open,
                        }
                    elif ntype == "gate_valve":
                        eq = self._equipment.get(nxt)
                        if eq is None:
                            continue
                        children.setdefault(cur, []).append(nxt)
                        tree_nodes[nxt] = {
                            "type": "valve",
                            "k": _K_EPS,
                            "closed": not getattr(eq, "is_open", True),
                        }
                    elif ntype == "pump":
                        children.setdefault(cur, []).append(nxt)
                        tree_nodes[nxt] = {"type": "pump", "head": self._make_pump_head(nxt)}
                    else:
                        children.setdefault(cur, []).append(nxt)
                        k_pipe = self._pipe_resistance(nxt, density)
                        if k_pipe is not None:
                            tree_nodes[nxt] = {"type": "res", "k": k_pipe, "head": self._static_head(nxt, density)}
                        else:
                            tree_nodes[nxt] = {"type": "pass"}
                    element_count += 1
                    visit(nxt, seen | {nxt}, by_source.get(nxt, []))

            if is_vessel:
                vs = self._vessel_boundary(root_nid)
                drain_id = f"{root_nid}__drain"
                # The drain resistance must see the static head of the liquid
                # column.  Separator/tank p_src already includes it (head 0);
                # a column/ELOU anchors p_src to the downstream sink pressure
                # instead, so the level head is added here or the drain line
                # would solve with zero differential -> zero flow.
                static_head = max(0.0, 850.0 * 9.81 * vs["level"] - (vs["p_src"] - vs["p_base"]))
                tree_nodes[drain_id] = {"type": "res", "k": vs["k_drain"], "head": static_head}
                children[root_nid] = [drain_id]
                element_count += 1
                visit(drain_id, {root_nid, drain_id}, by_source.get(root_nid, []))
            else:
                visit(root_nid, {root_nid}, by_source.get(root_nid, []))

            return tree_nodes, children, sink_ids, vessel_roots

        for nid, node in self._node_map.items():
            if node.type != "source" or nid in claimed:
                continue
            p_src = float(node.params.get("pressure_bar", 1.01325)) * 1e5
            p_src_max = float(node.params.get("max_pressure_bar", 10.0)) * 1e5
            q_src_limit = node.params.get("flow_kg_s")
            tree_nodes, children, sink_ids, vessel_roots = build_tree(nid)
            if not sink_ids or not any(k != nid for k in tree_nodes):
                continue
            claim(tree_nodes)
            trees.append({
                "root": nid,
                "p_src": p_src,
                "p_src_max": p_src_max,
                "q_src_limit": q_src_limit,
                "nodes": tree_nodes,
                "children": children,
            })
            queue.extend(vessel_roots)

        processed: set = set()
        while queue:
            vnid = queue.pop(0)
            if vnid in processed:
                continue
            processed.add(vnid)
            vs = self._vessel_boundary(vnid)
            tree_nodes, children, sink_ids, vessel_roots = build_tree(vnid, is_vessel=True)
            if not sink_ids or not any(k != vnid for k in tree_nodes):
                continue
            claim(tree_nodes)
            trees.append({
                "root": vnid,
                "p_src": vs.get("p_src", vs["p_out"]),
                "q_src_limit": None,
                "root_vessel": vnid,
                "nodes": tree_nodes,
                "children": children,
            })
            queue.extend(v for v in vessel_roots if v != vnid)
        return trees

    def _hx_channel_info(self, nid: str) -> Dict[str, Any]:
        """Hydraulic model of one heat-exchanger channel (hot or cold pass).

        A heat exchanger drops pressure like any resistance element: dP = k*Q^2.
        The per-channel k is calibrated so the drop equals the node's ``delta_p``
        (default 0.1 atm, Pa) at its reference flow.  ``delta_p = 0`` makes the
        channel a plain pass-through.
        """
        node = self._node_map.get(nid)
        p = node.params if node is not None else {}
        dp = p.get("delta_p")
        delta_p = float(dp) if dp is not None else self._HX_DEFAULT_DP
        if delta_p <= 0.0:
            return {"type": "pass"}
        q_ref = float(p.get("nominal_flow") or p.get("flow_kg_s") or 100.0)
        max_dp = float(p.get("max_delta_p") or self._HX_MAX_DP)
        return {
            "type": "res",
            "k": delta_p / max(q_ref * q_ref, 1e-6),
            "head": 0.0,
            "max_dp": max_dp,
        }

    def _pipe_resistance(self, nid: str, density: float) -> Optional[float]:
        """Quadratic pipe resistance k in ΔP = k·Q² for a scheme pipe node.

        Uses the node's pipe params (length_m, diameter_m, roughness_m,
        minor_loss_k, flow_kg_s / nominal_flow as the reference flow).  Returns
        None when the node carries no pipe geometry, so it stays a pass-through.
        """
        node = self._node_map.get(nid)
        if node is None:
            return None
        p = node.params
        length = p.get("length_m")
        diameter = p.get("diameter_m")
        if not length or not diameter or float(length) <= 0.0 or float(diameter) <= 0.0:
            return None
        ref_flow = float(p.get("flow_kg_s") or p.get("nominal_flow") or 1.0)
        dp = calculate_pipe_pressure_drop(
            flow_rate=ref_flow, density=density,
            viscosity=float(p.get("viscosity_pa_s", 0.001)),
            length=float(length), diameter=float(diameter),
            roughness=float(p.get("roughness_m", 0.000045)),
            minor_loss_k=float(p.get("minor_loss_k", 0.0)),
        )
        return dp / max(ref_flow * ref_flow, 1e-12)

    def _static_head(self, nid: str, density: float) -> float:
        """Static head term [Pa] for a scheme pipe node: ρ·g·Δz (ТЗ section 17).

        Positive when the outlet is ABOVE the inlet (costs pressure), negative
        when it falls (gains pressure).  Defaults to zero when no elevation
        params are present.
        """
        node = self._node_map.get(nid)
        if node is None:
            return 0.0
        p = node.params
        dz = p.get("delta_elevation_m")
        if dz is None:
            z_in = p.get("elevation_in_m", 0.0)
            z_out = p.get("elevation_out_m", 0.0)
            dz = z_out - z_in
        return density * 9.81 * float(dz)

    def _make_pump_head(self, nid: str) -> Callable[[float], float]:
        """Pump discharge head characteristic H(Q) for a scheme pump node.

        Delegates to the pump's real pump curve (ТЗ sections 19-22) so the
        network solver and the equipment use the SAME characteristic at the
        operating point.  Q is the mass flow [kg/s], H is in [Pa].
        """
        def pump_head(q: float) -> float:
            eq = self._equipment.get(nid)
            node = self._node_map.get(nid)
            if eq is None or node is None or not (eq.state.running and not eq.state.failed):
                return 0.0
            density = 850.0
            q_m3_s = max(0.0, q) / max(density, 1e-6)
            return max(0.0, eq.curve.pressure_rise(q_m3_s, eq.speed_ratio))
        return pump_head

    def _solve_line_hydraulics(self) -> Dict[str, Dict[str, float]]:
        """Steady-state hydraulic solution for every branched line.

        Returns per-node data {flow, p_in, p_out} for the nodes of each tree, so
        equipment steps can be overwritten with the physically consistent mass
        flow and pressure cascade: one shared flow through serial chains, flow
        split between fork branches in proportion to their resistance, the sink
        pressure treated as a hard boundary and dead-head pressure in front of a
        throttling or closed valve.
        """
        from calculation_core.hydraulics.line_hydraulics import solve_branched_network
        # Column / ELOU pressure is anchored to the product sinks downstream,
        # which an operator can retune at runtime -- re-derive it every step so
        # a sink pressure change propagates into the vessel immediately.  An
        # ELOU also builds a flow-dependent back-pressure on its static head:
        # p = p_after + rho*g*h + k_drain * q^2, so the dehydrator pressure
        # responds to the throughput and to the pressure downstream of it.
        for nid, node in self._node_map.items():
            if node.type not in ("column", "elou"):
                continue
            vs = self._vessel_state.get(nid)
            if vs is None:
                continue
            vs["p_base"] = self._column_downstream_pressure(nid, node.params)
            # The ELOU sits in the feed line of the downstream plant (typically
            # a column): its discharge pressure must equal the pressure of the
            # receiving equipment so the oil can actually flow into it.  Neither
            # the static head nor a drain back-pressure is added on top.
            vs["p_src"] = vs["p_base"]
            vs["p_out"] = vs["p_base"]
        self._vessel_q = {nid: {"in": 0.0, "out": 0.0} for nid in self._vessel_state}
        self._vessel_active = set()
        result: Dict[str, Dict[str, float]] = {}
        for tree in self._build_line_trees():
            try:
                solved = solve_branched_network(
                    tree["p_src"],
                    tree["q_src_limit"],
                    tree["nodes"],
                    tree["children"],
                    tree["root"],
                    tree.get("p_src_max"),
                )
            except Exception:
                logger.exception(
                    "Branch hydraulics failed for source '%s'; skipping.", tree["root"]
                )
                continue
            for nid, info in tree["nodes"].items():
                if info.get("type") == "sink" and info.get("vessel"):
                    r = solved.get(nid)
                    if r is not None:
                        self._vessel_active.add(nid)
                        q = self._vessel_q.setdefault(nid, {"in": 0.0, "out": 0.0})
                        q["in"] = q.get("in", 0.0) + max(0.0, r["flow"])
            rv = tree.get("root_vessel")
            if rv:
                r = solved.get(rv)
                if r is not None:
                    self._vessel_active.add(rv)
                    q = self._vessel_q.setdefault(rv, {"in": 0.0, "out": 0.0})
                    q["out"] = max(0.0, r["flow"])
                    # A separator / tank is not handled by the ELOU/column
                    # branches below, so the drain-line flow must reach the
                    # level balance here.  Without it _integrate_levels reads
                    # q_out = 0 and the level can only rise.
                    self._vessel_q_out[rv] = q["out"]
            result.update(solved)
        for nid in self._vessel_active:
            vs = self._vessel_state.get(nid)
            q = self._vessel_q.get(nid)
            if vs is None or q is None:
                continue
            result[nid] = {"flow": q["out"], "p_in": vs["p_out"], "p_out": vs["p_out"]}
        return result

    # ------------------------------------------------------------------
    # Water-hammer surge check (ТЗ section 36)
    # ------------------------------------------------------------------

    def _check_water_hammer(self, eq_outputs: Dict[str, Any]) -> List[ErrorEvent]:
        """Detect rapid valve closures and evaluate the Joukowsky surge.

        A valve that closes by more than ``_surge_close_threshold`` in one step
        and cuts a real flow triggers a surge evaluation against the pipe MAOP.
        MEDIUM/HIGH-risk surges become operator-error events (once per closure,
        not every step), so the check never spams the event log.
        """
        import math
        from physics.water_hammer import surge_risk
        events: List[ErrorEvent] = []
        density = 850.0
        for nid, out in eq_outputs.items():
            node = self._node_map.get(nid)
            if node is None or node.type not in _CONTROL_VALVE_TYPES:
                continue
            eq = self._equipment.get(nid)
            if eq is None:
                continue
            pos = float(getattr(eq, "position", 0.0))
            prev_pos = self._prev_valve_positions.get(nid, pos)
            self._prev_valve_positions[nid] = pos
            close_delta = prev_pos - pos
            if close_delta < self._surge_close_threshold:
                continue
            prev_flow = float(self._last_outputs.get(nid, {}).get("flow_out", 0.0))
            cur_flow = float(out.get("flow_out", 0.0))
            if prev_flow <= 1e-9:
                continue
            diam = float(node.params.get("diameter_m", 0.1))
            area = math.pi * diam * diam / 4.0
            v_prev = prev_flow / (density * area)
            v_cur = max(0.0, cur_flow) / (density * area)
            dv = max(0.0, v_prev - v_cur)
            if dv <= 1e-9:
                continue
            maop = float(node.params.get("maop_pa", 1e6))
            p_nom = float(node.params.get("pressure_bar", 1.01325)) * 1e5
            risk = surge_risk(p_nom, dv, maop, density=density, damping=0.9)
            band = risk["risk_band"]
            if band not in ("MEDIUM", "HIGH"):
                continue
            tag = f"{nid}:surge"
            if tag in self._last_surge_alerts:
                continue
            self._last_surge_alerts[tag] = self._time
            events.append(ErrorEvent(
                error_type="SURGE_RISK",
                severity=Severity.CRITICAL if band == "HIGH" else Severity.HIGH,
                timestamp=self._time,
                operator_action=f"SET_VALUE on {nid} (fast closure)",
                expected_action="Slow valve closure (ramp) to limit surge",
                cause=(f"Rapid closure of {nid} cut the flow by "
                       f"{dv:.2f} m/s in one step"),
                consequence=(f"Water hammer: P_max {risk['max_surge_pressure_pa']/1e5:.1f} bar "
                             f"vs MAOP {maop/1e5:.1f} bar ({band} risk)"),
            ))
        return events

    @staticmethod
    def _merge_streams(streams: Optional[List["Stream"]]) -> Optional["Stream"]:
        """Merge multiple feeds into one mass-conserving stream.

        All incoming streams are combined: mass flows are summed and
        intensive properties are mass-flow-weighted averaged, so a
        multi-feed column (e.g. K-1, K-9) receives its FULL incoming
        mass instead of silently dropping every feed but the largest.
        """
        from models.stream import Stream
        if not streams:
            return None
        active = [s for s in streams if s is not None and s.mass_flow > 0]
        if not active:
            return streams[0] if streams else None
        if len(active) == 1:
            return active[0]
        total = sum(s.mass_flow for s in active)
        base = active[0]
        components = sorted({c for s in active for c in s.composition})
        composition = {
            c: sum(s.composition.get(c, 0.0) * s.mass_flow for s in active) / total
            for c in components
        }
        return Stream(
            name="Merged",
            temperature=sum(s.temperature * s.mass_flow for s in active) / total,
            pressure=sum(s.pressure * s.mass_flow for s in active) / total,
            mass_flow=total,
            composition=composition,
            phase=base.phase,
            enthalpy=sum(s.enthalpy * s.mass_flow for s in active) / total,
            density=sum(s.density * s.mass_flow for s in active) / total,
            viscosity=sum(s.viscosity * s.mass_flow for s in active) / total,
        )

    def _make_source_stream(self, node: SchemeNode) -> "Stream":
        """Build the boundary Stream produced by a 'source' node."""
        from models.stream import Stream
        if node.id == "src_feed":
            # Prefer the per-node values; the global feed override is the
            # fallback when the node itself carries no flow/temperature/pressure.
            flow = node.params.get("flow_kg_s", self._feed_override.get("flow_kg_s", 100.0))
            temp_c = node.params.get("temperature_c", self._feed_override.get("temperature_c", 25.0))
            press_bar = node.params.get("pressure_bar", self._feed_override.get("pressure_bar", 1.01325))
        else:
            flow = node.params.get("flow_kg_s", 100.0)
            temp_c = node.params.get("temperature_c", 25.0)
            press_bar = node.params.get("pressure_bar", 1.01325)
        # Real petroleum fractions + water + salt (ELOU-AVT crude slate).
        default_composition = {
            "frac_nk62": 0.02, "frac_62_105": 0.04, "frac_105_180": 0.10,
            "frac_180_240": 0.13, "frac_240_300": 0.12, "frac_300_350": 0.10,
            "frac_mazut": 0.45, "water": 0.03, "salt": 0.01,
        }
        composition = node.params.get("composition") or default_composition
        stream = Stream(
            name=node.id,
            temperature=temp_c + 273.15,
            pressure=press_bar * 100000.0,
            mass_flow=flow,
            composition=dict(composition),
        )
        stream.enthalpy = self.thermo.calculate_enthalpy(
            stream.temperature, stream.pressure, stream.composition
        )
        return stream

    def _mixer_back_pressure(
        self, nid: str, hyd: Dict[str, Dict[str, float]]
    ) -> Optional[float]:
        """Pressure a mixer outlet must carry for junction continuity.

        A mixer is a junction: it takes the back-pressure of whatever element is
        first downstream of it that the line solver solved (that element's
        p_in), or the direct sink pressure.  Returns None when no downstream
        anchor exists -- the model then falls back to the lowest feed pressure
        (no feed can push in at a pressure below the junction).
        """
        for edge in self._edges:
            if edge.source != nid:
                continue
            dn = edge.target
            h = hyd.get(dn)
            if h is not None:
                return float(h["p_in"])
            dn_node = self._node_map.get(dn)
            if dn_node is not None and dn_node.type == "sink":
                return float(dn_node.params.get("pressure_bar", 1.01325)) * 1e5
        return None

    def _attach_level(
        self,
        state: SimulationState,
        nid: str,
        node: SchemeNode,
        incoming: Dict[str, List["Stream"]],
        out: Dict[str, Any],
        dt: float,
    ) -> None:
        """Compute a per-node liquid level via material balance (columns/tanks)."""
        from physics.process_physics import material_balance_level
        if node.type not in ("column", "elou", "separator", "tank", "separator_s1k"):
            return
        # Buffer vessels split by the line solver carry the engine's own
        # inventory state (integrated from the solved inflow/outflow).
        if nid in self._vessel_active:
            vs = self._vessel_state.get(nid)
            if vs is not None:
                out["level"] = vs["level"]
                state.level[nid] = vs["level"]
                q = self._vessel_q.get(nid)
                if q is not None:
                    out["in_flow"] = q.get("in", 0.0)
                    out["out_flow"] = q.get("out", 0.0)
                return
        # Equipment with its own level state (buffer tanks) is authoritative.
        if "level" in out:
            state.level[nid] = out["level"]
            return
        inlet = self._merge_streams(incoming.get("in") or incoming.get("cold_in"))
        if node.type == "column":
            # A multi-feed column (K-1 with in/feed1..4/reflux/circ/steam) must
            # balance ALL its incoming ports, not only the main 'in' feed.
            inlet = self._merge_streams(
                [s for lst in incoming.values() for s in lst]
            )
        density = inlet.density if inlet else 850.0
        if node.type == "column":
            dist = out.get("distillate")
            side = out.get("side_draw")
            bott = out.get("bottoms")
            out_flow = ((dist.mass_flow if dist else 0.0)
                        + (side.mass_flow if side else 0.0)
                        + (bott.mass_flow if bott else 0.0))
        elif node.type == "elou":
            s = out.get("outlet_stream")
            brine = out.get("brine_stream")
            out_flow = (s.mass_flow if s else 0.0) + (brine.mass_flow if brine else 0.0)
        else:
            s = out.get("outlet_stream")
            out_flow = s.mass_flow if s else 0.0
        in_flow = inlet.mass_flow if inlet else 0.0
        area = node.params.get("vessel_area", node.params.get("sump_area", 30.0))
        diameter = node.params.get("diameter_m")
        if diameter:
            area = 3.141592653589793 * (float(diameter) / 2.0) ** 2
        height = node.params.get("height_m", 6.0)
        prev = state.level.get(nid, 2.0)
        out["level"] = material_balance_level(
            prev, in_flow / max(density, 1e-6), out_flow / max(density, 1e-6), area, dt,
        )
        # A column is a live inventory boundary: keep its vessel level in step
        # with the integrated bottoms level.  Its pressure is anchored to the
        # downstream product sinks, not to the hydrostatic head.
        if node.type == "column":
            vs = self._vessel_state.get(nid)
            if vs is not None:
                vs["level"] = max(0.0, min(float(out["level"]), vs["height"]))
        # Overflow branch: mass above the vessel height cannot accumulate, so
        # it must leave the vessel (spill / relief) instead of being destroyed.
        if out["level"] > float(height):
            overflow_vol = (out["level"] - float(height)) * area
            out["overflow_mass"] = overflow_vol * density
            out["level"] = float(height)
        out["volume_m3"] = round(area * float(height), 2)

    def _register_node_outputs(self, streams: Dict[str, Any], nid: str, ntype: str, out: Dict[str, Any]) -> None:
        """Store output streams of a node under '<node_id>:<port>' keys."""
        if ntype == "heat_exchanger":
            if out.get("cold_out") is not None:
                streams[f"{nid}:cold_out"] = out["cold_out"]
            if out.get("hot_out") is not None:
                streams[f"{nid}:hot_out"] = out["hot_out"]
        elif ntype == "column":
            if out.get("distillate") is not None:
                streams[f"{nid}:distillate"] = out["distillate"]
            if out.get("side_draw") is not None:
                streams[f"{nid}:side_draw"] = out["side_draw"]
            if out.get("bottoms") is not None:
                streams[f"{nid}:bottoms"] = out["bottoms"]
            # Scheme columns expose section/named ports beyond the three model
            # outputs (K-2/K-3 sections, stabilizer product, circulation).  Map
            # each outgoing scheme port to the matching model product so edges
            # referencing it carry a real stream instead of dying silently.
            for edge in self._edges:
                if edge.source != nid:
                    continue
                port = edge.source_port or "out"
                key = f"{nid}:{port}"
                if key in streams:
                    continue
                p = port.lower()
                if p == "product":
                    src = out.get("bottoms")
                elif p.endswith("_out") or p == "bottoms":
                    src = out.get("bottoms")
                elif p.endswith("_vap") or p == "distillate":
                    src = out.get("distillate")
                elif p.endswith("_liq") or p.startswith("circ") or p == "side_draw":
                    src = out.get("side_draw")
                else:
                    src = out.get("distillate") or out.get("side_draw")
                if src is not None:
                    streams[key] = src
        elif ntype == "elou":
            # ELOU: desalted oil leaves via the right port (oil_out), the
            # salt/water brine via the bottom port (out).
            if out.get("brine_stream") is not None:
                streams[f"{nid}:out"] = out["brine_stream"]
            if out.get("outlet_stream") is not None:
                streams[f"{nid}:oil_out"] = out["outlet_stream"]
        elif ntype == "separator_s1k":
            if out.get("out_t") is not None:
                streams[f"{nid}:out_t"] = out["out_t"]
            if out.get("out_b") is not None:
                streams[f"{nid}:out_b"] = out["out_b"]
        elif ntype == "splitter":
            # Разъединитель публикует по одному потоку на каждую ветвь.
            for i, s in enumerate(out.get("outlet_streams") or []):
                streams[f"{nid}:out{i}"] = s
        elif ntype == "heater":
            # A multi-pass furnace publishes one stream per section outlet.
            for in_port, out_port in self._FURNACE_PORT_PAIRS.items():
                if out.get(out_port) is not None:
                    streams[f"{nid}:{out_port}"] = out[out_port]
        elif out.get("outlet_stream") is not None:
            streams[f"{nid}:out"] = out["outlet_stream"]

    def get_last_outputs(self) -> Dict[str, Any]:
        """Return the equipment outputs of the most recent step (for telemetry)."""
        return self._last_outputs

    def get_last_streams(self) -> Dict[str, Any]:
        """Return the per-port streams of the most recent step (for telemetry)."""
        return self._last_streams

    def _collect_node_params(
        self,
        eq_outputs: Dict[str, Any],
        prev_state: SimulationState,
    ) -> Dict[str, Dict[str, Any]]:
        """Per-node measured parameters (flow, pressure, temperature, level,
        duty, valve position) derived from this step's equipment outputs and
        port streams. Mirrors the live telemetry serializer so history series
        match what the operator sees in the inspector, but computed from the
        physical outputs of the current step rather than the last snapshot."""
        streams = self._last_streams
        equip = self._equipment
        node_params: Dict[str, Dict[str, Any]] = {}

        for nid, node in self._node_map.items():
            ntype = node.type
            out = eq_outputs.get(nid, {})
            eq = equip.get(nid)
            s = out.get("outlet_stream")
            if s is None:
                s = streams.get(f"{nid}:out")

            p: Dict[str, Any] = {}

            if ntype == "pump":
                p["flow_kg_s"] = out.get("flow_out", 0.0)
                p["power_w"] = out.get("power", 0.0)
                p["pressure_bar"] = round(s.pressure / 1e5, 4) if s else None
                p["temperature_c"] = round(s.temperature - 273.15, 3) if s else None
                if eq is not None and getattr(eq, "efficiency", None) is not None:
                    p["efficiency"] = eq.efficiency
                if eq is not None and getattr(eq, "speed", None) is not None:
                    p["speed_rpm"] = round(eq.speed, 1)
            elif ntype in ("valve", "angle_valve"):
                p["position"] = round(out.get("position", 0.0) * 100.0, 2)
                p["flow_kg_s"] = out.get("flow_out", 0.0)
                if out.get("inlet_pressure"):
                    p["pressure_in_bar"] = round(out["inlet_pressure"] / 1e5, 4)
                if out.get("outlet_pressure"):
                    p["pressure_out_bar"] = round(out["outlet_pressure"] / 1e5, 4)
            elif ntype == "gate_valve":
                p["flow_kg_s"] = round(out.get("flow_out", 0.0), 3)
                p["blocked"] = bool(out.get("blocked", False))
            elif ntype in ("separator", "separator_s1k", "tank"):
                s_ref = s or out.get("out_b") or out.get("out_t")
                p["level_m"] = out.get("level")
                p["in_flow"] = round(out.get("in_flow", 0.0), 3)
                p["out_flow"] = round(out.get("out_flow", 0.0), 3)
                p["flow_kg_s"] = round(out.get("out_flow", 0.0), 3)
                if s_ref is not None:
                    p["pressure_bar"] = round(s_ref.pressure / 1e5, 4)
                    p["temperature_c"] = round(s_ref.temperature - 273.15, 3)
                p["volume_m3"] = out.get("volume_m3")
            elif ntype == "mixer":
                if s is not None:
                    p["flow_kg_s"] = round(s.mass_flow, 3)
                    p["temperature_c"] = round(s.temperature - 273.15, 3)
                    p["pressure_bar"] = round(s.pressure / 1e5, 4)
            elif ntype == "splitter":
                # Телеметрия разъединителя: состояние первой ветви (у всех
                # ветвей общий состав/температура, давление — junction).
                s0 = out.get("out0") or streams.get(f"{nid}:out0")
                if s0 is not None:
                    p["flow_kg_s"] = round(s0.mass_flow, 3)
                    p["temperature_c"] = round(s0.temperature - 273.15, 3)
                    p["pressure_bar"] = round(s0.pressure / 1e5, 4)
            elif ntype == "elou":
                if s is not None:
                    p["flow_kg_s"] = round(s.mass_flow, 3)
                    p["temperature_c"] = round(s.temperature - 273.15, 3)
                    p["pressure_bar"] = round(s.pressure / 1e5, 4)
                if eq is not None and getattr(eq, "power_consumption", None) is not None:
                    p["power_w"] = eq.power_consumption
                p["level_m"] = out.get("level", prev_state.level.get(nid))
                p["volume_m3"] = out.get("volume_m3")
            elif ntype == "heat_exchanger":
                p["duty_w"] = out.get("duty", 0.0)
                for key, raw in (
                    ("t_cold_in_c", "t_cold_in"), ("t_cold_out_c", "t_cold_out"),
                    ("t_hot_in_c", "t_hot_in"), ("t_hot_out_c", "t_hot_out"),
                ):
                    v = out.get(raw)
                    if v is not None:
                        p[key] = round(v - 273.15, 3)
            elif ntype == "heater":
                if eq is not None:
                    p["duty_w"] = getattr(eq, "duty", 0.0)
                    p["fuel_flow"] = getattr(eq, "fuel_flow", 0.0)
                    if getattr(eq, "outlet_temp", None) is not None:
                        p["outlet_temp_c"] = round(eq.outlet_temp - 273.15, 3)
                p["flow_kg_s"] = round(out.get("flow_out", 0.0), 3)
            elif ntype == "column":
                dist = out.get("distillate")
                side = out.get("side_draw")
                bott = out.get("bottoms")
                p["distillate_flow"] = round(dist.mass_flow, 3) if dist else 0.0
                p["side_draw_flow"] = round(side.mass_flow, 3) if side else 0.0
                p["bottoms_flow"] = round(bott.mass_flow, 3) if bott else 0.0
                p["flow_kg_s"] = round(
                    (dist.mass_flow if dist else 0.0)
                    + (side.mass_flow if side else 0.0)
                    + (bott.mass_flow if bott else 0.0), 3)
                if dist is not None:
                    p["top_temp_c"] = round(dist.temperature - 273.15, 3)
                    p["pressure_bar"] = round(dist.pressure / 1e5, 4)
                if bott is not None:
                    p["bottom_temp_c"] = round(bott.temperature - 273.15, 3)
                p["level_m"] = out.get("level", prev_state.level.get(nid))
                p["volume_m3"] = out.get("volume_m3")
            elif ntype == "source":
                if s is not None:
                    p["flow_kg_s"] = round(s.mass_flow, 3)
                    p["temperature_c"] = round(s.temperature - 273.15, 3)
                    p["pressure_bar"] = round(s.pressure / 1e5, 4)
            elif ntype == "sink":
                for edge in self._edges:
                    if edge.target == nid:
                        s_in = streams.get(f"{edge.source}:{edge.source_port}")
                        if s_in is not None:
                            break
                else:
                    s_in = None
                if s_in is not None:
                    p["flow_kg_s"] = round(s_in.mass_flow, 3)
                    p["temperature_c"] = round(s_in.temperature - 273.15, 3)
                    p["pressure_bar"] = round(s_in.pressure / 1e5, 4)

            if p:
                node_params[nid] = p

        return node_params

    def _first_of_type(self, ntype: str) -> Optional[str]:
        """Return the id of the first scheme node of a given type (topo order)."""
        for nid in self._topo_order:
            node = self._node_map.get(nid)
            if node is not None and node.type == ntype:
                return nid
        return None

    def _bind_alarm_nodes(self, alarms: List[Alarm]) -> None:
        """Bind every triggered alarm to a concrete scheme node.

        Per-node parameters already carry a '<node_id>_<quantity>' key, so the
        node is recovered by the longest matching node-id prefix. Aggregate
        parameters (feed_flow, column_*, furnace_*) are bound to the first node
        of the equipment type that produced them, so the mnemo node lights up
        for the object the alarm actually concerns.
        """
        aggregate_map = {
            "feed_flow": ("pump", "elou"),
            "column_pressure": ("column",),
            "column_temperature": ("column",),
            "furnace_temperature": ("heater",),
        }
        node_ids = list(self._node_map.keys())
        for alarm in alarms:
            param = alarm.parameter
            best: Optional[str] = None
            for nid in node_ids:
                if param.startswith(nid + "_") and (best is None or len(nid) > len(best)):
                    best = nid
            if best is None:
                for ntype in aggregate_map.get(param, ()):
                    best = self._first_of_type(ntype)
                    if best is not None:
                        break
            if best is not None:
                alarm.node_id = best

    def _fill_alarm_values(
        self,
        alarm_values: Dict[str, float],
        eq_outputs: Dict[str, Any],
        new_state: SimulationState,
    ) -> None:
        """Add per-node process values for every limit defined on the scheme."""
        for nid, node in self._node_map.items():
            out = eq_outputs.get(nid, {})
            ntype = node.type
            if ntype == "column":
                dist = out.get("distillate")
                bott = out.get("bottoms")
                if dist is not None:
                    if f"{nid}_pressure" in self._alarm_setpoints:
                        alarm_values[f"{nid}_pressure"] = dist.pressure
                    if f"{nid}_temperature_top" in self._alarm_setpoints:
                        alarm_values[f"{nid}_temperature_top"] = dist.temperature
                if bott is not None and f"{nid}_temperature_bottom" in self._alarm_setpoints:
                    alarm_values[f"{nid}_temperature_bottom"] = bott.temperature
                if f"{nid}_level" in self._alarm_setpoints:
                    alarm_values[f"{nid}_level"] = out.get("level", new_state.level.get(nid, 2.0))
            elif ntype in ("elou", "separator", "separator_s1k", "tank"):
                s = out.get("outlet_stream") or out.get("out_b") or out.get("out_t")
                if s is not None:
                    if f"{nid}_pressure" in self._alarm_setpoints:
                        alarm_values[f"{nid}_pressure"] = s.pressure
                    if f"{nid}_temperature" in self._alarm_setpoints:
                        alarm_values[f"{nid}_temperature"] = s.temperature
                if f"{nid}_level" in self._alarm_setpoints:
                    alarm_values[f"{nid}_level"] = out.get("level", new_state.level.get(nid, 2.0))
            elif ntype == "heater":
                s = out.get("out") or out.get("outlet_stream")
                if s is not None and f"{nid}_temperature" in self._alarm_setpoints:
                    alarm_values[f"{nid}_temperature"] = s.temperature

    def _build_state(
        self,
        prev_state: SimulationState,
        eq_outputs: Dict[str, Any],
        dt: float,
    ) -> SimulationState:
        """Assemble new SimulationState from equipment outputs.

        The primary aggregates (feed flow, column pressure/temperature, levels)
        are derived from the first equipment of each type in topological order,
        so the engine works with any P&ID scheme, not just the demo layout.
        """
        def out_of(ntype: str) -> Dict[str, Any]:
            nid = self._first_of_type(ntype)
            return eq_outputs.get(nid, {}) if nid else {}

        col = out_of("column")
        furnace = out_of("heater")
        hx = out_of("heat_exchanger")
        elou = out_of("elou")
        p101 = out_of("pump")
        fv101 = out_of("valve")

        # Extract Stream objects
        s_elou = elou.get("outlet_stream")
        s_col_dist = col.get("distillate")
        s_col_side = col.get("side_draw")
        s_col_bott = col.get("bottoms")
        s_furnace = furnace.get("out") or furnace.get("outlet_stream")

        feed_flow = s_elou.mass_flow if s_elou else 0.0
        product_flow = ((s_col_dist.mass_flow if s_col_dist else 0.0)
                        + (s_col_side.mass_flow if s_col_side else 0.0)
                        + (s_col_bott.mass_flow if s_col_bott else 0.0))

        # Dynamic column pressure from actual process stream (stream-derived, not hardcoded).
        column_pressure = s_col_dist.pressure if s_col_dist else prev_state.pressure.get("column", 101325.0)

        # Dynamic levels via material balance: dL/dt = (Q_in - Q_out) / A.
        # Per-node levels are computed in _step_equipment (_attach_level);
        # aggregate keys are kept for the demo trend charts.
        level_by_node: Dict[str, float] = {}
        for nid in self._topo_order:
            node = self._node_map.get(nid)
            if node is None or node.type not in ("column", "elou", "separator", "separator_s1k"):
                continue
            level_by_node[nid] = eq_outputs.get(nid, {}).get(
                "level", prev_state.level.get(nid, 2.0)
            )
        elou_nid = self._first_of_type("elou")
        col_nid = self._first_of_type("column")
        level_elou = level_by_node.get(elou_nid, prev_state.level.get("elou", 2.0)) if elou_nid else prev_state.level.get("elou", 2.0)
        level_column = level_by_node.get(col_nid, prev_state.level.get("column", 2.0)) if col_nid else prev_state.level.get("column", 2.0)

        equipment_states = {
            eid: {
                "failed": eq.state.failed,
                "failure_mode": eq.state.failure_mode,
                "running": eq.state.running,
            }
            for eid, eq in self._equipment.items()
        }

        pump_states = {}
        valve_positions = {}
        for nid in self._topo_order:
            node = self._node_map.get(nid)
            if node is None:
                continue
            if node.type == "pump":
                pump_states[nid] = eq_outputs.get(nid, {}).get("running", False)
            elif node.type in _CONTROL_VALVE_TYPES:
                valve_positions[nid] = eq_outputs.get(nid, {}).get("position", 0.0)
        if not pump_states:
            pump_states = {"pump_P101": p101.get("running", False), "pump_P102": False}
        if not valve_positions:
            valve_positions = {"valve_FV101": fv101.get("position", 0.0)}

        return SimulationState(
            timestamp=self._time,
            pressure={
                "feed_line": s_elou.pressure if s_elou else 101325.0,
                "column":    column_pressure,
            },
            temperature={
                "feed":           prev_state.temperature.get("feed", 298.15),
                "preheat_outlet": hx.get("t_cold_out", 298.15),
                "furnace_outlet": s_furnace.temperature if s_furnace else 298.15,
                "column":         s_col_dist.temperature if s_col_dist else 298.15,
            },
            feed_flow=feed_flow,
            product_flow=product_flow,
            level={
                "elou":   level_elou,
                "column": level_column,
                **level_by_node,
            },
            heat_duty={
                "furnace": furnace.get("duty", 0.0),
                "hx_E101": hx.get("duty", 0.0),
            },
            pump_states=pump_states,
            valve_positions=valve_positions,
            equipment_states=equipment_states,
            node_params=self._collect_node_params(eq_outputs, prev_state),
            alarms=list(prev_state.alarms),
            active_failures=list(self._active_failures),
            errors=list(prev_state.errors),
        )

    # ------------------------------------------------------------------
    # Operator action dispatch
    # ------------------------------------------------------------------

    def _apply_action(
        self,
        action: OperatorAction,
        state: SimulationState,
    ) -> Optional[ErrorEvent]:
        """Apply operator action to target equipment."""
        eq = self._equipment.get(action.equipment_id)
        if eq is None:
            logger.warning("Unknown equipment: %s", action.equipment_id)
            return None
        eq.apply_action(action.action_type, action.new_value)
        return self._error_tracker.evaluate_action(action, state)

    # ------------------------------------------------------------------
    # Failure injection
    # ------------------------------------------------------------------

    def inject_failure(self, equipment_id: str, failure_mode: str) -> None:
        """Inject a failure into a specific equipment."""
        eq = self._equipment.get(equipment_id)
        if eq:
            eq.inject_failure(failure_mode)
            failure_tag = f"{equipment_id}:{failure_mode}"
            if failure_tag not in self._active_failures:
                self._active_failures.append(failure_tag)
            logger.warning("Failure injected: %s -> %s", equipment_id, failure_mode)

    # ------------------------------------------------------------------
    # Scenario event processing
    # ------------------------------------------------------------------

    def process_scenario_events(self, events: List[ScenarioEvent]) -> None:
        """Process scheduled scenario events at current simulation time."""
        for event in events:
            if abs(event.timestamp - self._time) < self.config.dt / 2.0:
                self._dispatch_scenario_event(event)

    def _dispatch_scenario_event(self, event: ScenarioEvent) -> None:
        if event.event_type == "INJECT_FAILURE":
            self.inject_failure(event.target_id, event.parameters.get("failure_mode", ""))
        elif event.event_type == "SET_PARAM":
            eq = self._equipment.get(event.target_id)
            if eq:
                value = event.parameters.get("fuel_flow") or event.parameters.get("flow")
                eq.apply_action("SET_VALUE", value)
        elif event.event_type == "SET_STATE":
            eq = self._equipment.get(event.target_id)
            if eq:
                eq.apply_action(event.parameters.get("state", "TURN_ON"),
                                event.parameters.get("value"))
        elif event.event_type == "RAISE_ALARM":
            params = event.parameters
            self._alarm_system.register_custom_alarm(
                timestamp=self._time,
                parameter=params.get("param", "scenario_alarm"),
                actual_value=params.get("value", 1.0),
                threshold=params.get("threshold", 0.0),
                severity=params.get("severity", "HIGH"),
                description=params.get("description", "Авария по сценарию"),
            )
        logger.info("Scenario event dispatched: %s on %s", event.event_type, event.target_id)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_history(self) -> List[SimulationState]:
        return [copy.deepcopy(s) for s in self._history]

    def get_alarms(self) -> List[Alarm]:
        return self._alarm_system.get_active_alarms()

    def get_events(self) -> List[ErrorEvent]:
        return self._error_tracker.get_events()

    def get_current_state(self) -> SimulationState:
        return self._state

    def register_expected_action(self, expected: ExpectedAction) -> None:
        self._error_tracker.register_expected(expected)

    def reset(self) -> None:
        """Full reset of engine to initial state."""
        self._time = 0.0
        self._history.clear()
        self._hyd_state.clear()
        self._vessel_state.clear()
        self._vessel_q.clear()
        self._vessel_q_in.clear()
        self._vessel_q_out.clear()
        self._vessel_active.clear()
        self._active_failures.clear()
        self._alarm_system.reset()
        self._error_tracker.reset()
        for eq in self._equipment.values():
            eq.reset()
        self._state = self._build_initial_state()
        logger.info("SimulationEngine reset.")
