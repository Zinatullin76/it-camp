"""
pump.py
=======
Rigorous centrifugal pump model with energy balance and Stream interface.
"""

from typing import Dict, Any, Optional
from .base_equipment import BaseEquipment, EquipmentState
from models.stream import Stream, Phase

class Pump(BaseEquipment):
    """
    Centrifugal pump with efficiency, power and variable rotation speed.

    The rotation speed (``speed``, RPM) follows the affinity laws: the mass
    capacity scales linearly with the speed ratio, the delivered head scales
    with its square.  This couples the pump to the rest of the system — slowing
    a pump reduces the flow its line can carry and the pressure it develops.
    """

    def __init__(self, equipment_id: str, params: Optional[Dict[str, Any]] = None):
        super().__init__(equipment_id, params or {})
        self.power = 0.0
        self._apply_params()
        self.speed = self.nominal_speed

    @property
    def speed_ratio(self) -> float:
        """Rotation speed relative to the nominal speed, clamped to [0, 2]."""
        return max(0.0, min(2.0, self.speed / max(self.nominal_speed, 1.0)))

    def _apply_params(self) -> None:
        self.nominal_flow = self.params.get("nominal_flow", 0.1)
        self.nominal_head = self.params.get("nominal_head", 50.0)
        self.efficiency = self.params.get("efficiency_nominal", 0.75)
        self.nominal_speed = max(1.0, float(self.params.get("nominal_speed", 1450.0)))

    def current_capacity(self, density: float = 850.0) -> float:
        """Mass-flow capacity at the current rotation speed [kg/s].

        Used by the flow-limits pass: a running pump throttles its line to the
        capacity of the current speed (a stopped or failed pump dead-heads it).
        """
        if not (self.state.running and not self.state.failed):
            return 0.0
        return max(0.0, self.nominal_flow * self.speed_ratio)

    def step(self, dt: float, **inputs) -> Dict[str, Any]:
        inlet: Stream = inputs.get("inlet_stream")
        delta_p = inputs.get("delta_p", 1e5)
        sr = self.speed_ratio
        failed = self.state.failed
        running = self.state.running and not failed
        if not running:
            self.power = 0.0
            zero_flow = 0.0
            outlet = inlet.copy_with(mass_flow=zero_flow) if inlet else None
            return {"outlet_stream": outlet, "flow_out": zero_flow, "power": 0.0, "running": False, "failed": failed}

        # Effective head follows the affinity law: H ~ n^2.
        eff_dp = delta_p * sr * sr

        # Standalone unit tests and demo use nominal pump capacity when no inlet stream is supplied.
        if inlet is None:
            flow = self.nominal_flow * self.efficiency * sr
            if self.state.failure_mode == "CAVITATION":
                flow *= 0.5
            return {"outlet_stream": None, "flow_out": flow, "power": flow * eff_dp / max(self.efficiency, 1e-6), "running": True, "failed": False}

        cap = self.current_capacity()
        flow = min(inlet.mass_flow, cap) if inlet.mass_flow > 0 else 0.0
        if self.state.failure_mode == "CAVITATION":
            flow *= 0.5
        vol_flow = flow / inlet.density
        self.power = (vol_flow * eff_dp) / max(self.efficiency, 1e-6)
        work_per_mass = self.power / max(flow, 1e-9)
        outlet = inlet.copy_with(pressure=inlet.pressure + eff_dp, mass_flow=flow, enthalpy=inlet.enthalpy + work_per_mass)
        return {"outlet_stream": outlet, "flow_out": outlet.mass_flow, "power": self.power, "running": True, "failed": False}

    def get_state(self) -> EquipmentState:
        self.state.extra["power"] = self.power
        self.state.extra["speed_rpm"] = self.speed
        self.state.extra["speed_ratio"] = self.speed_ratio
        return self.state

    def apply_action(self, action_type: str, value: Optional[float] = None) -> None:
        if action_type == "TURN_ON":
            self.state.running = True
        elif action_type == "TURN_OFF":
            self.state.running = False
        elif action_type == "EMERGENCY_STOP":
            self.state.running = False
        elif action_type == "SET_SPEED" and value is not None:
            self.speed = max(0.0, min(2.0 * self.nominal_speed, float(value)))

    def reset(self) -> None:
        super().reset()
        self.power = 0.0
        self.speed = self.nominal_speed
