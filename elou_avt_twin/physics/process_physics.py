"""
process_physics.py
==================
Physical model of the ELOU-AVT process.

All equations are simplified engineering approximations suitable for an MVP
operator training simulator. They are NOT certified industrial models.
Each equation is documented with:
  - Formula
  - Physical meaning
  - Units
  - Applicability range
  - Simplification notes (tagged [MVP SIMPLIFICATION])

ELOU-AVT process overview:
  1. Feed oil enters the desalting unit (ELOU).
  2. Desalted oil is preheated in heat exchangers.
  3. Preheated oil enters the atmospheric furnace.
  4. Hot oil is fed to the atmospheric distillation column (AVT).
  5. Distillate fractions are drawn off.
  6. Residue goes to the vacuum column.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Optional

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------
G = 9.81          # m/s^2  — gravitational acceleration
CP_OIL = 2100.0   # J/(kg·K) — specific heat capacity of crude oil [MVP SIMPLIFICATION: constant]
CP_WATER = 4186.0 # J/(kg·K) — specific heat capacity of water
RHO_OIL = 850.0   # kg/m^3  — crude oil density [MVP SIMPLIFICATION: constant]


# ---------------------------------------------------------------------------
# Material balance
# ---------------------------------------------------------------------------

def material_balance_level(
    level: float,
    flow_in: float,
    flow_out: float,
    tank_area: float,
    dt: float,
) -> float:
    """
    Compute new liquid level in a vessel.

    Formula:
        dh/dt = (Q_in - Q_out) / A
        h(t+dt) = h(t) + dh/dt * dt

    Parameters:
        level     : current liquid level [m]
        flow_in   : volumetric inflow [m³/s]
        flow_out  : volumetric outflow [m³/s]
        tank_area : cross-sectional area of the vessel [m²]
        dt        : time step [s]

    Returns:
        new_level [m]

    Applicability: 0 ≤ h ≤ H_max (clamped externally)
    [MVP SIMPLIFICATION]: constant density, no foam/entrainment
    """
    if tank_area <= 0.0:
        return level
    dh = (flow_in - flow_out) / tank_area * dt
    return max(0.0, level + dh)


def material_balance_flow(
    feed_flow: float,
    valve_cv: float,
    valve_position: float,
    delta_p: float,
    density: float = RHO_OIL,
) -> float:
    """
    Compute volumetric flow through a control valve.

    Formula (simplified Cv equation):
        Q = Cv * f(x) * sqrt(ΔP / ρ)

    where f(x) = x  (linear valve characteristic) [MVP SIMPLIFICATION]

    Parameters:
        feed_flow      : upstream nominal flow for reference [m³/s]
        valve_cv       : valve flow coefficient Cv [m³/s / sqrt(Pa/(kg/m³))]
        valve_position : valve opening [0..1]
        delta_p        : pressure drop across valve [Pa]
        density        : fluid density [kg/m³]

    Returns:
        volumetric flow [m³/s]

    Applicability: ΔP > 0, valve_position ∈ [0, 1]
    [MVP SIMPLIFICATION]: linear characteristic, incompressible flow
    """
    if delta_p <= 0.0 or valve_position <= 0.0:
        return 0.0
    return valve_cv * valve_position * np.sqrt(delta_p / density)


# ---------------------------------------------------------------------------
# Heat balance
# ---------------------------------------------------------------------------

def heat_balance_temperature(
    temp: float,
    heat_in: float,
    heat_out: float,
    mass: float,
    cp: float = CP_OIL,
    dt: float = 1.0,
) -> float:
    """
    Compute new temperature from heat balance.

    Formula:
        dT/dt = (Q_in - Q_out) / (m * Cp)
        T(t+dt) = T(t) + dT/dt * dt

    Parameters:
        temp     : current temperature [K]
        heat_in  : heat input rate [W]
        heat_out : heat output rate [W]
        mass     : fluid mass in vessel [kg]
        cp       : specific heat capacity [J/(kg·K)]
        dt       : time step [s]

    Returns:
        new temperature [K]

    Applicability: mass > 0
    [MVP SIMPLIFICATION]: lumped parameter model, no phase change
    """
    if mass <= 0.0:
        return temp
    dT = (heat_in - heat_out) / (mass * cp) * dt
    return temp + dT


def furnace_heat_output(
    fuel_flow: float,
    efficiency: float = 0.85,
    heating_value: float = 40e6,  # J/kg — typical fuel gas LHV [MVP SIMPLIFICATION]
) -> float:
    """
    Compute furnace heat output.

    Formula:
        Q_furnace = m_fuel * LHV * η

    Parameters:
        fuel_flow     : fuel mass flow [kg/s]
        efficiency    : thermal efficiency [dimensionless, 0..1]
        heating_value : lower heating value of fuel [J/kg]

    Returns:
        heat output [W]

    [MVP SIMPLIFICATION]: constant efficiency, no heat losses to environment
    """
    return fuel_flow * heating_value * efficiency


def heat_exchanger_duty(
    u: float,
    area: float,
    t_hot_in: float,
    t_hot_out: float,
    t_cold_in: float,
    t_cold_out: float,
    fouling_factor: float = 1.0,
) -> float:
    """
    Compute heat exchanger duty using LMTD method.

    Formula:
        Q = U * A * LMTD * fouling_factor

    LMTD = (ΔT1 - ΔT2) / ln(ΔT1/ΔT2)
    ΔT1 = T_hot_in  - T_cold_out
    ΔT2 = T_hot_out - T_cold_in

    Parameters:
        u             : overall heat transfer coefficient [W/(m²·K)]
        area          : heat transfer area [m²]
        t_hot_in      : hot stream inlet temperature [K]
        t_hot_out     : hot stream outlet temperature [K]
        t_cold_in     : cold stream inlet temperature [K]
        t_cold_out    : cold stream outlet temperature [K]
        fouling_factor: degradation factor [0..1], 1 = clean

    Returns:
        heat duty [W]

    Applicability: counter-current flow assumed [MVP SIMPLIFICATION]
    """
    dt1 = t_hot_in - t_cold_out
    dt2 = t_hot_out - t_cold_in
    if dt1 <= 0.0 or dt2 <= 0.0:
        return 0.0
    if abs(dt1 - dt2) < 1e-6:
        lmtd = dt1
    else:
        lmtd = (dt1 - dt2) / np.log(dt1 / dt2)
    return u * area * lmtd * fouling_factor


# ---------------------------------------------------------------------------
# Pressure dynamics
# ---------------------------------------------------------------------------

def pressure_dynamics_vessel(
    pressure: float,
    mass_flow_in: float,
    mass_flow_out: float,
    volume: float,
    temperature: float,
    dt: float,
    beta: float = 1e9,  # bulk modulus of oil [Pa] [MVP SIMPLIFICATION]
) -> float:
    """
    Compute pressure change in a liquid-filled vessel.

    Formula (liquid compressibility model):
        dP/dt = β / V * (Q_in - Q_out)
        P(t+dt) = P(t) + dP/dt * dt

    where β is the bulk modulus of the liquid.

    Parameters:
        pressure      : current pressure [Pa]
        mass_flow_in  : mass inflow [kg/s]
        mass_flow_out : mass outflow [kg/s]
        volume        : vessel volume [m³]
        temperature   : fluid temperature [K] (unused in simplified model)
        dt            : time step [s]
        beta          : bulk modulus [Pa]

    Returns:
        new pressure [Pa]

    [MVP SIMPLIFICATION]: isothermal, single-phase liquid, constant β
    """
    vol_flow_net = (mass_flow_in - mass_flow_out) / RHO_OIL
    dP = beta / volume * vol_flow_net * dt
    return pressure + dP


def pressure_dynamics_gas_vessel(
    pressure: float,
    molar_flow_in: float,
    molar_flow_out: float,
    volume: float,
    temperature: float,
    dt: float,
    R: float = 8.314,
) -> float:
    """
    Compute pressure change in a gas-phase vessel using ideal gas law.

    Formula:
        dP/dt = R * T / V * (n_in - n_out)
        P(t+dt) = P(t) + dP/dt * dt

    Parameters:
        pressure      : current pressure [Pa]
        molar_flow_in : molar inflow [mol/s]
        molar_flow_out: molar outflow [mol/s]
        volume        : vessel volume [m³]
        temperature   : gas temperature [K]
        dt            : time step [s]
        R             : universal gas constant [J/(mol·K)]

    Returns:
        new pressure [Pa]

    [MVP SIMPLIFICATION]: ideal gas, no condensation
    """
    dP = R * temperature / volume * (molar_flow_in - molar_flow_out) * dt
    return pressure + dP


# ---------------------------------------------------------------------------
# Pump model
# ---------------------------------------------------------------------------

def pump_flow(
    nominal_flow: float,
    efficiency: float = 1.0,
    running: bool = True,
) -> float:
    """
    Compute pump volumetric flow.

    Formula:
        Q = Q_nom * η  (if running)
        Q = 0          (if stopped)

    Parameters:
        nominal_flow : pump nominal flow [m³/s]
        efficiency   : current efficiency [0..1]
        running      : pump on/off state

    Returns:
        volumetric flow [m³/s]

    [MVP SIMPLIFICATION]: no pump curve, no cavitation model
    """
    if not running:
        return 0.0
    return nominal_flow * max(0.0, efficiency)


# ---------------------------------------------------------------------------
# Distillation column simplified model
# ---------------------------------------------------------------------------

def column_separation(
    feed_flow: float,
    feed_temperature: float,
    column_pressure: float,
    nominal_pressure: float = 101325.0,
    separation_efficiency: float = 0.85,
) -> Dict[str, float]:
    """
    Simplified distillation column separation model.

    [MVP SIMPLIFICATION]: This is a heuristic split model, NOT a rigorous
    VLE calculation. It distributes feed into light, medium, and heavy
    fractions based on temperature and pressure deviations.

    Formula (heuristic):
        f_light  = η * (T_feed / T_ref)^0.5 * (P_nom / P)^0.3
        f_heavy  = (1 - f_light) * 0.4
        f_medium = 1 - f_light - f_heavy

    Parameters:
        feed_flow           : feed volumetric flow [m³/s]
        feed_temperature    : feed temperature [K]
        column_pressure     : operating pressure [Pa]
        nominal_pressure    : design pressure [Pa]
        separation_efficiency: overall separation efficiency [0..1]

    Returns:
        dict with keys: light_fraction, medium_fraction, heavy_fraction [m³/s]
    """
    T_ref = 623.15  # K — typical AVT feed temperature ~350°C [MVP]
    f_light = separation_efficiency * (feed_temperature / T_ref) ** 0.5
    f_light *= (nominal_pressure / max(column_pressure, 1e3)) ** 0.3
    f_light = np.clip(f_light, 0.0, 0.7)
    f_heavy = (1.0 - f_light) * 0.4
    f_medium = 1.0 - f_light - f_heavy
    return {
        "light_fraction":  feed_flow * f_light,
        "medium_fraction": feed_flow * f_medium,
        "heavy_fraction":  feed_flow * f_heavy,
    }


# ---------------------------------------------------------------------------
# ELOU (desalting) simplified model
# ---------------------------------------------------------------------------

def elou_desalting(
    feed_flow: float,
    wash_water_ratio: float = 0.05,
    efficiency: float = 0.95,
    running: bool = True,
) -> Dict[str, float]:
    """
    Simplified ELOU desalting model.

    Formula:
        Q_desalted = Q_feed * η  (if running)
        Q_brine    = Q_feed * wash_water_ratio

    Parameters:
        feed_flow         : crude oil feed flow [m³/s]
        wash_water_ratio  : wash water to feed ratio [dimensionless]
        efficiency        : desalting efficiency [0..1]
        running           : ELOU operational state

    Returns:
        dict with keys: desalted_flow [m³/s], brine_flow [m³/s]

    [MVP SIMPLIFICATION]: no salt concentration dynamics, no emulsion model
    """
    if not running:
        return {"desalted_flow": 0.0, "brine_flow": 0.0}
    return {
        "desalted_flow": feed_flow * efficiency,
        "brine_flow":    feed_flow * wash_water_ratio,
    }
