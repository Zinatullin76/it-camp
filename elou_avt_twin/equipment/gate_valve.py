"""
gate_valve.py
=============
Gate valve (задвижка) — a binary shut-off element with open/closed state.
"""

from typing import Dict, Any, Optional
from .base_equipment import BaseEquipment, EquipmentState
from models.stream import Stream


class GateValve(BaseEquipment):
    """
    On/off gate valve: either passes the flow through or isolates the line.

    The opening is driven by a stroke rate (response_rate), so the valve
    opens/closes gradually instead of snapping instantly, keeping the
    simulated system inertial like HYSYS Dynamics.
    """

    def __init__(self, equipment_id: str, params: Optional[Dict[str, Any]] = None):
        super().__init__(equipment_id, params or {})
        self._apply_params()

    def _apply_params(self) -> None:
        init = 1.0 if float(self.params.get("initial_open", 1.0)) >= 0.5 else 0.0
        self.opening = init
        self.target_opening = init
        self.stroke_rate = float(self.params.get("response_rate", 0.4))
        self.state.running = self.opening >= 0.5

    @property
    def is_open(self) -> bool:
        return self.opening >= 0.5

    def step(self, dt: float, **inputs) -> Dict[str, Any]:
        if self.state.failed:
            self.opening = 0.0
            self.target_opening = 0.0
            self.state.running = False
        else:
            diff = self.target_opening - self.opening
            move = self.stroke_rate * dt
            if abs(diff) <= move:
                self.opening = self.target_opening
            else:
                self.opening += move * (1 if diff > 0 else -1)
            self.opening = max(0.0, min(1.0, self.opening))
            self.state.running = self.opening >= 0.5
        inlet: Optional[Stream] = inputs.get("inlet_stream")
        if not self.is_open:
            self.state.running = False
            if inlet is None:
                return {"outlet_stream": None, "open": False, "flow_out": 0.0, "blocked": True}
            blocked = inlet.copy_with(mass_flow=0.0)
            return {"outlet_stream": blocked, "open": False, "flow_out": 0.0, "blocked": True}
        self.state.running = True
        if inlet is None:
            return {"outlet_stream": None, "open": True, "flow_out": 0.0, "blocked": False}
        outlet = inlet.copy_with(mass_flow=inlet.mass_flow)
        return {"outlet_stream": outlet, "open": True, "flow_out": inlet.mass_flow, "blocked": False}

    def get_state(self) -> EquipmentState:
        self.state.running = self.is_open
        self.state.extra["open"] = self.is_open
        return self.state

    def apply_action(self, action_type: str, value: Optional[float] = None) -> None:
        if self.state.failed:
            return
        if action_type in ("TURN_ON", "OPEN"):
            self.target_opening = self.opening = 1.0
        elif action_type in ("TURN_OFF", "CLOSE"):
            self.target_opening = self.opening = 0.0
        elif action_type == "SET_VALUE" and value is not None:
            self.target_opening = self.opening = 1.0 if value >= 0.5 else 0.0
        elif action_type in ("FAIL", "INJECT_FAILURE"):
            self.inject_failure("MECHANICAL_FAILURE")
            self.opening = self.target_opening = 0.0
        self.state.running = self.opening >= 0.5 and not self.state.failed

    def reset(self) -> None:
        super().reset()
        self._apply_params()
