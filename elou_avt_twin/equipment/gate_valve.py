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

    Unlike the throttling control Valve, the gate valve has no intermediate
    positions: it is either fully open or fully closed.
    """

    def __init__(self, equipment_id: str, params: Optional[Dict[str, Any]] = None):
        super().__init__(equipment_id, params or {})
        self.is_open = bool(self.params.get("initial_open", 1.0))
        self.state.running = self.is_open

    def _apply_params(self) -> None:
        self.is_open = bool(self.params.get("initial_open", 1.0))
        self.state.running = self.is_open

    def step(self, dt: float, **inputs) -> Dict[str, Any]:
        if self.state.failed:
            # Fail-closed safety: a faulty задвижка isolates the line.
            self.is_open = False
            self.state.running = False
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
            self.is_open = True
        elif action_type in ("TURN_OFF", "CLOSE"):
            self.is_open = False
        elif action_type == "SET_VALUE" and value is not None:
            self.is_open = value >= 0.5
        self.state.running = self.is_open

    def reset(self) -> None:
        super().reset()
        self.is_open = bool(self.params.get("initial_open", 1.0))
        self.state.running = self.is_open
