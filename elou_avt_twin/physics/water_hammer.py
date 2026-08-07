"""
water_hammer.py
===============
Hydraulic transient (water hammer / surge) model — ТЗ section 36.

Joukowsky equation for the pressure surge caused by a rapid flow change in a
liquid-filled pipe:

    ΔP_surge = ρ · a · Δv · d

    ρ  : fluid density        [kg/m^3]
    a  : wave propagation speed [m/s]  (see ``wave_speed_elastic_pipe``)
    Δv : change in fluid velocity [m/s] (rapid closure of a valve / pump trip)
    d  : damping factor 0..1 (accounts for pipe friction and slow closures)

The risk check compares the maximum surge pressure against the piping maximum
allowable operating pressure (MAOP):

    P_max = P_nominal + ΔP_surge

    P_max / MAOP < 0.8                       -> LOW  risk
    0.8 <= P_max / MAOP < 1.0                -> MEDIUM risk
    P_max / MAOP >= 1.0                      -> HIGH risk (MAOP exceeded)

Used by the operator-error checking pass (surge on a fast valve closure) and
the pump trip scenario check.
"""

import math

from physics.state import PhysicsDiagnostic

RHO_OIL = 850.0  # kg/m^3

# Fraction of MAOP below which the surge is considered harmless.
LOW_RISK_RATIO = 0.8


def wave_speed_elastic_pipe(
    bulk_modulus_pa: float = 1.5e9,
    density: float = RHO_OIL,
    diameter_m: float = 0.1,
    wall_thickness_m: float = 0.01,
    youngs_modulus_pa: float = 2.1e11,  # steel
) -> float:
    """Acoustic wave speed [m/s] in a thin-walled elastic pipe (Joukowsky).

    a = sqrt( K / (ρ · (1 + (K·D)/(E·t))) )
    """
    denom = 1.0 + (bulk_modulus_pa * diameter_m) / (youngs_modulus_pa * wall_thickness_m)
    return math.sqrt(bulk_modulus_pa / (max(density, 1e-9) * denom))


def water_hammer_overpressure_pa(
    velocity_change_m_s: float,
    density: float = RHO_OIL,
    wave_speed_m_s: float = 1000.0,
    damping: float = 1.0,
) -> float:
    """Joukowsky pressure surge [Pa]: ΔP = ρ·a·Δv·d.

    ``velocity_change_m_s`` is the magnitude of the rapid velocity change
    (positive).  ``damping`` in (0, 1] lowers the surge for slow closures.
    """
    dv = max(0.0, velocity_change_m_s)
    return density * max(wave_speed_m_s, 0.0) * dv * max(0.0, min(1.0, damping))


def surge_risk(
    nominal_pressure_pa: float,
    velocity_change_m_s: float,
    maop_pa: float,
    density: float = RHO_OIL,
    wave_speed_m_s: float = 1000.0,
    damping: float = 1.0,
) -> dict:
    """Evaluate the surge risk of a rapid flow change.

    Returns a dict with the surge pressure, the maximum surge pressure and a
    risk band ('LOW' / 'MEDIUM' / 'HIGH') per the ratio P_max/MAOP.
    """
    surge_pa = water_hammer_overpressure_pa(
        velocity_change_m_s, density, wave_speed_m_s, damping
    )
    p_max = nominal_pressure_pa + surge_pa
    if maop_pa <= 0.0:
        ratio = 1.0
    else:
        ratio = p_max / maop_pa
    if ratio >= 1.0:
        band = "HIGH"
    elif ratio >= LOW_RISK_RATIO:
        band = "MEDIUM"
    else:
        band = "LOW"
    return {
        "surge_pressure_pa": surge_pa,
        "max_surge_pressure_pa": p_max,
        "maop_pa": maop_pa,
        "ratio_to_maop": ratio,
        "risk_band": band,
    }


def surge_diagnostic(
    component: str, nominal_pressure_pa: float, velocity_change_m_s: float,
    maop_pa: float, **kwargs,
) -> PhysicsDiagnostic:
    """Build a PhysicsDiagnostic from a surge risk evaluation."""
    risk = surge_risk(nominal_pressure_pa, velocity_change_m_s, maop_pa, **kwargs)
    band = risk["risk_band"]
    severity = "error" if band == "HIGH" else ("warning" if band == "MEDIUM" else "info")
    return PhysicsDiagnostic(
        severity=severity,
        code="SURGE_HIGH_RISK" if band == "HIGH" else (
            "SURGE_ELEVATED" if band == "MEDIUM" else "SURGE_OK"),
        component=component,
        message=(f"Water hammer: P_max {risk['max_surge_pressure_pa']:.0f} Pa vs "
                 f"MAOP {maop_pa:.0f} Pa ({band} risk)."),
        value=risk["max_surge_pressure_pa"],
        limit=maop_pa,
    )
