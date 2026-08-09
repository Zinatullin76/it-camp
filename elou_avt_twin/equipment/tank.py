"""
tank.py
=======
Simple MVP buffer tank (settler / feed tank) with a real material balance:
  level_new = level + (m_in - m_out) / (rho * area) * dt
and a level controller that sets the outflow:
  m_out = m_in + Kc * (level - setpoint)
At steady state m_out == m_in and the level holds at the setpoint; a change
in the inflow first accumulates in the level, then the outflow ramps to
match it.  Mass is always conserved and the product never disappears.
"""

from typing import Any, Dict, Optional
from .base_equipment import BaseEquipment, EquipmentState
from models.stream import Stream


class Tank(BaseEquipment):
    """
    Buffer / settling tank with level dynamics and mass conservation.
    """

    def __init__(self, equipment_id: str, params: Optional[Dict[str, Any]] = None):
        super().__init__(equipment_id, params or {})
        init_level = self.params.get("initial_level", 2.0)
        self.level = init_level
        self.setpoint = self.params.get("setpoint_level", init_level)
        self.level_controller_auto = self.params.get("level_auto", True)
        self._apply_params()

    def _apply_params(self) -> None:
        diameter = self.params.get("diameter_m")
        if diameter:
            self.area = 3.141592653589793 * (float(diameter) / 2.0) ** 2
        else:
            self.area = self.params.get("vessel_area", self.params.get("sump_area", 30.0))
        self.height = self.params.get("height_m", 6.0)
        self.volume = self.area * self.height
        self.gain = self.params.get("level_gain", 50.0)
        self.pressure = self.params.get("nominal_pressure", None)
        if "setpoint_level" in self.params:
            self.setpoint = max(0.0, float(self.params["setpoint_level"]))

    def step(self, dt: float, **inputs) -> Dict[str, Any]:
        inlet: Stream = inputs.get("inlet_stream")
        # Downstream restriction: the tank may push out at most this much, the
        # excess accumulates in the level (blocked/dead-headed line).
        max_out = inputs.get("max_out")
        # The vessel's own operating pressure (base + hydrostatic head), the
        # same pressure the upstream line pushes against.  Keeps the outlet
        # continuous with the inlet even outside a solved hydraulic line.
        vessel_pressure = inputs.get("vessel_pressure")
        if inlet is None:
            return {"outlet_stream": None, "level": self.level, "setpoint": self.setpoint}

        rho = inlet.density if inlet.density and inlet.density > 0 else 850.0
        m_in = max(0.0, inlet.mass_flow)

        if self.state.failed:
            return {"outlet_stream": inlet, "level": self.level, "setpoint": self.setpoint}

        # Level controller: pass the inflow, corrected by the level deviation
        # (in AUTO).  A high level pushes more out, a low level holds back.
        if self.level_controller_auto:
            m_out = m_in + self.gain * (self.level - self.setpoint)
        else:
            m_out = m_in
        if max_out is not None:
            m_out = min(m_out, max_out)
        m_out = max(0.0, m_out)

        # Material balance: accumulation = in - out.
        level_new = self.level + (m_in - m_out) / max(rho * self.area, 1e-6) * dt
        # Overflow: mass above the tank height cannot accumulate, so it must
        # leave the vessel (spill / relief to the downstream) — otherwise the
        # balance would silently destroy mass.
        overflow_mass = 0.0
        if level_new > self.height:
            overflow_mass = (level_new - self.height) * rho * self.area
            m_out += overflow_mass
            level_new = self.height
        level_new = max(0.0, level_new)
        self.level = level_new

        out_pressure = vessel_pressure or self.pressure or inlet.pressure
        outlet = inlet.copy_with(
            name="TankOut",
            pressure=out_pressure,
            mass_flow=m_out,
            temperature=inlet.temperature,
        )
        return {
            "outlet_stream": outlet,
            "level": self.level,
            "setpoint": self.setpoint,
            "volume_m3": round(self.area * self.height, 2),
            "in_flow": m_in,
            "out_flow": m_out,
            "overflow_mass": overflow_mass,
        }

    def get_state(self) -> EquipmentState:
        self.state.extra["level"] = self.level
        self.state.extra["setpoint"] = self.setpoint
        return self.state

    def apply_action(self, action_type: str, value: Optional[float] = None) -> None:
        if action_type == "SET_VALUE" and value is not None:
            self.setpoint = max(0.0, value)
        elif action_type == "SET_LEVEL" and value is not None:
            self.setpoint = max(0.0, value)
        elif action_type == "TURN_ON":
            self.level_controller_auto = True
        elif action_type == "TURN_OFF":
            self.level_controller_auto = False

    def reset(self) -> None:
        super().reset()
        init_level = self.params.get("initial_level", 2.0)
        self.level = init_level
        self.setpoint = self.params.get("setpoint_level", init_level)
        self.level_controller_auto = self.params.get("level_auto", True)
