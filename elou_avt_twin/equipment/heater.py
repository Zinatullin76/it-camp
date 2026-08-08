"""
heater.py
=========
Rigorous furnace model with fuel-air combustion and energy balance.
"""

from typing import Dict, Any, Optional
from .base_equipment import BaseEquipment, EquipmentState
from models.stream import Stream, Phase

class Heater(BaseEquipment):
    """
    Atmospheric furnace with combustion energy balance.
    """

    def __init__(self, equipment_id: str, params: Optional[Dict[str, Any]] = None):
        super().__init__(equipment_id, params or {})
        self.fuel_flow = 0.0
        self.target_fuel_flow = 0.0
        init_fuel = self.params.get("initial_fuel_flow")
        if init_fuel is not None:
            self.fuel_flow = self.target_fuel_flow = max(0.0, float(init_fuel))
        self.duty = 0.0
        self.outlet_temp = 293.15
        self.duty_limited = False
        self._apply_params()

    def _apply_params(self) -> None:
        self.max_duty = self.params.get("max_heat_duty", 50e6)
        self.efficiency = self.params.get("efficiency", 0.85)
        self.lhv = self.params.get("heating_value", 40e6)

    def step(self, dt: float, **inputs) -> Dict[str, Any]:
        """
        Inputs:
            inlet_stream: Stream
            thermo: ThermodynamicModel
        """
        inlet: Stream = inputs.get("inlet_stream")
        thermo = inputs.get("thermo")
        
        if not inlet or not thermo:
            return {"outlet_stream": None}

        if self.state.failed:
            # Flame-out: no combustion, outlet at inlet temperature.
            self.fuel_flow = 0.0
            self.duty = 0.0
            self.outlet_temp = inlet.temperature
            return {"outlet_stream": inlet, "duty": 0.0, "failed": True}

        # Fuel flow dynamics
        tau = self.params.get("response_tau", 60.0)
        self.fuel_flow += (self.target_fuel_flow - self.fuel_flow) / tau * dt
        self.fuel_flow = max(0.0, self.fuel_flow)
        
        # Calculate heat duty: Q = m_fuel * LHV * η
        self.duty = self.fuel_flow * self.lhv * self.efficiency
        self.duty = min(self.duty, self.max_duty)
        
        # Energy balance: H_out = H_in + Q / m_process
        if inlet.mass_flow > 0:
            h_in = inlet.enthalpy
            h_out = h_in + self.duty / inlet.mass_flow
            if hasattr(thermo, "temperature_from_enthalpy"):
                # Rigorous inversion H(T) -> T for the mixture (handles the
                # PR residual-enthalpy reference that the Cp shortcut breaks).
                self.outlet_temp = float(
                    thermo.temperature_from_enthalpy(
                        h_out, inlet.pressure, inlet.composition, Phase.LIQUID
                    )
                )
            else:
                # H = Cp * (T - T_ref) => T = T_ref + H / Cp
                cp = thermo.calculate_cp(inlet.temperature, inlet.pressure, inlet.composition)
                self.outlet_temp = 298.15 + h_out / cp

            # Physical material limit (tube skin / metallurgy): the process
            # temperature must never exceed the limit.  Instead of silently
            # capping T (which would break the energy balance), trim the
            # delivered duty so H_out(T_max) = H_in + Q_delivered / m holds
            # exactly.  When the scheme defines the furnace's temperature
            # alarm limit (limits.temperature_high) it is used as the hard
            # metallurgical cap; an explicit max_outlet_temp overrides it.
            max_outlet_temp = self.params.get(
                "max_outlet_temp",
                (self.params.get("limits") or {}).get("temperature_high", 1000.0),
            )
            if self.outlet_temp > max_outlet_temp:
                self.outlet_temp = max_outlet_temp
                h_out = float(thermo.calculate_enthalpy(
                    max_outlet_temp, inlet.pressure, inlet.composition
                ))
                self.duty = max(0.0, (h_out - h_in) * inlet.mass_flow)
                self.duty_limited = True
            else:
                self.duty_limited = False
        else:
            self.outlet_temp = inlet.temperature
            h_out = inlet.enthalpy

        outlet = inlet.copy_with(
            temperature=self.outlet_temp,
            enthalpy=h_out
        )
        
        return {"outlet_stream": outlet, "duty": self.duty}

    def get_state(self) -> EquipmentState:
        self.state.extra["fuel_flow"] = self.fuel_flow
        self.state.extra["duty"] = self.duty
        self.state.extra["outlet_temp"] = self.outlet_temp
        self.state.extra["duty_limited"] = self.duty_limited
        return self.state

    def apply_action(self, action_type: str, value: Optional[float] = None) -> None:
        if action_type == "SET_VALUE" and value is not None:
            v = max(0.0, value)
            self.target_fuel_flow = v
            if not self.state.failed:
                self.fuel_flow = v
        elif action_type == "TURN_OFF":
            self.target_fuel_flow = 0.0
            if not self.state.failed:
                self.fuel_flow = 0.0
        elif action_type == "EMERGENCY_STOP":
            self.target_fuel_flow = 0.0
            self.fuel_flow = 0.0

    def reset(self) -> None:
        super().reset()
        init_fuel = self.params.get("initial_fuel_flow")
        self.fuel_flow = self.target_fuel_flow = 0.0
        if init_fuel is not None:
            self.fuel_flow = self.target_fuel_flow = max(0.0, float(init_fuel))
        self.duty = 0.0
        self.outlet_temp = 293.15
