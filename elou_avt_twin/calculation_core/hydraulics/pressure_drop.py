"""
pressure_drop.py
================
Pipe / valve / equipment pressure-drop physics (ТЗ sections 15-18).

All functions use canonical SI units:
    pressure drop  -> Pa
    mass flow      -> kg/s
    volumetric flow-> m^3/s
    length         -> m
    diameter       -> m
    roughness      -> m
    density        -> kg/m^3
    viscosity      -> Pa*s

Darcy-Weisbach:  ΔP = f · (L/D) · (ρ v² / 2)
with the friction factor covering laminar / transitional / turbulent regimes
(ТЗ section 15) and an optional K-coefficient term for minor losses
(ТЗ section 16).  Static head is ΔP_static = ρ·g·Δz (ТЗ section 17).
"""

import math

import numpy as np

from physics.state import PhysicsDiagnostic, SolverStatus

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
G = 9.81  # m/s^2 gravitational acceleration

RE_LAMINAR_MAX = 2300.0
RE_TURBULENT_MIN = 4000.0
DEFAULT_ROUGHNESS = 0.000045  # m, commercial steel


# ---------------------------------------------------------------------------
# Friction factor
# ---------------------------------------------------------------------------

def friction_factor(reynolds: float, roughness_m: float = DEFAULT_ROUGHNESS,
                    diameter_m: float = 0.1) -> float:
    """Darcy friction factor (dimensionless) covering all flow regimes.

    Laminar:   f = 64/Re
    Turbulent: Haaland approximation of Colebrook-White
    Transitional: linear interpolation between the two at the regime borders
    """
    if reynolds <= RE_LAMINAR_MAX:
        return 64.0 / max(reynolds, 1e-12)
    if reynolds >= RE_TURBULENT_MIN:
        eps_d = max(roughness_m, 0.0) / max(diameter_m, 1e-12)
        re = max(reynolds, 1.0)
        try:
            f = (1.0 / (-1.8 * math.log10((eps_d / 3.7) ** 1.11 + 6.9 / re))) ** 2
        except (ValueError, OverflowError):
            f = 0.02
        return f
    # Transitional regime: blend between laminar and turbulent values.
    f_lam = 64.0 / reynolds
    f_turb = friction_factor(RE_TURBULENT_MIN, roughness_m, diameter_m)
    t = (reynolds - RE_LAMINAR_MAX) / (RE_TURBULENT_MIN - RE_LAMINAR_MAX)
    return f_lam + t * (f_turb - f_lam)


# ---------------------------------------------------------------------------
# Pipe pressure drop (Darcy-Weisbach)
# ---------------------------------------------------------------------------

def calculate_pipe_pressure_drop(
    flow_rate: float,
    density: float,
    viscosity: float,
    length: float,
    diameter: float,
    roughness: float = DEFAULT_ROUGHNESS,
    minor_loss_k: float = 0.0,
) -> float:
    """Darcy-Weisbach pipe pressure drop [Pa].

    ``flow_rate`` is the MASS flow [kg/s].  ``minor_loss_k`` is the sum of
    dimensionless K coefficients for elbows/tees/reducers/entrances/exits
    (ТЗ section 16).  Returns 0 for zero flow or non-positive diameter.
    """
    if flow_rate <= 0.0 or diameter <= 0.0 or length <= 0.0:
        return 0.0
    area = math.pi * (diameter ** 2) / 4.0
    velocity = flow_rate / (density * area)
    reynolds = (density * velocity * diameter) / max(viscosity, 1e-12)
    f = friction_factor(reynolds, roughness, diameter)
    velocity_head = 0.5 * density * velocity * velocity
    dp_friction = f * (length / diameter) * velocity_head
    dp_minor = minor_loss_k * velocity_head
    return dp_friction + dp_minor


def pipe_dp_by_volume(
    volumetric_flow_m3_s: float,
    density: float,
    viscosity: float,
    length: float,
    diameter: float,
    roughness: float = DEFAULT_ROUGHNESS,
    minor_loss_k: float = 0.0,
) -> float:
    """Pipe pressure drop [Pa] from a volumetric flow [m^3/s]."""
    return calculate_pipe_pressure_drop(
        flow_rate=volumetric_flow_m3_s * density,
        density=density,
        viscosity=viscosity,
        length=length,
        diameter=diameter,
        roughness=roughness,
        minor_loss_k=minor_loss_k,
    )


