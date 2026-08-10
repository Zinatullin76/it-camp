"""
elou.py
=======
Rigorous ELOU model with salt and water removal efficiency.
"""

from typing import Dict, Any, Optional
from .base_equipment import BaseEquipment, EquipmentState
from models.stream import Stream

class ELOU(BaseEquipment):
    """
    Electro-desalting unit with salt and water balance.
    """

    def __init__(self, equipment_id: str, params: Optional[Dict[str, Any]] = None):
        super().__init__(equipment_id, params or {})
        self.power_consumption = 0.0
        self.state.running = bool(self.params.get("initial_running", True))
        self._apply_params()

    def _apply_params(self) -> None:
        self.salt_efficiency = self.params.get("salt_efficiency", 0.95)
        self.water_efficiency = self.params.get("water_efficiency", 0.90)
        self.wash_water_ratio = self.params.get("wash_water_ratio", 0.05)
        self.pressure_drop = self.params.get("pressure_drop", 5e4)
        diameter = self.params.get("diameter_m")
        if diameter:
            self.vessel_area = 3.141592653589793 * (float(diameter) / 2.0) ** 2
        else:
            self.vessel_area = self.params.get("vessel_area", 30.0)
        self.height = self.params.get("height_m", 4.0)
        self.volume = self.vessel_area * self.height

    def step(self, dt: float, **inputs) -> Dict[str, Any]:
        """
        Inputs:
            inlet_stream: Stream
            wash_water: Stream
            thermo: ThermodynamicModel (optional; used to keep enthalpy
                    consistent after the composition change)
        """
        inlet: Stream = inputs.get("inlet_stream")
        wash_water: Stream = inputs.get("wash_water")
        thermo = inputs.get("thermo")
        
        if not inlet:
            return {"outlet_stream": None, "brine_stream": None}

        if not self.state.running or self.state.failed:
            return {"outlet_stream": inlet, "brine_stream": None}

        # Composition tracking: 'salt', 'water', 'oil' (mass fractions).
        comp = inlet.composition.copy()
        salt_in = comp.get("salt", 0.0)
        water_in = comp.get("water", 0.0)
        m_in = inlet.mass_flow

        # Removed amounts are mass fractions OF THE TOTAL feed, so the
        # component balance stays exact:  m_out + m_brine == m_in (+ wash).
        salt_removed_frac = salt_in * self.salt_efficiency
        water_removed_frac = water_in * self.water_efficiency
        salt_removed_mass = m_in * salt_removed_frac
        water_removed_mass = m_in * water_removed_frac

        # Outlet composition: the un-removed salt/water plus all hydrocarbons,
        # renormalised to unit mass.
        comp["salt"] = salt_in * (1.0 - self.salt_efficiency)
        comp["water"] = water_in * (1.0 - self.water_efficiency)
        total = sum(comp.values())
        comp = {k: v / total for k, v in comp.items()} if total > 0 else comp

        # Power consumption (simplified)
        self.power_consumption = 5000.0 * (m_in / 100.0)  # 5kW per 100kg/s

        outlet_pressure = max(1000.0, inlet.pressure - self.pressure_drop)
        outlet = inlet.copy_with(
            pressure=outlet_pressure,
            composition=comp,
            mass_flow=m_in * (1.0 - salt_removed_frac - water_removed_frac),
        )

        # Brine carries exactly the removed salt and water (plus wash water),
        # so the component balance closes: salt/water leave the oil and go
        # into the brine with the correct masses.
        brine_mass = salt_removed_mass + water_removed_mass
        wash_mass = wash_water.mass_flow if wash_water else 0.0
        brine_mass += wash_mass
        if brine_mass > 0.0:
            brine_comp = {
                "salt": salt_removed_mass / brine_mass,
                "water": (water_removed_mass + wash_mass) / brine_mass,
            }
        else:
            brine_comp = {"salt": 0.0, "water": 1.0}

        brine = inlet.copy_with(
            name="Brine",
            mass_flow=brine_mass,
            composition=brine_comp,
        )

        # Keep enthalpy consistent with the new composition (F11): a changed
        # composition at the same T/P must get its own enthalpy.
        if thermo is not None:
            try:
                outlet.enthalpy = float(thermo.calculate_enthalpy(
                    outlet.temperature, outlet.pressure, outlet.composition
                ))
                brine.enthalpy = float(thermo.calculate_enthalpy(
                    brine.temperature, brine.pressure, brine.composition
                ))
            except Exception:
                pass

        return {"outlet_stream": outlet, "brine_stream": brine}

    def get_state(self) -> EquipmentState:
        self.state.extra["power_consumption"] = self.power_consumption
        return self.state

    def apply_action(self, action_type: str, value: Optional[float] = None) -> None:
        if action_type == "TURN_ON":
            self.state.running = True
        elif action_type == "TURN_OFF":
            self.state.running = False

    def reset(self) -> None:
        super().reset()
        self.power_consumption = 0.0
        self.state.running = bool(self.params.get("initial_running", True))
