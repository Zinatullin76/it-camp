"""
separator_s1k.py
================
С-1К vertical two-phase separator (Сепаратор С-1К): merges two feed streams
(in_l / in_r), flashes the combined feed at the vessel T/P and splits it into
a top gas stream (out_t) and a bottom liquid stream (out_b).

  flash(T, P, z) -> beta, x_mass, y_mass   (molar vapor fraction + phase
                                            compositions as MASS fractions)
  vf = mass vapor fraction, recovered from the component mass balance
  m_vap = vf * m_feed   (leaves through the top immediately)
  m_liq = (1 - vf) * m_feed  (accumulates in the vessel; the bottom outflow is
                              set by a P-level controller, like Tank)

The overall mass balance always closes: m_in = m_out_t + m_out_b + accumulation.
"""

from typing import Any, Dict, List, Optional, Tuple
from .base_equipment import BaseEquipment, EquipmentState
from models.stream import Stream, Phase


def _normalize(comp: Dict[str, float]) -> Dict[str, float]:
    """Renormalise a mass composition to sum = 1 (Stream contract)."""
    total = sum(comp.values())
    if total <= 0.0:
        return {"water": 1.0}
    return {k: v / total for k, v in comp.items()}


class SeparatorS1K(BaseEquipment):
    """
    Two-phase separator with two inlets and two outlets (top gas / bottom
    liquid), a liquid level and a level-controlled bottom outlet.
    """

    def __init__(self, equipment_id: str, params: Optional[Dict[str, Any]] = None):
        super().__init__(equipment_id, params or {})
        init_level = self.params.get("initial_level", self.params.get("setpoint_level", 2.0))
        self.level = float(init_level)
        self.setpoint = float(self.params.get("setpoint_level", init_level))
        self.level_controller_auto = self.params.get("level_auto", True)
        self._apply_params()

    def _apply_params(self) -> None:
        diameter = self.params.get("diameter_m")
        if diameter:
            self.area = 3.141592653589793 * (float(diameter) / 2.0) ** 2
        else:
            self.area = self.params.get("vessel_area", 30.0)
        self.height = self.params.get("height_m", 6.0)
        self.gain = self.params.get("level_gain", 50.0)
        self.pressure = self.params.get("nominal_pressure", None)
        if "setpoint_level" in self.params:
            self.setpoint = max(0.0, float(self.params["setpoint_level"]))

    def _merge_feed(self, streams: List[Stream]) -> Optional[Stream]:
        """Mass-conserving merge of the two inlet streams."""
        active = [s for s in streams if s is not None and s.mass_flow > 0]
        if not active:
            active = [s for s in streams if s is not None]
            if not active:
                return None
        if len(active) == 1:
            return active[0]
        total = sum(s.mass_flow for s in active)
        components = sorted({c for s in active for c in s.composition})
        composition = {
            c: sum(s.composition.get(c, 0.0) * s.mass_flow for s in active) / total
            for c in components
        }
        base = active[0]
        return base.copy_with(
            name="S1KFeed",
            mass_flow=total,
            composition=_normalize(composition),
            temperature=sum(s.temperature * s.mass_flow for s in active) / total,
            pressure=sum(s.pressure * s.mass_flow for s in active) / total,
            enthalpy=sum(s.enthalpy * s.mass_flow for s in active) / total,
            density=sum(s.density * s.mass_flow for s in active) / total,
            viscosity=sum(s.viscosity * s.mass_flow for s in active) / total,
        )

    def _split(self, feed: Stream, thermo, P: float) -> Tuple[float, Dict[str, float], Dict[str, float]]:
        """Flash the feed at vessel T/P -> (mass vapor fraction, x_mass, y_mass)."""
        T = feed.temperature
        if thermo is None or feed.mass_flow <= 0.0:
            return 0.0, feed.composition, feed.composition
        try:
            beta, x_mass, y_mass = thermo.calculate_vle(T, P, feed.composition)
        except Exception:
            return 0.0, feed.composition, feed.composition
        x_mass = _normalize(dict(x_mass))
        y_mass = _normalize(dict(y_mass))
        if beta <= 0.0:
            return 0.0, x_mass, y_mass
        if beta >= 1.0:
            return 1.0, x_mass, y_mass
        # Mass vapor fraction from the component mass balance
        # w_i = vf*y_i + (1-vf)*x_i  =>  vf = (x_i - w_i) / (x_i - y_i).
        # The flash is solved consistently, so every component gives the same
        # vf; averaging over them removes floating-point scatter.
        w = feed.composition
        candidates: List[float] = []
        for c in w:
            den = x_mass.get(c, 0.0) - y_mass.get(c, 0.0)
            if abs(den) > 1e-9:
                candidates.append((x_mass.get(c, 0.0) - w.get(c, 0.0)) / den)
        vf = 0.0
        if candidates:
            vf = sum(candidates) / len(candidates)
        return min(1.0, max(0.0, vf)), x_mass, y_mass

    def step(self, dt: float, **inputs) -> Dict[str, Any]:
        """
        Inputs:
            inlet_streams: List[Stream] — the in_l / in_r feed streams
            thermo: ThermodynamicModel (for the flash and phase properties)
            max_out: float (optional) — downstream restriction for the bottom
                    outlet (dead-head hold-back), from the line solver
            vessel_pressure: float (optional) — the vessel's operating pressure
                    (base + hydrostatic head), the pressure the outlets carry
                    and the flash is run at; falls back to the nominal pressure
                    then to the feed pressure
        """
        streams = inputs.get("inlet_streams")
        if not streams:
            single = inputs.get("inlet_stream")
            streams = [single] if single is not None else None
        feed = self._merge_feed(streams) if streams else None
        if feed is None:
            return {
                "out_t": None, "out_b": None,
                "level": self.level, "setpoint": self.setpoint,
                "in_flow": 0.0, "out_flow": 0.0,
            }
        thermo = inputs.get("thermo")
        max_out = inputs.get("max_out")

        vessel_pressure = inputs.get("vessel_pressure")
        P = vessel_pressure or self.pressure or feed.pressure
        vf, x_mass, y_mass = self._split(feed, thermo, P)

        m_feed = max(0.0, feed.mass_flow)
        m_vap = m_feed * vf
        m_liq = m_feed * (1.0 - vf)

        # Level controller on the liquid: pass the flash liquid, corrected by
        # the level deviation (AUTO), clamped by the downstream restriction.
        if self.level_controller_auto:
            m_out_b = m_liq + self.gain * (self.level - self.setpoint)
        else:
            m_out_b = m_liq
        if max_out is not None:
            m_out_b = min(m_out_b, max_out)
        m_out_b = max(0.0, m_out_b)

        # Liquid accumulation: dL/dt = (m_liq_in - m_out_b) / (rho * A).
        # Overflow above the vessel height leaves the vessel (spill) instead of
        # being destroyed, so the material balance stays exact (F07 contract).
        rho = feed.density if feed.density and feed.density > 0 else 850.0
        overflow_mass = 0.0
        level_new = self.level + (m_liq - m_out_b) / max(rho * self.area, 1e-6) * dt
        if level_new > self.height:
            overflow_mass = (level_new - self.height) * rho * self.area
            m_out_b += overflow_mass / max(dt, 1e-9)
            level_new = self.height
        level_new = max(0.0, level_new)
        self.level = level_new

        # Phase properties from thermo (fall back to the feed state).
        h_v = feed.enthalpy
        h_l = feed.enthalpy
        rho_v = 1.2
        rho_l = rho
        if thermo is not None and m_feed > 0.0:
            try:
                h_v = float(thermo.calculate_enthalpy(
                    feed.temperature, P, y_mass, Phase.VAPOR
                ))
                h_l = float(thermo.calculate_enthalpy(
                    feed.temperature, P, x_mass, Phase.LIQUID
                ))
                rho_v = float(thermo.calculate_density(
                    feed.temperature, P, y_mass, Phase.VAPOR
                ))
                rho_l = float(thermo.calculate_density(
                    feed.temperature, P, x_mass, Phase.LIQUID
                ))
            except Exception:
                pass

        out_t = feed.copy_with(
            name="S1KTopGas",
            phase=Phase.VAPOR,
            pressure=P,
            mass_flow=m_vap,
            composition=y_mass,
            enthalpy=h_v,
            density=rho_v,
            viscosity=1e-5,
        )
        out_b = feed.copy_with(
            name="S1KBottomLiquid",
            phase=Phase.LIQUID,
            pressure=P,
            mass_flow=m_out_b,
            composition=x_mass,
            enthalpy=h_l,
            density=rho_l,
        )
        return {
            "out_t": out_t,
            "out_b": out_b,
            "level": self.level,
            "setpoint": self.setpoint,
            "volume_m3": round(self.area * self.height, 2),
            "in_flow": m_feed,
            "out_flow": m_out_b + m_vap,
            "overflow_mass": overflow_mass,
            "vapor_fraction": vf,
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
        init_level = self.params.get("initial_level", self.params.get("setpoint_level", 2.0))
        self.level = float(init_level)
        self.setpoint = float(self.params.get("setpoint_level", init_level))
        self.level_controller_auto = self.params.get("level_auto", True)
        self._apply_params()
