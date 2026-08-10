"""
valve.py
========
Rigorous control valve model with pressure drop and Stream interface.
"""

from typing import Dict, Any, Optional
from .base_equipment import BaseEquipment, EquipmentState
from models.stream import Stream
from calculation_core.hydraulics.pressure_drop import calculate_valve_flow

# Default valve opening when a scheme carries no explicit initial_position.
# 0.7 = 70% (operator requirement: control valves start open enough to pass
# the feed, so a scheme that does not configure its valves is not dead-headed).
DEFAULT_POSITION = 0.7

class Valve(BaseEquipment):
    """
    Control valve with pressure drop calculation.
    """

    def __init__(self, equipment_id: str, params: Optional[Dict[str, Any]] = None):
        super().__init__(equipment_id, params or {})
        init_pos = self.params.get("initial_position", self.params.get("valve_position"))
        self.position = 0.0
        self._position = 0.0
        self.target_position = 0.0
        if init_pos is not None:
            self.position = self._position = self.target_position = max(0.0, min(1.0, float(init_pos)))
        else:
            self.position = self._position = self.target_position = DEFAULT_POSITION
        self._apply_params()

    def _apply_params(self) -> None:
        self.cv = self.params.get("cv", self.params.get("flow_coefficient_si", 0.01))
        self.response_rate = self.params.get("response_rate", 0.4)
        self.legacy_constant = self.params.get("valve_constant")

    def step(self, dt: float, **inputs) -> Dict[str, Any]:
        inlet: Stream = inputs.get("inlet_stream")
        if self.state.failed:
            return {"outlet_stream": inlet, "position": self.position, "flow_out": inlet.mass_flow if inlet else 0.0, "failed": True}
        diff = self.target_position - self.position
        move = self.response_rate * dt
        if abs(diff) <= move: self.position = self.target_position
        else: self.position += move * (1 if diff > 0 else -1)
        self.position = max(0.0, min(1.0, self.position))
        self._position = self.position
        if inlet is None:
            # Legacy scalar API had no upstream process stream; treat an
            # unconfigured valve as closed rather than fabricating flow.
            if not self.params:
                return {"outlet_stream": None, "position": self.position, "flow_out": 0.0}
            delta_p = max(0.0, inputs.get("delta_p", 1e4))
            flow_out = calculate_valve_flow(self.cv, self.position, delta_p, 850.0)
            return {"outlet_stream": None, "position": self.position, "flow_out": flow_out}

        # Legacy isolated-equipment contract.  Keep it deterministic for old
        # scenarios/tests while process schemes use the SI-Cv branch below.
        if self.legacy_constant is not None:
            k = max(float(self.legacy_constant), 1e-12)
            available_dp = max(0.0, float(inlet.pressure))
            mass_flow = min(inlet.mass_flow, k * self.position * available_dp ** 0.5)
            pressure_drop = min(available_dp, (mass_flow / k) ** 2)
            outlet = inlet.copy_with(
                pressure=max(1000.0, inlet.pressure - pressure_drop),
                mass_flow=mass_flow,
            )
            blocked = self.position <= 1e-9 or mass_flow <= 1e-12
            if blocked:
                outlet = inlet.copy_with(mass_flow=0.0)
                pressure_drop = 0.0
            return {
                "outlet_stream": outlet,
                "position": self.position,
                "flow_out": mass_flow,
                "mass_flow_kg_s": mass_flow,
                "pressure_drop_pa": pressure_drop,
                "blocked": blocked,
            }
        design_dp = self.params.get("design_delta_p", 2e5)
        # Restriction grows as the valve closes below its normal opening. At
        # the normal position there is no extra pressure loss (nominal dP);
        # closing all the way imposes the full design drop (dead-heading).
        nominal = max(0.0, self.params.get("initial_position", DEFAULT_POSITION) or 0.0)
        if nominal > 1e-6:
            restriction = min(1.0, max(0.0, (nominal - self.position) / nominal))
        else:
            restriction = 0.0
        if self.params.get("flow_controller"):
            # Flow-control valve: passes the incoming feed, throttled only
            # by its full-open capacity (operator feed change propagates).
            cap_mass = calculate_valve_flow(self.cv, 1.0, design_dp, inlet.density) * inlet.density
        else:
            cap_mass = calculate_valve_flow(self.cv, self.position, design_dp, inlet.density) * inlet.density
        mass_flow = min(cap_mass, inlet.mass_flow)
        # A flowing control valve always throttles at least a small base
        # drop (seat/piping restriction); closing it grows the drop up to
        # the design value.
        base_dp = 0.05 * design_dp
        dp = base_dp + design_dp * restriction
        # Continuous-line model: the valve passes the incoming pressure through
        # and drops it by its throttling loss, so the outlet pressure of one
        # node matches the inlet pressure of the next one downstream.
        out_pressure = max(1000.0, inlet.pressure - dp)
        outlet = inlet.copy_with(pressure=out_pressure, mass_flow=mass_flow)
        return {
            "outlet_stream": outlet,
            "position": self.position,
            "flow_out": mass_flow,
            "mass_flow_kg_s": mass_flow,
            "pressure_drop_pa": dp,
            "inlet_pressure": inlet.pressure,
            "outlet_pressure": out_pressure,
            "dp": dp,
            "throttle": restriction,
            "blocked": self.position <= 1e-6 and mass_flow <= 1e-9,
        }

    def current_capacity(self, density: float = 850.0) -> float:
        """Mass-flow capacity at the current opening for the design drop.

        Used to dead-head the upstream line: the capacity follows the valve's
        live position, so closing throttles/isolates the line and reopening
        restores it (no dependence on the previous step's throughput).
        """
        if self.position <= 1e-6:
            return 0.0
        design_dp = self.params.get("design_delta_p", 2e5)
        opening = 1.0 if self.params.get("flow_controller") else self.position
        return calculate_valve_flow(self.cv, opening, design_dp, density) * density

    def draw_capacity(self, level_m: float, density: float = 850.0,
                      dp_extra: float = 0.0) -> float:
        """Column-bottom draw through the valve from the true dp across it.

        Q = Cv·x·sqrt(dP/ρ)·ρ.  The pressure upstream of the sump valve is the
        column pressure plus the static head rho*g*h of the liquid above it, and
        downstream is the receiving sink pressure; dp_extra carries the column-
        to-sink pressure difference, so the driving force is
        dP = rho*g*h + dp_extra.  An emptied sump cannot be drawn, and a deeper
        sump draws more -- the level settles where this equals the MESH bottoms
        inflow.
        """
        if self.position <= 1e-6 or level_m <= 1e-9:
            return 0.0
        opening = 1.0 if self.params.get("flow_controller") else self.position
        head_dp = max(density, 1e-9) * 9.81 * max(0.0, level_m)
        dp = max(0.0, head_dp + dp_extra)
        return calculate_valve_flow(self.cv, opening, dp, density) * density

    def get_state(self) -> EquipmentState:
        self.state.extra["position"] = self.position
        return self.state

    def apply_action(self, action_type: str, value: Optional[float] = None) -> None:
        if action_type == "SET_VALUE" and value is not None:
            self.target_position = max(0.0, min(1.0, value))
        elif action_type == "TURN_OFF":
            self.target_position = 0.0
        elif action_type == "TURN_ON":
            self.target_position = 1.0

    def reset(self) -> None:
        super().reset()
        init_pos = self.params.get("initial_position", self.params.get("valve_position"))
        self.position = self._position = self.target_position = 0.0
        if init_pos is not None:
            self.position = self._position = self.target_position = max(0.0, min(1.0, float(init_pos)))
        else:
            self.position = self._position = self.target_position = DEFAULT_POSITION


class AngleValve(Valve):
    """
    Angle valve (угловой клапан) — a control valve with adjustable opening.

    Behaves exactly like a regular control valve (position set via
    apply_action("SET_VALUE"), throttling, dead-heading), but defaults to
    the standard DEFAULT_POSITION when no initial_position is configured,
    so adding it to a scheme does not silently dead-head the line.
    """

    def __init__(self, equipment_id: str, params: Optional[Dict[str, Any]] = None):
        params = dict(params or {})
        if "initial_position" not in params:
            params["initial_position"] = DEFAULT_POSITION
        super().__init__(equipment_id, params)
