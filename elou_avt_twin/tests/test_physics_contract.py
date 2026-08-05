"""
test_physics_contract.py
========================
Regression tests for the Physics Contract (PHASE 2-3) fixes:

  * canonical unit conversions          (calculation_core.units)
  * strict Stream composition contract  (mass fractions, sum = 1)
  * mass<->molar / mass<->volumetric consistency on Stream
  * rigorous enthalpy: H = integral(Cp dT) on IdealThermodynamics
  * PR water normal boiling point and latent heat
  * salt non-volatility in the PR flash
  * unknown-component rejection in the PR EOS
  * ELOU component-conserving salt/water balance
  * tank / vessel overflow without mass loss
  * heater outlet-temperature duty limiting (energy balance preserved)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import numpy as np

from calculation_core.units import (
    celsius_to_kelvin, kelvin_to_celsius,
    bar_to_pa, pa_to_bar,
    mass_to_mole_fractions, mole_to_mass_fractions,
    mass_to_molar_flow, molar_to_mass_flow,
    mean_molecular_weight,
)
from calculation_core.thermodynamics.base import IdealThermodynamics
from calculation_core.thermodynamics.components import COMPONENTS
from calculation_core.thermodynamics.pr_eos import PengRobinsonThermodynamics
from calculation_core.thermodynamics.fractions import FRACTION_COMPONENTS
from models.stream import Stream, Phase
from equipment.elou import ELOU
from equipment.tank import Tank
from equipment.heater import Heater


# ---------------------------------------------------------------------------
# Canonical units
# ---------------------------------------------------------------------------

def test_temperature_and_pressure_conversions():
    assert celsius_to_kelvin(0.0) == pytest.approx(273.15)
    assert kelvin_to_celsius(273.15) == pytest.approx(0.0)
    assert bar_to_pa(1.0) == pytest.approx(1e5)
    assert pa_to_bar(1e5) == pytest.approx(1.0)
    assert bar_to_pa(1.01325) == pytest.approx(101325.0)


def test_mole_fraction_conversions_round_trip():
    mw = {"oil": 0.250, "water": 0.018, "salt": 0.058, "naphtha": 0.100}
    w = {"oil": 0.5, "water": 0.3, "salt": 0.1, "naphtha": 0.1}
    x = mass_to_mole_fractions(w, mw)
    assert sum(x.values()) == pytest.approx(1.0, abs=1e-12)
    w2 = mole_to_mass_fractions(x, mw)
    assert sum(w2.values()) == pytest.approx(1.0, abs=1e-12)
    for k in mw:
        assert w2[k] == pytest.approx(w[k], rel=1e-9)


def test_mole_fraction_unknown_component_rejected():
    with pytest.raises(ValueError):
        mass_to_mole_fractions({"oil": 1.0}, {"water": 0.018})


def test_mean_molecular_weight_flow_identity():
    mw = {"frac_nk62": 0.070, "frac_mazut": 0.45}
    w = {"frac_nk62": 0.5, "frac_mazut": 0.5}
    M = mean_molecular_weight(w, mw)
    assert M == pytest.approx(1.0 / (0.5 / 0.070 + 0.5 / 0.45))
    mass_flow = 100.0
    molar_flow = mass_to_molar_flow(mass_flow, M)
    assert molar_to_mass_flow(molar_flow, M) == pytest.approx(mass_flow, rel=1e-12)


# ---------------------------------------------------------------------------
# Strict Stream composition contract
# ---------------------------------------------------------------------------

def test_stream_composition_strict_sum():
    s = Stream(temperature=300, pressure=101325, mass_flow=10.0,
               composition={"oil": 1.0})
    assert s.composition == {"oil": 1.0}


def test_stream_composition_no_silent_normalisation():
    # sum = 0.9 must be rejected, NOT silently renormalised to 1.0.
    with pytest.raises(ValueError):
        Stream(temperature=300, pressure=101325, mass_flow=10.0,
               composition={"oil": 0.9})
    with pytest.raises(ValueError):
        Stream(temperature=300, pressure=101325, mass_flow=10.0,
               composition={"oil": 1.1})
    with pytest.raises(ValueError):
        Stream(temperature=300, pressure=101325, mass_flow=10.0,
               composition={"oil": 1.2, "water": -0.2})


def test_stream_mole_fractions_and_mean_molar_mass():
    s = Stream(temperature=300, pressure=101325, mass_flow=100.0,
               composition={"frac_nk62": 0.5, "frac_mazut": 0.5})
    mw = {c: d["molar_mass"] for c, d in FRACTION_COMPONENTS.items()}
    x = s.mole_fractions(mw)
    assert sum(x.values()) == pytest.approx(1.0, abs=1e-12)
    M = s.mean_molar_mass(mw)
    # molar_flow * Mw must recover the mass flow
    assert molar_to_mass_flow(s.mass_flow / M, M) == pytest.approx(s.mass_flow, rel=1e-12)


def test_stream_flow_consistency():
    mw = {"frac_mazut": 0.45}
    s = Stream(temperature=300, pressure=101325, mass_flow=100.0,
               density=850.0, composition={"frac_mazut": 1.0})
    vol = s.mass_flow / s.density
    s2 = s.copy_with(volumetric_flow=vol)
    s2.validate_consistency(mw=mw)  # molar_flow not set -> skipped, no error

    s3 = s.copy_with(volumetric_flow=vol * 2.0)
    with pytest.raises(ValueError):
        s3.validate_consistency()


# ---------------------------------------------------------------------------
# IdealThermodynamics: enthalpy consistent with Cp (H' = Cp)
# ---------------------------------------------------------------------------

def test_ideal_enthalpy_matches_cp_integral():
    thermo = IdealThermodynamics(COMPONENTS)
    comp = {"oil": 0.6, "water": 0.4}
    T = 350.0
    P = 101325.0
    h = thermo.calculate_enthalpy(T, P, comp)
    cp = thermo.calculate_cp(T, P, comp)
    h_plus = thermo.calculate_enthalpy(T + 1.0, P, comp)
    # finite difference: dH/dT ~ Cp  (H is exact integral of Cp)
    assert (h_plus - h) / 1.0 == pytest.approx(cp, rel=1e-3)


def test_ideal_enthalpy_reference_zero():
    thermo = IdealThermodynamics(COMPONENTS)
    comp = {"oil": 1.0}
    # H(Tref) must be exactly 0
    assert thermo.calculate_enthalpy(298.15, 101325.0, comp) == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Peng-Robinson: water normal boiling point & latent heat
# ---------------------------------------------------------------------------

@pytest.fixture
def pr():
    return PengRobinsonThermodynamics(FRACTION_COMPONENTS)


def test_pr_water_normal_boiling_point(pr):
    # Psat(H2O) = 101325 Pa at T = 373.15 K (NBP).  The PR bubble point of
    # pure water at 1 atm must land within a few K of 373.15.
    tb = pr.bubble_temperature(101325.0, ["water"], np.array([1.0]), rigorous=True)
    assert abs(tb - 373.15) < 3.0, f"PR water NBP = {tb} K"


def test_pr_water_latent_heat_positive(pr):
    # At the 1 atm bubble point the vapour must carry more enthalpy than the
    # liquid (latent heat of vaporisation ~ 2.26 MJ/kg for water).
    T = 373.15
    P = 101325.0
    names = ["water"]
    z = np.array([1.0])
    h_l = float(pr.phase_enthalpy_molar(T, P, names, z, Phase.LIQUID))
    h_v = float(pr.phase_enthalpy_molar(T, P, names, z, Phase.VAPOR))
    d_h = h_v - h_l
    assert d_h > 1.0e3, f"Latent heat of water too small: {d_h} J/mol"
    # order of magnitude check: ~ 40.7 kJ/mol at NBP
    assert d_h < 1.0e6


def test_pr_salt_non_volatile_in_flash(pr):
    # Salt must never enter the vapour phase, even far above its (fake)
    # pseudo-critical point.
    names = ["water", "salt"]
    z = np.array([0.99, 0.01])
    beta, x, y = pr.flash_molar(500.0, 101325.0, names, z)
    assert beta > 0.0, "water should vaporise at 500K / 1 bar"
    salt_vapor = float(y[1])
    assert salt_vapor < 1e-6, f"Salt leaked into vapour: y_salt = {salt_vapor}"
    assert x[1] > 0.0, "Salt must stay in the liquid phase"


def test_pr_unknown_component_rejected(pr):
    with pytest.raises(ValueError):
        pr.calculate_enthalpy(300.0, 101325.0, {"nope": 1.0})
    with pytest.raises(ValueError):
        pr.flash_molar(400.0, 101325.0, ["nope"], np.array([1.0]))


# ---------------------------------------------------------------------------
# ELOU: component-conserving salt / water balance (F02 + F11)
# ---------------------------------------------------------------------------

def test_elou_component_balance():
    elou = ELOU("elou_E001", {})
    inlet = Stream(
        temperature=300.0, pressure=5e5, mass_flow=100.0,
        composition={"frac_mazut": 0.96, "water": 0.03, "salt": 0.01},
    )
    out = elou.step(1.0, inlet_stream=inlet)
    oil_out, brine = out["outlet_stream"], out["brine_stream"]

    assert sum(oil_out.composition.values()) == pytest.approx(1.0, abs=1e-9)
    assert sum(brine.composition.values()) == pytest.approx(1.0, abs=1e-9)

    for comp in ("salt", "water"):
        m_in = inlet.mass_flow * inlet.composition.get(comp, 0.0)
        m_oil = oil_out.mass_flow * oil_out.composition.get(comp, 0.0)
        m_brine = brine.mass_flow * brine.composition.get(comp, 0.0)
        assert m_in == pytest.approx(m_oil + m_brine, rel=1e-6), (
            f"Component {comp} not conserved: in={m_in}, "
            f"oil_out={m_oil}, brine={m_brine}"
        )
    # Overall mass balance: out + brine == in
    assert oil_out.mass_flow + brine.mass_flow == pytest.approx(inlet.mass_flow, rel=1e-9)


def test_elou_zero_salt_water_stream_still_valid():
    elou = ELOU("elou_E001", {})
    inlet = Stream(temperature=300.0, pressure=5e5, mass_flow=100.0,
                   composition={"frac_mazut": 1.0})
    out = elou.step(1.0, inlet_stream=inlet)
    assert out["outlet_stream"].mass_flow == pytest.approx(100.0, rel=1e-9)
    assert out["brine_stream"].composition["water"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Tank / vessel overflow: mass must not disappear (F07)
# ---------------------------------------------------------------------------

def test_tank_overflow_conserves_mass():
    tank = Tank("T1", {
        "diameter_m": 1.1284,   # area ~ 1.0 m^2
        "height_m": 0.5,
        "initial_level": 0.49,
        "setpoint_level": 0.49,
        "level_auto": False,
    })
    inlet = Stream(temperature=300.0, pressure=101325.0, mass_flow=100.0,
                   density=850.0, composition={"frac_mazut": 1.0})
    rho = 850.0
    area = tank.area
    level_prev = tank.level
    out = tank.step(1.0, inlet_stream=inlet, max_out=10.0)

    level_new = out["level"]
    overflow = out.get("overflow_mass", 0.0)
    m_out = out["out_flow"]
    m_in = 100.0

    assert level_new == pytest.approx(0.5, abs=1e-9), "Level must clamp at height"
    assert overflow > 0.0, "Overflow must have occurred"
    # inventory change + outflow == inflow  (no mass destroyed)
    d_stored = (level_new - level_prev) * rho * area
    assert d_stored + m_out == pytest.approx(m_in, rel=1e-9)


# ---------------------------------------------------------------------------
# Heater: outlet-temperature limiting preserves the energy balance (F05)
# ---------------------------------------------------------------------------

def test_heater_duty_limit_preserves_energy_balance():
    pr = PengRobinsonThermodynamics(FRACTION_COMPONENTS)
    heater = Heater("furnace_F101", {
        "max_heat_duty": 1e9,
        "efficiency": 0.85,
        "heating_value": 40e6,
        "max_outlet_temp": 700.0,
    })
    inlet = Stream(
        temperature=400.0, pressure=2e5, mass_flow=100.0,
        composition={"frac_mazut": 1.0},
    )
    inlet.enthalpy = pr.calculate_enthalpy(inlet.temperature, inlet.pressure, inlet.composition)
    heater.apply_action("SET_VALUE", 100.0)  # huge fuel flow -> huge duty

    for _ in range(10):
        out = heater.step(1.0, inlet_stream=inlet, thermo=pr)

    s_out = out["outlet_stream"]
    assert s_out.temperature <= 700.0 + 1e-6, f"T_out={s_out.temperature} K"
    assert heater.duty_limited is True
    # energy balance: H_out = H_in + Q/m  (exactly, by construction)
    h_in = inlet.enthalpy
    h_out_balance = h_in + heater.duty / inlet.mass_flow
    assert s_out.enthalpy == pytest.approx(h_out_balance, rel=1e-6)
