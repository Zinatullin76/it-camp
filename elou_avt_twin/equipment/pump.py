"""
pump.py
=======
Centrifugal pump driven by a real pump curve ΔP = f(Q, N) (ТЗ sections 19-22).

The pump no longer uses the ``delta_p = fixed * speed^2`` shortcut.  Its head
comes from :class:`~physics.pump_curve.PumpCurve`, which embeds the affinity
laws (Q ∝ N, ΔP ∝ N², Power ∝ N³).  The pump/system operating point is found
by the hydraulic network solver; this class applies the consistent pressure
rise at the solved flow (no silent overwrite — ТЗ section 29).

Cavitation is handled via NPSHA/NPSHR (ТЗ section 32):
    NPSHA = P_suction + ρ·g·z_suction − P_vap
    if NPSHA < NPSHR -> CAVITATION_WARNING + documented degraded regime.

Units: head/ΔP in Pa, flows in kg/s (mass) and m^3/s (volumetric).
"""

from typing import Any, Dict, Optional

from models.stream import Stream
from physics.pump_curve import PumpCurve, curve_from_params, pump_diagnostic
from physics.state import PhysicsDiagnostic
from .base_equipment import BaseEquipment, EquipmentState

G = 9.81  # m/s^2

# Degraded regime when cavitating: the flow is throttled so the head meets the
# available NPSH head.  This is a DOCUMENTED degradation (ТЗ section 32), not a
# hidden physics switch.
CAVITATION_FLOW_FACTOR = 0.5


