"""
heater.py
=========
Rigorous furnace model with fuel-air combustion and energy balance.
"""

from typing import Dict, Any, Optional, List
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
        # A furnace may heat several independent sections (tube passes).  Each
        # channel is a dedicated inlet -> outlet port pair; the combustion duty
        # is shared between the channels present in the current step.
        self._channel_pairs = {
            "in": "out", "in2": "out2", "in3": "out3",
            "in4": "out4", "pp_in": "pp_out",
            "pp1_in": "pp1_out", "pp2_in": "pp2_out",
        }
        self._channel_ports = list(self._channel_pairs.keys())
        self._apply_params()

    def _apply_params(self) -> None:
        self.max_duty = self.params.get("max_heat_duty", 50e6)
        self.efficiency = self.params.get("efficiency", 0.85)
        self.lhv = self.params.get("heating_value", 40e6)

    def step(self, dt: float, **inputs) -> Dict[str, Any]:
        """
        Inputs:
            in, in2, in3, in4, pp_in: Stream (one per furnace section)
            thermo: ThermodynamicModel

        The furnace heats every section that has a connected inlet; the total
        combustion duty is split evenly between the active sections.  Returns
        one outlet stream per active section under its outlet port name.
        """
        thermo = inputs.get("thermo")
        # ``inlet_stream`` is the canonical single-stream compatibility API;
        # multi-pass furnaces use explicit ``in``, ``in2`` ... ports.
        if inputs.get("inlet_stream") is not None and inputs.get("in") is None:
            inputs["in"] = inputs["inlet_stream"]
        channel_ports = [p for p in self._channel_ports if inputs.get(p) is not None]
        if not channel_ports or not thermo:
            return {}

        if self.state.failed:
            # Flame-out: no combustion, every section exits at its inlet
            # temperature.
            self.fuel_flow = 0.0
            self.duty = 0.0
            out = {self._channel_pairs[p]: inputs[p] for p in channel_ports}
            if len(channel_ports) == 1 and channel_ports[0] == "in":
                out["outlet_stream"] = out.get("out")
            return out

        # Fuel flow dynamics
        tau = self.params.get("response_tau", 60.0)
        self.fuel_flow += (self.target_fuel_flow - self.fuel_flow) / tau * dt
        self.fuel_flow = max(0.0, self.fuel_flow)

        # Calculate total heat duty: Q = m_fuel * LHV * η, shared by the
        # active sections.
        duty_total = self.fuel_flow * self.lhv * self.efficiency
        duty_total = min(duty_total, self.max_duty)
        duty_per = duty_total / len(channel_ports)

        max_outlet_temp = self.params.get(
            "max_outlet_temp",
            (self.params.get("limits") or {}).get("temperature_high", 1000.0),
        )

        out: Dict[str, Any] = {}
        delivered = 0.0
        temps: List[float] = []
        for port in channel_ports:
            inlet = inputs[port]
            out_port = self._channel_pairs[port]
            if inlet.mass_flow <= 0:
                temps.append(inlet.temperature)
                out[out_port] = inlet.copy_with(
                    temperature=inlet.temperature, enthalpy=inlet.enthalpy
                )
                continue
            # Energy balance: H_out = H_in + Q / m_process
            h_in = inlet.enthalpy
            h_out = h_in + duty_per / inlet.mass_flow
            if hasattr(thermo, "temperature_from_enthalpy"):
                try:
                    t_out = float(
                        thermo.temperature_from_enthalpy(
                            h_out, inlet.pressure, inlet.composition, Phase.LIQUID
                        )
                    )
                except Exception:
                    cp = thermo.calculate_cp(inlet.temperature, inlet.pressure, inlet.composition)
                    t_out = 298.15 + h_out / cp
            else:
                cp = thermo.calculate_cp(inlet.temperature, inlet.pressure, inlet.composition)
                t_out = 298.15 + h_out / cp
            # Metallurgical cap: trim the delivered duty instead of silently
            # capping T (keeps the energy balance exact).
            if t_out > max_outlet_temp:
                t_out = max_outlet_temp
                h_out = float(thermo.calculate_enthalpy(
                    max_outlet_temp, inlet.pressure, inlet.composition
                ))
                delivered += max(0.0, (h_out - h_in)) * inlet.mass_flow
            else:
                delivered += duty_per
            temps.append(t_out)
            out[out_port] = inlet.copy_with(temperature=t_out, enthalpy=h_out)

        self.duty = delivered
        self.outlet_temp = sum(temps) / len(temps) if temps else 293.15
        self.duty_limited = delivered < duty_total - 1e-6
        # Preserve the single-stream API alongside explicit furnace ports.
        if len(channel_ports) == 1 and channel_ports[0] == "in":
            out["outlet_stream"] = out.get("out")
        return out

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
