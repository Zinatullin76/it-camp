"""test_units.py — ТЗ §45, §7: canonical SI unit contract."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from calculation_core.units import (
    celsius_to_kelvin, kelvin_to_celsius, bar_to_pa, pa_to_bar,
    mass_to_mole_fractions, mole_to_mass_fractions,
    mass_to_molar_flow, molar_to_mass_flow,
    mass_to_volumetric_flow, volumetric_to_mass_flow,
    mean_molecular_weight, KELVIN_ZERO_C, BAR_TO_PA,
)


def test_kelvin_celsius_round_trip():
    assert celsius_to_kelvin(0.0) == pytest.approx(KELVIN_ZERO_C)
    assert celsius_to_kelvin(25.0) == pytest.approx(298.15)
    assert kelvin_to_celsius(298.15) == pytest.approx(25.0)


def test_bar_pa_round_trip():
    assert bar_to_pa(1.0) == pytest.approx(BAR_TO_PA)
    assert bar_to_pa(1.01325) == pytest.approx(101325.0)
    assert pa_to_bar(1e5) == pytest.approx(1.0)


def test_mass_molar_flow_conversion():
    n = mass_to_molar_flow(100.0, 0.1)
    assert n == pytest.approx(1000.0)
    assert molar_to_mass_flow(n, 0.1) == pytest.approx(100.0)
    with pytest.raises(ValueError):
        mass_to_molar_flow(100.0, 0.0)


def test_mass_volume_flow_conversion():
    q = mass_to_volumetric_flow(850.0, 850.0)
    assert q == pytest.approx(1.0)
    assert volumetric_to_mass_flow(q, 850.0) == pytest.approx(850.0)
    with pytest.raises(ValueError):
        mass_to_volumetric_flow(1.0, 0.0)


def test_mole_mass_fraction_round_trip():
    mw = {"a": 0.1, "b": 0.02}
    w = {"a": 0.6, "b": 0.4}
    x = mass_to_mole_fractions(w, mw)
    assert sum(x.values()) == pytest.approx(1.0, abs=1e-12)
    w2 = mole_to_mass_fractions(x, mw)
    for k in mw:
        assert w2[k] == pytest.approx(w[k], rel=1e-9)


def test_mean_molecular_weight_and_flow_identity():
    mw = {"a": 0.1, "b": 0.02}
    w = {"a": 0.5, "b": 0.5}
    M = mean_molecular_weight(w, mw)
    assert M == pytest.approx(1.0 / (0.5 / 0.1 + 0.5 / 0.02))
    n = mass_to_molar_flow(100.0, M)
    assert molar_to_mass_flow(n, M) == pytest.approx(100.0, rel=1e-12)


def test_unknown_component_rejected():
    with pytest.raises(ValueError):
        mass_to_mole_fractions({"x": 1.0}, {"y": 0.1})
    with pytest.raises(ValueError):
        mean_molecular_weight({"x": 1.0}, {"y": 0.1})