class Pump(BaseEquipment):
    """
    Centrifugal pump with a parabolic pump curve and affinity-law speed control.

    Params (canonical):
        nominal_volumetric_flow_m3_s : design volumetric flow [m^3/s]
        nominal_head_pa              : design (BEP) head [Pa]
        shutoff_head_pa              : dead-head pressure at Q=0 [Pa]
        efficiency_nominal           : hydraulic efficiency [-]
        nominal_speed                : nominal rotation speed [RPM]
        npshr_pa                     : required NPSH [Pa]
        vapor_pressure_pa            : fluid vapour pressure [Pa]
        suction_lift_m               : static suction lift [m] (>0 reduces NPSHA)
    Legacy aliases ``nominal_flow`` (m^3/s) and ``delta_p`` (Pa) are accepted
    and migrated to the canonical names.
    """

    def __init__(self, equipment_id: str, params: Optional[Dict[str, Any]] = None):
        super().__init__(equipment_id, params or {})
        self.power = 0.0
        self.pressure_rise_pa = 0.0
        self.npsha_pa: Optional[float] = None
        self.npshr_pa: Optional[float] = None
        self.cavitating = False
        self.diagnostics: list[PhysicsDiagnostic] = []
        self._apply_params()
        self.speed = self.nominal_speed
        self.state.running = bool(self.params.get("initial_running", True))

    @property
    def speed_ratio(self) -> float:
        """Rotation speed relative to nominal, clamped to [0, 2]."""
        return max(0.0, min(2.0, self.speed / max(self.nominal_speed, 1.0)))

    def _apply_params(self) -> None:
        self.curve: PumpCurve = curve_from_params(self.params)
        self.efficiency = self.params.get("efficiency_nominal", 0.75)
        self.nominal_speed = max(1.0, float(self.params.get("nominal_speed", 1450.0)))
        self.npshr_pa = float(self.params.get("npshr_pa", 3.0 * G * 1000.0))
        self.vapor_pressure_pa = float(self.params.get("vapor_pressure_pa", 1.0e4))
        self.suction_lift_m = float(self.params.get("suction_lift_m", 0.0))

    # -- characteristic ------------------------------------------------------

    def pressure_rise(self, flow_kg_s: float, density: float = 850.0) -> float:
        """Discharge pressure rise [Pa] at a mass flow and current speed."""
        q_m3_s = max(0.0, flow_kg_s) / max(density, 1e-6)
        return self.curve.pressure_rise(q_m3_s, self.speed_ratio)

    def current_capacity(self, density: float = 850.0) -> float:
        """Mass-flow capacity at the current speed [kg/s].

        Used by the flow-limits pass: a running pump throttles its line to the
        capacity of the current speed (a stopped/failed pump dead-heads it).
        """
        if not (self.state.running and not self.state.failed):
            return 0.0
        q = self.curve.design_flow_at_speed(self.speed_ratio)
        return max(0.0, q * density)

    # -- NPSH ----------------------------------------------------------------

    def compute_npsh(self, suction_pressure_pa: float, density: float = 850.0) -> float:
        """Available NPSH [Pa]: NPSHA = P_suction + ρ·g·z_suction − P_vap."""
        z_suction = -self.suction_lift_m  # lift reduces the static head
        return max(0.0, suction_pressure_pa + density * G * z_suction - self.vapor_pressure_pa)

    def inject_failure(self, failure_mode: str) -> None:
        """Inject a failure.

        CAVITATION (ТЗ section 32) is NOT a hard failure: it puts the pump into
        the documented degraded regime with a CAVITATION_WARNING, so the machine
        stays online but loses head/flow.  Everything else is a real trip
        (failed -> no flow).
        """
        if failure_mode == "CAVITATION":
            self.state.failed = False
            self.state.failure_mode = failure_mode
            self.state.degradation = 1.0
            return
        super().inject_failure(failure_mode)

    # -- stepping ------------------------------------------------------------

    def step(self, dt: float, **inputs) -> Dict[str, Any]:
        inlet: Optional[Stream] = inputs.get("inlet_stream")
        flow_kg_s: Optional[float] = inputs.get("flow_kg_s")
        density = float(inputs.get("density", 850.0))
        if inlet is not None:
            density = inlet.density if inlet.density and inlet.density > 0 else density

        sr = self.speed_ratio
        failed = self.state.failed
        running = self.state.running and not failed
        self.diagnostics = []

        if not running:
            self.power = 0.0
            self.pressure_rise_pa = 0.0
            outlet = inlet.copy_with(mass_flow=0.0) if inlet else None
            return {
                "outlet_stream": outlet, "flow_out": 0.0, "power": 0.0,
                "running": False, "failed": failed,
            }

        # Cavitation (ТЗ section 32): NPSH-driven on a live inlet, or an
        # injected CAVITATION degradation.  Both emit CAVITATION_WARNING and
        # enter the documented degraded regime (flow collapses toward the NPSH
        # limit).  The cavitation factor is applied in BOTH paths so the
        # standalone model degrades identically to the network model.
        if inlet is not None:
            suction_p = inlet.pressure if inlet else 101325.0
            self.npsha_pa = self.compute_npsh(suction_p, density)
            self.npshr_pa = float(self.npshr_pa)
            self.cavitating = self.npsha_pa < self.npshr_pa
        else:
            self.cavitating = self.state.failure_mode == "CAVITATION"
        if self.cavitating:
            if self.npsha_pa is not None and self.npshr_pa is not None:
                cav_factor = min(1.0, self.npsha_pa / max(self.npshr_pa, 1.0))
            else:
                cav_factor = 1.0 - self.state.degradation * 0.5
            cav_factor = max(0.0, cav_factor) * CAVITATION_FLOW_FACTOR
            self.diagnostics.append(pump_diagnostic(
                code="PUMP_CAVITATION", component=self.equipment_id,
                message=(f"NPSHA {self.npsha_pa if self.npsha_pa is not None else 0:.0f} Pa < "
                         f"NPSHR {self.npshr_pa if self.npshr_pa is not None else 0:.0f} Pa — "
                         f"cavitation, degraded regime."),
                severity="warning",
                value=self.npsha_pa, limit=self.npshr_pa,
            ))
        else:
            cav_factor = 1.0

        # Standalone mode (no inlet stream): operate at the design point.
        if inlet is None:
            q_m3_s = self.curve.design_flow_at_speed(sr)
            flow_mass = q_m3_s * density * max(0.0, self.efficiency) * cav_factor
            q_m3_s = flow_mass / max(density, 1e-6)
            dp = self.curve.pressure_rise(q_m3_s, sr)
            self.pressure_rise_pa = dp
            self.power = (q_m3_s * dp) / max(self.efficiency, 1e-6)
            return {
                "outlet_stream": None,
                "flow_out": flow_mass / max(density, 1e-6),  # m^3/s (legacy)
                "mass_flow_kg_s": flow_mass,
                "volumetric_flow_m3_s": q_m3_s,
                "pressure_rise_pa": dp,
                "power": self.power, "running": True, "failed": False,
                "cavitating": self.cavitating,
                "diagnostics": list(self.diagnostics),
            }

        # Live path: apply the curve at the flow imposed by the hydraulic solve.
        flow = max(0.0, float(flow_kg_s)) if flow_kg_s is not None else inlet.mass_flow
        flow *= cav_factor
        q_m3_s = flow / max(density, 1e-6)
        dp = self.curve.pressure_rise(q_m3_s, sr)
        self.pressure_rise_pa = dp

        self.power = (q_m3_s * dp) / max(self.efficiency, 1e-6)
        work_per_mass = self.power / max(flow, 1e-9)
        outlet = inlet.copy_with(
            pressure=inlet.pressure + dp,
            mass_flow=flow,
            enthalpy=inlet.enthalpy + work_per_mass,
        )
        return {
            "outlet_stream": outlet,
            "flow_out": outlet.mass_flow,
            "mass_flow_kg_s": outlet.mass_flow,
            "volumetric_flow_m3_s": q_m3_s,
            "pressure_rise_pa": dp,
            "power": self.power,
            "running": True, "failed": False,
            "npsha_pa": self.npsha_pa,
            "npshr_pa": self.npshr_pa,
            "cavitating": self.cavitating,
            "diagnostics": list(self.diagnostics),
        }

    def get_state(self) -> EquipmentState:
        self.state.extra["power"] = self.power
        self.state.extra["speed_rpm"] = self.speed
        self.state.extra["speed_ratio"] = self.speed_ratio
        self.state.extra["pressure_rise_pa"] = self.pressure_rise_pa
        self.state.extra["cavitating"] = self.cavitating
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
        self.pressure_rise_pa = 0.0
        self.npsha_pa = None
        self.cavitating = False
        self.diagnostics = []
        self.speed = self.nominal_speed
        self.state.running = bool(self.params.get("initial_running", True))
