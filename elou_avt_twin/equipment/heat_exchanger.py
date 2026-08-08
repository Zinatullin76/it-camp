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

        The exchanger is bidirectional: heat always flows from the physically
        hotter inlet to the physically colder one, regardless of which stream
        is connected to the ``hot_in`` / ``cold_in`` ports.  The internal
        calculation labels the hotter stream "hot" and the colder one "cold";
        the results are then mapped back to the original ports so the port
        roles (hot_out / cold_out) always refer to the connected streams.
        """
        port_hot_in: Stream = inputs.get("hot_in")
        port_cold_in: Stream = inputs.get("cold_in")
        thermo = inputs.get("thermo")
        
        if not port_hot_in or not port_cold_in or not thermo:
            return {"hot_out": None, "cold_out": None}

        # Resolve the physical roles: the hotter stream releases heat, the
        # colder one absorbs it, no matter which port it is attached to.
        if port_hot_in.temperature >= port_cold_in.temperature:
            hot_in, cold_in = port_hot_in, port_cold_in
            swapped = False
        else:
            hot_in, cold_in = port_cold_in, port_hot_in
            swapped = True

        # Calculate max possible heat transfer (effectiveness-NTU or simple approach)
        # For MVP, we use a simplified iterative LMTD
        cp_hot = thermo.calculate_cp(hot_in.temperature, hot_in.pressure, hot_in.composition)
        cp_cold = thermo.calculate_cp(cold_in.temperature, cold_in.pressure, cold_in.composition)
        
        c_hot = hot_in.mass_flow * cp_hot
        c_cold = cold_in.mass_flow * cp_cold
        
        if c_hot <= 0 or c_cold <= 0:
            return {"hot_out": port_hot_in, "cold_out": port_cold_in}

        # Simplified duty calculation for MVP
        # Q = UA * LMTD
        # We need an iterative solver for real T_out, here we use a fixed approach
        dt_max = hot_in.temperature - cold_in.temperature
        if dt_max <= 0:
            return {"hot_out": port_hot_in, "cold_out": port_cold_in}
            
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

        duty_ntu = eps * c_min * dt_max

        # Physical duty caps so the outlet temperatures respect the second
        # law: the hot outlet cannot be colder than the cold inlet and the
        # cold outlet cannot be hotter than the hot inlet.  The NTU shortcut
        # with constant Cp over-estimates the duty whenever latent heat is
        # involved (a condenser would "cool" the distillate far below the
        # cooling-water temperature), so the caps are enforced against the
        # actual flashed enthalpies.
        # Reference inlet enthalpies from the flashed EOS state, not the
        # stream's claimed enthalpy.  Upstream equipment (e.g. a column that
        # emits a super-saturated "vapor" distillate below its dew point) can
        # carry an enthalpy inconsistent with T/P/x; recomputing it makes the
        # energy balance and the duty caps self-consistent.
        try:
            h_hot_in = thermo.calculate_enthalpy(
                hot_in.temperature, hot_in.pressure, hot_in.composition)
        except Exception:
            h_hot_in = hot_in.enthalpy
        try:
            h_cold_in = thermo.calculate_enthalpy(
                cold_in.temperature, cold_in.pressure, cold_in.composition)
        except Exception:
            h_cold_in = cold_in.enthalpy
        try:
            h_hot_at_cold_in = thermo.calculate_enthalpy(
                cold_in.temperature, hot_in.pressure, hot_in.composition)
        except Exception:
            h_hot_at_cold_in = h_hot_in - c_hot * (hot_in.temperature - cold_in.temperature)
        try:
            h_cold_at_hot_in = thermo.calculate_enthalpy(
                hot_in.temperature, cold_in.pressure, cold_in.composition)
        except Exception:
            h_cold_at_hot_in = h_cold_in + c_cold * (hot_in.temperature - cold_in.temperature)
        duty_max_hot = hot_in.mass_flow * max(0.0, h_hot_in - h_hot_at_cold_in)
        duty_max_cold = cold_in.mass_flow * max(0.0, h_cold_at_hot_in - h_cold_in)
        self.duty = min(duty_ntu, duty_max_hot, duty_max_cold)
        if self.duty <= 0:
            return {
                "hot_out": port_hot_in, "cold_out": port_cold_in, "duty": 0.0,
                "t_hot_in": port_hot_in.temperature,
                "t_hot_out": port_hot_in.temperature,
                "t_cold_in": port_cold_in.temperature,
                "t_cold_out": port_cold_in.temperature,
            }

        # Energy balances
        h_hot_out = h_hot_in - self.duty / hot_in.mass_flow
        h_cold_out = h_cold_in + self.duty / cold_in.mass_flow

        if hasattr(thermo, "temperature_from_enthalpy"):
            try:
                self.t_hot_out = self._enthalpy_to_temp(thermo, hot_in, h_hot_out)
            except Exception:
                self.t_hot_out = hot_in.temperature - self.duty / c_hot
            try:
                self.t_cold_out = self._enthalpy_to_temp(thermo, cold_in, h_cold_out)
            except Exception:
                self.t_cold_out = cold_in.temperature + self.duty / c_cold
        else:
            self.t_hot_out = hot_in.temperature - self.duty / c_hot
            self.t_cold_out = cold_in.temperature + self.duty / c_cold

        # Map the internal (physical) hot/cold results back to the connected
        # ports: the "hot" outlet port always receives the cooled stream of the
        # port_hot_in connection and vice versa.
        if swapped:
            # port_hot_in was the physically colder stream (internal cold),
            # so it exits heated on the hot_out port.
            port_hot_out = cold_in.copy_with(temperature=self.t_cold_out, enthalpy=h_cold_out)
            port_cold_out = hot_in.copy_with(temperature=self.t_hot_out, enthalpy=h_hot_out)
            # Keep get_state() consistent with the port semantics.
            port_t_hot_out = self.t_cold_out
            port_t_cold_out = self.t_hot_out
            self.t_hot_out = port_t_hot_out
            self.t_cold_out = port_t_cold_out
            return {
                "hot_out": port_hot_out,
                "cold_out": port_cold_out,
                "duty": self.duty,
                "t_hot_in": port_hot_in.temperature,
                "t_hot_out": port_t_hot_out,
                "t_cold_in": port_cold_in.temperature,
                "t_cold_out": port_t_cold_out,
            }

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

    def _enthalpy_to_temp(self, thermo, stream, h_target: float) -> float:
        """Monotone phase-aware enthalpy -> temperature inversion.

        Inverts the flashed (auto-phase) enthalpy H(T, P, x) for the stream.
        Because the auto-phase enthalpy includes the latent heat, a condensing
        distillate stays pinned at its saturation temperature and a two-phase
        hot stream condenses in place -- instead of "warming up" or dropping
        below the cooling medium like the old fixed-LIQUID-phase inversion
        did.
        """
        p = stream.pressure
        comp = stream.composition
        lo, hi = 200.0, 1200.0
        f_lo = thermo.calculate_enthalpy(lo, p, comp) - h_target
        f_hi = thermo.calculate_enthalpy(hi, p, comp) - h_target
        if f_lo >= 0.0:
            return lo
        if f_hi <= 0.0:
            return hi
        for _ in range(35):
            mid = 0.5 * (lo + hi)
            f_mid = thermo.calculate_enthalpy(mid, p, comp) - h_target
            if abs(f_mid) < 1e-6:
                return mid
            if f_lo * f_mid < 0.0:
                hi = mid
            else:
                lo, f_lo = mid, f_mid
        return 0.5 * (lo + hi)

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
