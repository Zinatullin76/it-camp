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
from typing import Dict, List, Optional, Any

from models.base import (
    SimulationState,
    SimulationConfig,
    OperatorAction,
    Alarm,
    ErrorEvent,
)
from models.scenario import Scenario, ScenarioEvent
from equipment import (
    Pump, Valve, Heater, HeatExchanger, DistillationColumn, ELOU, Tank,
)
from scheme import ProcessScheme, SchemeNode, load_scheme
from safety.alarm_system import AlarmSystem
from events.error_tracker import ErrorTracker, ExpectedAction

logger = logging.getLogger("elou_avt.engine")


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
        self._last_outputs: Dict[str, Any] = {}
        self._last_streams: Dict[str, Any] = {}
        self._alarm_setpoints: Dict[str, Any] = {}
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
            "column_C101": DistillationColumn("column_C101", ep.get("column_C101", {})),
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
            elif node.type == "valve":
                valve_positions.setdefault(nid, 0.0)
            elif node.type in ("column", "elou", "separator"):
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

        # 4. Build new state
        new_state = self._build_state(state, eq_outputs, dt)
        new_state.timestamp = self._time
        new_state.errors = list(state.errors) + new_errors
        new_state.active_failures = list(self._active_failures)

        # 5. Evaluate alarms
        alarm_values: Dict[str, float] = {"feed_flow": new_state.feed_flow}
        if not self._has_scheme_limits:
            # Demo/deprecated aggregates, used when a scheme carries no limits.
            alarm_values.update({
                "column_pressure": new_state.pressure.get("column", 0.0),
                "column_temperature": new_state.temperature.get("column", 0.0),
                "furnace_temperature": new_state.temperature.get("furnace_outlet", 0.0),
            })
        self._fill_alarm_values(alarm_values, eq_outputs, new_state)
        new_alarms = self._alarm_system.evaluate(self._time, alarm_values)
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
        # Downstream valves limit the flow of their exclusive upstream line
        # (previous step's valve throughput). The source itself is a fixed
        # flow boundary and is never clamped; restrictions make the equipment
        # upstream hold back flow (levels/pressures respond instead).
        flow_limits = self._compute_flow_limits(self._last_outputs)
        hyd = self._solve_line_hydraulics()

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
                        branch = base.copy_with(
                            name=f"{base.name}:{edge.target}",
                            mass_flow=base.mass_flow / n_cons,
                        )
                    else:
                        branch = base
                    incoming.setdefault(edge.target_port or "in", []).append(branch)
            if not incoming:
                continue  # isolated node or upstream data not ready

            eq = self._equipment.get(nid)
            out: Dict[str, Any] = {}
            if eq is None:
                # Unknown equipment types (separator, ...) act as pass-through.
                inlet = self._merge_streams(incoming.get("in") or incoming.get("cold_in"))
                if inlet is not None:
                    out = {"outlet_stream": inlet}
            elif ntype == "pump":
                inlet = self._merge_streams(incoming.get("in"))
                if inlet is None:
                    continue
                out = eq.step(dt, inlet_stream=inlet, delta_p=node.params.get("delta_p", 5e5))
            elif ntype == "valve":
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
                inlet = self._merge_streams(incoming.get("in"))
                if inlet is None:
                    continue
                out = eq.step(dt, inlet_stream=inlet, thermo=self.thermo)
            elif ntype == "column":
                feed = self._merge_streams(incoming.get("in"))
                if feed is None:
                    continue
                out = eq.step(dt, feed_stream=feed, thermo=self.thermo)
            elif ntype in ("separator", "tank"):
                inlet = self._merge_streams(incoming.get("in"))
                if inlet is None:
                    continue
                out = eq.step(dt, inlet_stream=inlet, max_out=flow_limits.get(nid))
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
            if h is not None:
                os_ = out.get("outlet_stream")
                if os_ is not None:
                    out["outlet_stream"] = os_.copy_with(
                        mass_flow=max(0.0, h["flow"]), pressure=h["p_out"]
                    )
                out["flow_out"] = h["flow"]
                if ntype == "valve":
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
            self._attach_level(state, nid, node, incoming, out, dt)
            self._register_node_outputs(streams, nid, ntype, out)

        # Back-pressure feedback: a throttling valve raises the pressure on its
        # inlet (dead-heading). Propagate that rise to the equipment feeding it
        # so the upstream shows the raised pressure instead of the nominal one.
        # The rise travels all the way back up the train (pumps, heaters, ...)
        # to the source, so the whole line responds to one valve change.
        for nid, out in outputs.items():
            node = self._node_map.get(nid)
            if node is None or node.type != "valve":
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
        from safety.alarm_system import AlarmSetpoint, DEFAULT_SETPOINTS
        setpoints: Dict[str, AlarmSetpoint] = dict(DEFAULT_SETPOINTS)
        measured: Dict[str, int] = {}
        for node in scheme.nodes:
            limits = node.params.get("limits")
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
        self._alarm_setpoints = setpoints
        self._measured_params = measured
        self._has_scheme_limits = any(
            isinstance(n.params.get("limits"), dict) for n in scheme.nodes
        )
        self._alarm_system.configure(setpoints)

    def _extend_equipment_from_scheme(self, scheme: ProcessScheme) -> None:
        """Create equipment instances for scheme nodes of supported types."""
        for node in scheme.nodes:
            if node.id in self._equipment or node.type in ("source", "sink"):
                continue
            if node.type == "pump":
                self._equipment[node.id] = Pump(node.id, node.params)
            elif node.type == "valve":
                self._equipment[node.id] = Valve(node.id, node.params)
            elif node.type == "elou":
                self._equipment[node.id] = ELOU(node.id, node.params)
            elif node.type == "heat_exchanger":
                self._equipment[node.id] = HeatExchanger(node.id, node.params)
            elif node.type == "heater":
                self._equipment[node.id] = Heater(node.id, node.params)
            elif node.type == "column":
                self._equipment[node.id] = DistillationColumn(node.id, node.params)
            elif node.type == "separator":
                self._equipment[node.id] = Tank(node.id, node.params)

    def _rebuild_topology(self, scheme: ProcessScheme) -> None:
        """Rebuild the node map, edge list and topological order."""
        self._node_map = scheme.node_map()
        self._edges = list(scheme.edges)
        indeg: Dict[str, int] = {nid: 0 for nid in self._node_map}
        for edge in self._edges:
            if edge.target in indeg:
                indeg[edge.target] += 1
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
            if node.type != "valve":
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
            elif node.type == "valve":
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
    # Serial-line hydraulics
    # ------------------------------------------------------------------

    _COMPLEX_NODE_TYPES = ("heat_exchanger", "column", "elou")

    def _build_serial_lines(self) -> List[List[str]]:
        """Split the scheme into simple serial chains source -> ... -> sink.

        A chain is followed forward from a 'source' while every node has
        exactly one feed and one output and is not a complex multi-stream
        device (heat exchanger, column, ELOU).  Such devices break the line.
        """
        indeg: Dict[str, int] = {nid: 0 for nid in self._node_map}
        for edge in self._edges:
            indeg[edge.target] = indeg.get(edge.target, 0) + 1
        lines: List[List[str]] = []
        used: set = set()
        for nid, node in self._node_map.items():
            if node.type != "source" or nid in used:
                continue
            line = [nid]
            cur = nid
            while True:
                outs = [e for e in self._edges if e.source == cur]
                if len(outs) != 1:
                    break
                nxt = outs[0].target
                if nxt in used or nxt not in self._node_map:
                    break
                if self._node_map[nxt].type in self._COMPLEX_NODE_TYPES:
                    break
                if indeg.get(nxt, 0) != 1:
                    break
                line.append(nxt)
                if self._node_map[nxt].type == "sink":
                    break
                cur = nxt
            if len(line) >= 2 and self._node_map[line[-1]].type == "sink":
                lines.append(line)
                used.update(line)
        return lines

    def _solve_line_hydraulics(self) -> Dict[str, Dict[str, float]]:
        """Steady-state hydraulic solution for every serial line.

        Returns per-node data {flow, p_in, p_out} for the nodes of each line,
        so equipment steps can be overwritten with the physically consistent
        mass flow and pressure cascade (dead-head pressure in front of a
        throttling valve, one shared flow through the whole chain).
        """
        from calculation_core.hydraulics.line_hydraulics import solve_serial_line, valve_resistance
        result: Dict[str, Dict[str, float]] = {}
        density = 850.0
        for line in self._build_serial_lines():
            src_id, sink_id = line[0], line[-1]
            p_src = float(self._node_map[src_id].params.get("pressure_bar", 1.01325)) * 1e5
            p_sink = float(self._node_map[sink_id].params.get("pressure_bar", 1.01325)) * 1e5
            q_src_limit = self._node_map[src_id].params.get("flow_kg_s")
            valves: List[tuple] = []
            pump: Optional[str] = None
            for nid in line[1:-1]:
                node = self._node_map[nid]
                if node.type == "valve":
                    eq = self._equipment.get(nid)
                    if eq is None:
                        continue
                    valves.append((nid, valve_resistance(density, eq.cv, eq.position)))
                elif node.type == "pump":
                    pump = nid

            def pump_head(q: float, _pump: Optional[str] = pump) -> float:
                if _pump is None:
                    return 0.0
                eq = self._equipment.get(_pump)
                node = self._node_map.get(_pump)
                if eq is None or node is None or not (eq.state.running and not eq.state.failed):
                    return 0.0
                h_max = float(node.params.get("delta_p", 5e5)) * eq.speed_ratio * eq.speed_ratio
                q_ref = eq.current_capacity()
                if q_ref <= 1e-9:
                    return 0.0
                return h_max * max(0.0, 1.0 - (q / q_ref) ** 2)

            q_ref = 1.0
            if pump is not None:
                eq = self._equipment.get(pump)
                q_ref = eq.current_capacity() if eq is not None else 1.0
            q, dP = solve_serial_line(
                p_src, p_sink, density, valves, pump_head, q_ref, q_src_limit
            )
            P = p_src
            result[src_id] = {"flow": q, "p_in": p_src, "p_out": p_src}
            for nid in line[1:-1]:
                node = self._node_map[nid]
                if node.type == "pump":
                    dp = pump_head(q)
                    result[nid] = {"flow": q, "p_in": P, "p_out": P + dp}
                    P += dp
                elif node.type == "valve":
                    dp = dP.get(nid, 0.0)
                    result[nid] = {"flow": q, "p_in": P, "p_out": P - dp}
                    P -= dp
                else:
                    result[nid] = {"flow": q, "p_in": P, "p_out": P}
            result[sink_id] = {"flow": q, "p_in": P, "p_out": p_sink}
        return result

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
        if node.type not in ("column", "elou", "separator"):
            return
        # Equipment with its own level state (buffer tanks) is authoritative.
        if "level" in out:
            state.level[nid] = out["level"]
            return
        inlet = self._merge_streams(incoming.get("in") or incoming.get("cold_in"))
        density = inlet.density if inlet else 850.0
        if node.type == "column":
            dist = out.get("distillate")
            bott = out.get("bottoms")
            out_flow = (dist.mass_flow if dist else 0.0) + (bott.mass_flow if bott else 0.0)
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
            if out.get("bottoms") is not None:
                streams[f"{nid}:bottoms"] = out["bottoms"]
        elif ntype == "elou" and out.get("brine_stream") is not None:
            if out.get("outlet_stream") is not None:
                streams[f"{nid}:out"] = out["outlet_stream"]
            streams[f"{nid}:brine"] = out["brine_stream"]
        elif out.get("outlet_stream") is not None:
            streams[f"{nid}:out"] = out["outlet_stream"]

    def get_last_outputs(self) -> Dict[str, Any]:
        """Return the equipment outputs of the most recent step (for telemetry)."""
        return self._last_outputs

    def get_last_streams(self) -> Dict[str, Any]:
        """Return the per-port streams of the most recent step (for telemetry)."""
        return self._last_streams

    def _first_of_type(self, ntype: str) -> Optional[str]:
        """Return the id of the first scheme node of a given type (topo order)."""
        for nid in self._topo_order:
            node = self._node_map.get(nid)
            if node is not None and node.type == ntype:
                return nid
        return None

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
                    if f"{nid}_pressure" in self._measured_params:
                        alarm_values[f"{nid}_pressure"] = dist.pressure
                    if f"{nid}_temperature_top" in self._measured_params:
                        alarm_values[f"{nid}_temperature_top"] = dist.temperature
                if bott is not None and f"{nid}_temperature_bottom" in self._measured_params:
                    alarm_values[f"{nid}_temperature_bottom"] = bott.temperature
                if f"{nid}_level" in self._measured_params:
                    alarm_values[f"{nid}_level"] = out.get("level", new_state.level.get(nid, 2.0))
            elif ntype in ("elou", "separator"):
                s = out.get("outlet_stream")
                if s is not None:
                    if f"{nid}_pressure" in self._measured_params:
                        alarm_values[f"{nid}_pressure"] = s.pressure
                    if f"{nid}_temperature" in self._measured_params:
                        alarm_values[f"{nid}_temperature"] = s.temperature
                if f"{nid}_level" in self._measured_params:
                    alarm_values[f"{nid}_level"] = out.get("level", new_state.level.get(nid, 2.0))
            elif ntype == "heater":
                s = out.get("outlet_stream")
                if s is not None and f"{nid}_temperature" in self._measured_params:
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
        s_col_bott = col.get("bottoms")
        s_furnace = furnace.get("outlet_stream")

        feed_flow = s_elou.mass_flow if s_elou else 0.0
        product_flow = (s_col_dist.mass_flow if s_col_dist else 0.0) + (s_col_bott.mass_flow if s_col_bott else 0.0)

        # Dynamic column pressure from actual process stream (stream-derived, not hardcoded).
        column_pressure = s_col_dist.pressure if s_col_dist else prev_state.pressure.get("column", 101325.0)

        # Dynamic levels via material balance: dL/dt = (Q_in - Q_out) / A.
        # Per-node levels are computed in _step_equipment (_attach_level);
        # aggregate keys are kept for the demo trend charts.
        level_by_node: Dict[str, float] = {}
        for nid in self._topo_order:
            node = self._node_map.get(nid)
            if node is None or node.type not in ("column", "elou", "separator"):
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
            elif node.type == "valve":
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
        self._active_failures.clear()
        self._alarm_system.reset()
        self._error_tracker.reset()
        for eq in self._equipment.values():
            eq.reset()
        self._state = self._build_initial_state()
        logger.info("SimulationEngine reset.")
