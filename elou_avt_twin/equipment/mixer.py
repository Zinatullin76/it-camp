"""
mixer.py
========
Stream mixer (смеситель): combines N incoming streams into a single outlet
with mass and energy conservation.

  m_out    = Σ m_i
  w_out,c  = Σ w_i,c * m_i / m_out      (mass fractions, component balance closes)
  h_out    = Σ h_i * m_i / m_out        (isenthalpic mixing, energy conserved)
  T_out    = solved from h_out via thermo (F11: H and T stay consistent)
  P, ρ, μ  = mass-flow-weighted averages (the line solver overrides P anyway)

The steady-state condition is trivial: all inputs in, one well-mixed output.
"""

from typing import Any, Dict, List, Optional
from .base_equipment import BaseEquipment, EquipmentState
from models.stream import Stream


class Mixer(BaseEquipment):
    """
    Mixer of several feed streams into a single product stream.
    """

    def __init__(self, equipment_id: str, params: Optional[Dict[str, Any]] = None):
        super().__init__(equipment_id, params or {})
        self._apply_params()

    def _apply_params(self) -> None:
        self.num_inputs = max(1, int(self.params.get("num_inputs", 2)))

    @staticmethod
    def _merge(streams: List[Stream]) -> Optional[Stream]:
        """Mass- and energy-conserving merge of the inlet streams."""
        active = [s for s in streams if s is not None and s.mass_flow > 0]
        if not active:
            active = [s for s in streams if s is not None]
            if not active:
                return None
            # All-zero feeds: keep the zero flow and the state of the largest one.
            base = max(active, key=lambda s: s.mass_flow)
            return base.copy_with(name="Mixed")
        if len(active) == 1:
            return active[0].copy_with(name="Mixed")
        total = sum(s.mass_flow for s in active)
        components = sorted({c for s in active for c in s.composition})
        composition = {
            c: sum(s.composition.get(c, 0.0) * s.mass_flow for s in active) / total
            for c in components
        }
        base = active[0]
        return base.copy_with(
            name="Mixed",
            mass_flow=total,
            composition=composition,
            temperature=sum(s.temperature * s.mass_flow for s in active) / total,
            pressure=sum(s.pressure * s.mass_flow for s in active) / total,
            enthalpy=sum(s.enthalpy * s.mass_flow for s in active) / total,
            density=sum(s.density * s.mass_flow for s in active) / total,
            viscosity=sum(s.viscosity * s.mass_flow for s in active) / total,
        )

    def step(self, dt: float, **inputs) -> Dict[str, Any]:
        """
        Inputs:
            inlet_streams: List[Stream] — the N feed streams
            inlet_stream: Stream (optional single-input convenience)
            thermo: ThermodynamicModel (optional; resolves T from H)
            back_pressure: float (optional) — junction pressure the outlet must
                    carry, set by the first solved element downstream.  Falls
                    back to the lowest feed pressure (no feed can enter a
                    junction below its own pressure).
        """
        streams: Optional[List[Stream]] = inputs.get("inlet_streams")
        if not streams:
            single = inputs.get("inlet_stream")
            streams = [single] if single is not None else None
        if not streams:
            return {"outlet_stream": None, "flow_out": 0.0}
        if self.state.failed:
            merged = self._merge(streams)
            return {
                "outlet_stream": merged,
                "flow_out": merged.mass_flow if merged else 0.0,
                "in_flows": [s.mass_flow for s in streams],
            }
        merged = self._merge(streams)
        if merged is None:
            return {"outlet_stream": None, "flow_out": 0.0}
        # Junction pressure continuity: the mixer outlet sits at the back-
        # pressure of the downstream equipment (or the lowest feed pressure).
        back_pressure = inputs.get("back_pressure")
        if back_pressure is not None:
            merged = merged.copy_with(pressure=float(back_pressure))
        else:
            feed_pressures = [
                s.pressure for s in streams if s is not None and s.mass_flow > 0
            ]
            if feed_pressures:
                merged = merged.copy_with(pressure=min(feed_pressures))
        thermo = inputs.get("thermo")
        # Resolve the outlet temperature from the enthalpy balance so H and T
        # stay thermodynamically consistent after the mix (only when the feeds
        # actually carry enthalpy; uninitialised zero-enthalpy feeds keep the
        # mass-weighted temperature).
        if thermo is not None and merged.mass_flow > 0 and abs(merged.enthalpy) > 1e-6:
            try:
                t_out = float(thermo.temperature_from_enthalpy(
                    merged.enthalpy, merged.pressure, merged.composition, merged.phase
                ))
                h_out = float(thermo.calculate_enthalpy(
                    t_out, merged.pressure, merged.composition, merged.phase
                ))
                merged = merged.copy_with(temperature=t_out, enthalpy=h_out)
            except Exception:
                pass
        return {
            "outlet_stream": merged,
            "flow_out": merged.mass_flow,
            "in_flows": [s.mass_flow for s in streams],
        }

    def get_state(self) -> EquipmentState:
        self.state.extra["num_inputs"] = self.num_inputs
        return self.state

    def apply_action(self, action_type: str, value: Optional[float] = None) -> None:
        if action_type == "SET_VALUE" and value is not None:
            self.num_inputs = max(1, int(value))

    def reset(self) -> None:
        super().reset()
        self._apply_params()