# ---------------------------------------------------------------------------
# Valve (ТЗ section 18)
# ---------------------------------------------------------------------------

def valve_resistance(density: float, cv: float, opening: float, min_opening: float = 1e-4) -> float:
    """Quadratic resistance coefficient k in ΔP = k·m², m in kg/s.

    Physical control-valve characteristic: a fully open valve (x = 1) imposes
    no drop at all, and the resistance grows steeply as the valve closes -- a
    liquid through a nearly-open valve (x = 0.95) still sees almost no drop.

        k(x) = (1/(ρ·Cv²)) · ((1-x)/x)²

    ``cv`` is the SI flow coefficient [m^3/s per sqrt(Pa/(kg/m^3))].
    """
    x = min(max(min_opening, float(opening)), 1.0)
    base = 1.0 / (max(density, 1e-9) * max(cv, 1e-12) * max(cv, 1e-12))
    return base * ((1.0 - x) / x) ** 2.0


def calculate_valve_flow(cv: float, opening: float, delta_p: float, density: float) -> float:
    """Valve volumetric flow [m^3/s]: Q = Cv·x·sqrt(ΔP/ρ)."""
    if delta_p <= 0.0 or opening <= 0.0:
        return 0.0
    return cv * max(0.0, min(1.0, opening)) * math.sqrt(max(0.0, delta_p) / max(density, 1e-9))


# ---------------------------------------------------------------------------
# Equipment pressure drop (ТЗ section 27)
# ---------------------------------------------------------------------------

def equipment_resistance(density: float, dp_nominal_pa: float, flow_nominal_kg_s: float) -> float:
    """Quadratic resistance coefficient K in ΔP = K·m²/ρ for an apparatus.

    ``dp_nominal_pa`` is the pressure drop at the nominal flow
    ``flow_nominal_kg_s``.  Falls back to a small positive base so a fully
    open apparatus still has a finite, well-conditioned resistance.
    """
    base = 1e-9
    if flow_nominal_kg_s <= 0.0:
        return base
    k = dp_nominal_pa * max(density, 1e-9) / (flow_nominal_kg_s * flow_nominal_kg_s)
    return max(base, k)


def equipment_pressure_drop(mass_flow_kg_s: float, density: float, k: float) -> float:
    """Pressure drop [Pa] of an apparatus at a mass flow: ΔP = K·m²/ρ."""
    return k * mass_flow_kg_s * mass_flow_kg_s / max(density, 1e-9)


# ---------------------------------------------------------------------------
# Static head (ТЗ section 17)
# ---------------------------------------------------------------------------

def static_head_pressure(density: float, delta_elevation_m: float, g: float = G) -> float:
    """Hydrostatic pressure contribution [Pa]: ΔP = ρ·g·Δz.

    ``delta_elevation_m`` is the outlet elevation minus inlet elevation; a
    positive rise costs pressure (must be overcome), a fall gains pressure.
    """
    return density * g * delta_elevation_m


# ---------------------------------------------------------------------------
# Convenience: total serial-line drop
# ---------------------------------------------------------------------------

def serial_line_resistance_coefficient(
    mass_flow_kg_s: float,
    density: float,
    viscosity: float,
    pipes: list,
    valves: list,
    equipment_k: float = 0.0,
) -> float:
    """Sum of the quadratic resistance coefficients of a serial chain.

    ``pipes`` is a list of dicts with length_m/diameter_m/roughness_m;
    ``valves`` a list of (cv, opening).  Each element contributes
    ΔP = k_i·m², so the coefficients add.
    """
    k_total = equipment_k
    for pipe in pipes:
        dp = calculate_pipe_pressure_drop(
            mass_flow_kg_s, density, viscosity,
            pipe.get("length_m", 0.0), pipe.get("diameter_m", 0.1),
            pipe.get("roughness_m", DEFAULT_ROUGHNESS),
            pipe.get("minor_loss_k", 0.0),
        )
        if dp > 0.0:
            k_total += dp / max(mass_flow_kg_s * mass_flow_kg_s, 1e-30)
    for cv, opening in valves:
        k_total += valve_resistance(density, cv, opening)
    return k_total
