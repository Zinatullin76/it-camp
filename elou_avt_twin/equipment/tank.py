"""
tank.py
=======
Buffer tank (settler / feed tank) with a real material balance and a physical
drain line:

  dM/dt  = m_in - m_out
  m_out  = min(draw(level), max_out)
  draw   = sqrt(rho*g*h / k_drain)          (static-head drain)

The tank has NO hidden level controller: the outflow is NOT `m_in + Kc*(L-SP)`.
The outflow is set by the static head of the liquid column and the resistance
of the outlet line (k_drain), clamped by the downstream capacity `max_out`.
The level is a consequence of the mass balance: closing a downstream valve
cuts `max_out`, the outflow drops and the level builds up; opening it lets the
level fall.  The drain resistance is calibrated so that at the nominal draw
flow and reference level the line passes exactly the nominal flow.

Mass is always conserved and the product never disappears.
"""

import math
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
        self._drain_k: Optional[float] = None
        self._nominal_draw: Optional[float] = None
        self._apply_params()

    def _apply_params(self) -> None:
        diameter = self.params.get("diameter_m")
        if diameter:
            self.area = 3.141592653589793 * (float(diameter) / 2.0) ** 2
        else:
            self.area = self.params.get("vessel_area", self.params.get("sump_area", 30.0))
        self.height = self.params.get("height_m", 6.0)
        self.volume = self.area * self.height
        self.pressure = self.params.get("nominal_pressure", None)
        if "setpoint_level" in self.params:
            self.setpoint = max(0.0, float(self.params["setpoint_level"]))
        q_nom = self.params.get("nominal_flow") or self.params.get("flow_kg_s")
        if q_nom:
            self._nominal_draw = max(float(q_nom), 1e-3)
        self._drain_k = None

    def _drain_flow(self, level: float, rho: float) -> float:
        """Static-head drain through the outlet line: Q = sqrt(rho*g*h / k)."""
        if level <= 1e-9:
            return 0.0
        if self._drain_k is None or self._nominal_draw is None:
            return 0.0
        head = max(rho * 9.81 * level, 0.0)
        return math.sqrt(head / max(self._drain_k, 1e-12))

    def _calibrate_drain(self, nominal_flow: float, rho: float) -> None:
        """Calibrate the outlet-line resistance at the reference level.

        k_drain = rho*g*h_ref / q_nom^2, so that at h_ref the line passes
        exactly the nominal draw flow.  h_ref is the initial level (the
        operating point the vessel is designed for).
        """
        q_nom = max(float(nominal_flow), 1e-3)
        h_ref = max(float(self.level), 0.2)
        self._drain_k = max(rho * 9.81 * h_ref, 1.0) / max(q_nom * q_nom, 1e-6)
        if self._nominal_draw is None:
            self._nominal_draw = q_nom

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

        # The outlet-line resistance is calibrated once against the nominal
        # flow (explicit param, or the actual operating inflow at start-up).
        if self._drain_k is None:
            self._calibrate_drain(self._nominal_draw or max(m_in, 1e-3), rho)

        # Physical drain: the outflow follows the static head of the liquid
        # column (Q = sqrt(rho*g*h/k_drain)), never a level controller.  An
        # empty vessel cannot be drawn.  The downstream capacity clamps it.
        m_out = self._drain_flow(self.level, rho)
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
            m_out += overflow_mass / max(dt, 1e-9)
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
        # No hidden level controller: setpoint is informational only.
        if action_type in ("SET_VALUE", "SET_LEVEL") and value is not None:
            self.setpoint = max(0.0, value)

    def reset(self) -> None:
        super().reset()
        init_level = self.params.get("initial_level", 2.0)
        self.level = init_level
        self.setpoint = self.params.get("setpoint_level", init_level)
        self._drain_k = None
        self._nominal_draw = None
        q_nom = self.params.get("nominal_flow") or self.params.get("flow_kg_s")
        if q_nom:
            self._nominal_draw = max(float(q_nom), 1e-3)
        self._apply_params()
