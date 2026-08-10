"""
pump_curve.py
=============
Pump curve model: ΔP = f(Q, N) (ТЗ sections 19-22).

Replaces the old ``delta_p = fixed * speed^2`` shortcut with a real
centrifugal characteristic.  The curve is parametrised by a dead-head
(shut-off) pressure and a design point:

    ΔP(Q, N) = H0·N² − a·Q²          with   a = (H0 − H_design)/Q_design²

At constant speed the curve is a parabola through the design point: at Q = 0
it delivers the dead-head pressure, and the pressure decreases as Q grows
(centrifugal behaviour).  Affinity laws are built in:

    Q ∝ N        ΔP ∝ N²        Power ∝ N³

so the speed scales the curve (dead-head ∝ N²) rather than artificially
scaling a final flow (ТЗ section 22).

Units: pressures/heads in Pa, volumetric flow in m^3/s, speed as a fraction
of nominal speed [0..2].
"""

from __future__ import annotations

from typing import Optional

from physics.state import PhysicsDiagnostic, SolverStatus

RHO_OIL = 850.0  # kg/m^3 — fallback density for mass<->volume conversion


class PumpCurve:
    """Centrifugal pump curve with affinity-law speed scaling."""

    def __init__(
        self,
        shutoff_head_pa: float,
        design_volumetric_flow_m3_s: float,
        design_head_pa: Optional[float] = None,
    ) -> None:
        if shutoff_head_pa <= 0.0:
            raise ValueError("shutoff_head_pa must be > 0")
        if design_volumetric_flow_m3_s <= 0.0:
            raise ValueError("design_volumetric_flow_m3_s must be > 0")
        self.shutoff_head_pa = float(shutoff_head_pa)
        self.q_design_m3_s = float(design_volumetric_flow_m3_s)
        self.h_design_pa = (
            float(design_head_pa) if design_head_pa is not None
            else float(shutoff_head_pa) * 0.75
        )
        self.h_design_pa = min(self.h_design_pa, self.shutoff_head_pa)
        # a = (H0 - H_design) / Q_design^2  ->  always >= 0.
        self._a = max(
            0.0,
            (self.shutoff_head_pa - self.h_design_pa)
            / (self.q_design_m3_s * self.q_design_m3_s),
        )

    # -- characteristic ------------------------------------------------------

    def pressure_rise(self, volumetric_flow_m3_s: float, speed_fraction: float = 1.0) -> float:
        """Pump discharge pressure rise [Pa] at a given flow and speed."""
        n = self._clamp_speed(speed_fraction)
        q = max(0.0, volumetric_flow_m3_s)
        return self.shutoff_head_pa * n * n - self._a * q * q

    def power_w(self, volumetric_flow_m3_s: float, speed_fraction: float = 1.0,
                efficiency: float = 0.75) -> float:
        """Hydraulic power [W] = Q·ΔP/η (affinity Power ∝ N³ follows from ΔP, Q)."""
        q = max(0.0, volumetric_flow_m3_s)
        dp = self.pressure_rise(q, speed_fraction)
        return (q * dp) / max(efficiency, 1e-6)

    # -- helpers -------------------------------------------------------------

    def dead_head_pa(self, speed_fraction: float = 1.0) -> float:
        """Pressure at Q = 0 (ТЗ section 20: must be the shut-off pressure)."""
        n = self._clamp_speed(speed_fraction)
        return self.shutoff_head_pa * n * n

    def design_flow_at_speed(self, speed_fraction: float = 1.0) -> float:
        """Design volumetric flow [m^3/s] scaled by the affinity law Q ∝ N."""
        return self.q_design_m3_s * self._clamp_speed(speed_fraction)

    def on_curve(self, volumetric_flow_m3_s: float, speed_fraction: float = 1.0,
                 relative_tol: float = 0.15) -> bool:
        """Whether Q is inside the usable part of the curve (not beyond BEP).

        Flows far beyond the design point are outside the guaranteed range of
        the characteristic; the engine reports ``PUMP_OUTSIDE_CURVE`` for them
        instead of silently extrapolating.
        """
        q_design = self.design_flow_at_speed(speed_fraction)
        return 0.0 <= volumetric_flow_m3_s <= q_design * (1.0 + relative_tol)

    @staticmethod
    def _clamp_speed(speed_fraction: float) -> float:
        return max(0.0, min(2.0, float(speed_fraction)))

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (f"PumpCurve(H0={self.shutoff_head_pa:.3g}, "
                f"Q_design={self.q_design_m3_s:.3g}, H_design={self.h_design_pa:.3g})")


def curve_from_params(params: dict, density: float = RHO_OIL) -> PumpCurve:
    """Build a PumpCurve from equipment params (canonical names preferred).

    Accepted params:
        shutoff_head_pa                 (dead head, Pa)
        nominal_head_pa / delta_p       (design head, Pa — legacy alias)
        nominal_volumetric_flow_m3_s    (design flow, m^3/s)
        nominal_flow                    (legacy alias, treated as m^3/s)
        mass_capacity_kg_s              (alternative: design flow by mass)
    """
    q_design = float(params.get("nominal_volumetric_flow_m3_s", 0.0))
    if q_design <= 0.0:
        # ``nominal_flow`` is retained as a legacy volumetric-flow alias for
        # standalone equipment APIs.  New process schemes should use the
        # explicit SI key above (or ``mass_capacity_kg_s`` for mass flow).
        q_design = float(params.get("nominal_flow", 0.0))
        if q_design <= 0.0:
            q_design = 0.1
    if "mass_capacity_kg_s" in params:
        q_design = float(params["mass_capacity_kg_s"]) / max(density, 1e-6)

    h_design = float(params.get("nominal_head_pa", 0.0))
    if h_design <= 0.0:
        h_design = float(params.get("delta_p", 5e5))
    if h_design <= 0.0:
        h_design = 5e5

    shutoff = float(params.get("shutoff_head_pa", 0.0))
    if shutoff <= 0.0:
        shutoff = h_design * 1.3  # default shut-off ~30% above the design head

    return PumpCurve(shutoff, q_design, h_design)


def pump_diagnostic(code: str, component: str, message: str,
                    severity: str = "warning", value=None, limit=None) -> PhysicsDiagnostic:
    return PhysicsDiagnostic(
        severity=severity, code=code, component=component,
        message=message, value=value, limit=limit,
    )
