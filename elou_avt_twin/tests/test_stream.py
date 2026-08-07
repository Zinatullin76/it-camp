"""test_stream.py — ТЗ §45, §11: Stream model, composition contract, phase, consistency."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from models.stream import Stream, Phase
from calculation_core.thermodynamics.fractions import FRACTION_COMPONENTS


def _stream(**kw):
    base = dict(temperature=300.0, pressure=101325.0, mass_flow=10.0,
                composition={"frac_mazut": 1.0})
    base.update(kw)
    return Stream(**base)


def test_phase_enum():
    assert {p.value for p in Phase} == {"LIQUID", "VAPOR", "TWO_PHASE"}


def test_composition_must_sum_to_one():
    with pytest.raises(ValueError):
        _stream(composition={"frac_mazut": 0.9})
    with pytest.raises(ValueError):
        _stream(composition={"frac_mazut": 1.1})
    with pytest.raises(ValueError):
        _stream(composition={"frac_mazut": 0.5, "water": 0.6})


def test_negative_fraction_rejected():
    with pytest.raises(ValueError):
        _stream(composition={"frac_mazut": 1.2, "water": -0.2})


def test_physical_bounds():
    s = _stream()
    s.validate_physics()
    with pytest.raises(ValueError):
        _stream(temperature=50.0).validate_physics()
    with pytest.raises(ValueError):
        _stream(pressure=1.0).validate_physics()


def test_copy_with_is_immutable():
    s = _stream()
    s2 = s.copy_with(mass_flow=20.0)
    assert s2.mass_flow == 20.0
    assert s.mass_flow == 10.0


def test_flow_consistency_mass_volume():
    s = _stream(mass_flow=100.0, density=850.0)
    s2 = s.copy_with(volumetric_flow=100.0 / 850.0)
    s2.validate_consistency()  # must not raise
    s3 = s.copy_with(volumetric_flow=5.0)
    with pytest.raises(ValueError):
        s3.validate_consistency()


def test_mole_fraction_round_trip():
    mw = {c: d["molar_mass"] for c, d in FRACTION_COMPONENTS.items()}
    comp = {"frac_nk62": 0.3, "frac_105_180": 0.3, "frac_mazut": 0.4}
    s = _stream(composition=comp)
    x = s.mole_fractions(mw)
    assert sum(x.values()) == pytest.approx(1.0, abs=1e-12)
    M = s.mean_molar_mass(mw)
    assert 0.03 < M < 0.5
