"""
heat_exchanger.py
=================
Rigorous heat exchanger model with LMTD and energy balance.
"""

from typing import Dict, Any, Optional
import numpy as np
from .base_equipment import BaseEquipment, EquipmentState
from models.stream import Stream, Phase

class HeatExchanger(BaseEquipment):
    """
    Shell-and-tube heat exchanger with LMTD method.
    """

    def __init__(self, equipment_id: str, params: Optional[Dict[str, Any]] = None):
        super().__init__(equipment_id, params or {})
        self.duty = 0.0
        self.t_hot_out = 293.15
        self.t_cold_out = 293.15
        self._apply_params()

    def _apply_params(self) -> None:
        self.u = self.params.get("u", 300.0)
        self.area = self.params.get("area", 200.0)

    def step(self, dt: float, **inputs) -> Dict[str, Any]:
        """
        Inputs:
            hot_in: Stream
            cold_in: Stream
            thermo: ThermodynamicModel
        """
        hot_in: Stream = inputs.get("hot_in")
        cold_in: Stream = inputs.get("cold_in")
        thermo = inputs.get("thermo")
        
        if not hot_in or not cold_in or not thermo:
            return {"hot_out": None, "cold_out": None}

        # Calculate max possible heat transfer (effectiveness-NTU or simple approach)
        # For MVP, we use a simplified iterative LMTD
        cp_hot = thermo.calculate_cp(hot_in.temperature, hot_in.pressure, hot_in.composition)
        cp_cold = thermo.calculate_cp(cold_in.temperature, cold_in.pressure, cold_in.composition)
        
        c_hot = hot_in.mass_flow * cp_hot
        c_cold = cold_in.mass_flow * cp_cold
        
        if c_hot <= 0 or c_cold <= 0:
            return {"hot_out": hot_in, "cold_out": cold_in}

        # Simplified duty calculation for MVP
        # Q = UA * LMTD
        # We need an iterative solver for real T_out, here we use a fixed approach
        dt_max = hot_in.temperature - cold_in.temperature
        if dt_max <= 0:
            return {"hot_out": hot_in, "cold_out": cold_in}
            
        # Effectiveness-NTU method
        c_min = min(c_hot, c_cold)
        c_max = max(c_hot, c_cold)
        cr = c_min / c_max
        ntu = (self.u * self.area) / c_min
        
        # Effectiveness for counter-flow
        if cr < 1:
            eps = (1 - np.exp(-ntu * (1 - cr))) / (1 - cr * np.exp(-ntu * (1 - cr)))
        else:
            eps = ntu / (1 + ntu)
            
        self.duty = eps * c_min * dt_max
        
        # Energy balances
        h_hot_out = hot_in.enthalpy - self.duty / hot_in.mass_flow
        h_cold_out = cold_in.enthalpy + self.duty / cold_in.mass_flow

        if hasattr(thermo, "temperature_from_enthalpy"):
            # Keep T consistent with the PR enthalpy model (matters for
            # condensers where the latent heat dominates the temperature drop).
            try:
                self.t_hot_out = float(thermo.temperature_from_enthalpy(
                    h_hot_out, hot_in.pressure, hot_in.composition, Phase.LIQUID))
            except Exception:
                self.t_hot_out = hot_in.temperature - self.duty / c_hot
            try:
                self.t_cold_out = float(thermo.temperature_from_enthalpy(
                    h_cold_out, cold_in.pressure, cold_in.composition, Phase.LIQUID))
            except Exception:
                self.t_cold_out = cold_in.temperature + self.duty / c_cold
        else:
            self.t_hot_out = hot_in.temperature - self.duty / c_hot
            self.t_cold_out = cold_in.temperature + self.duty / c_cold
        
        hot_out = hot_in.copy_with(temperature=self.t_hot_out, enthalpy=h_hot_out)
        cold_out = cold_in.copy_with(temperature=self.t_cold_out, enthalpy=h_cold_out)

        return {
            "hot_out": hot_out,
            "cold_out": cold_out,
            "duty": self.duty,
            "t_hot_in": hot_in.temperature,
            "t_hot_out": self.t_hot_out,
            "t_cold_in": cold_in.temperature,
            "t_cold_out": self.t_cold_out,
        }

    def get_state(self) -> EquipmentState:
        self.state.extra["duty"] = self.duty
        self.state.extra["t_hot_out"] = self.t_hot_out
        self.state.extra["t_cold_out"] = self.t_cold_out
        return self.state

    def apply_action(self, action_type: str, value: Optional[float] = None) -> None:
        pass

    def reset(self) -> None:
        super().reset()
        self.duty = 0.0
        self.t_hot_out = 293.15
        self.t_cold_out = 293.15
