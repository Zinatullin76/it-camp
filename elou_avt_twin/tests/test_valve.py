"""test_valve.py — изолированные физические тесты регулирующего клапана (ТЗ §23-25)."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from equipment.valve import Valve
from models.stream import Stream

PARAMS = {"valve_constant": 0.02, "cv": 0.02, "max_valve_position": 1.0}


def _valve(over=None, **kwargs):
    return Valve("V001", {**PARAMS, **(over or {}), **kwargs})


def _oil(pressure=10e5, mass_flow=10.0):
    return Stream(temperature=300.0, pressure=pressure, mass_flow=mass_flow,
                  density=850.0, composition={"frac_mazut": 1.0})


def test_valve_pressure_drop_equation():
    valve = _valve()
    out = valve.step(1.0, inlet_stream=_oil())
    k = valve.params["valve_constant"]
    expected = (out["mass_flow_kg_s"] / k) ** 2
    assert out["pressure_drop_pa"] == pytest.approx(expected, rel=1e-9)


def test_valve_open_increases_flow():
    lo = _valve({"valve_position": 0.1})
    hi = _valve({"valve_position": 1.0})
    o_lo = lo.step(1.0, inlet_stream=_oil())
    o_hi = hi.step(1.0, inlet_stream=_oil())
    assert o_hi["mass_flow_kg_s"] > o_lo["mass_flow_kg_s"]
    assert o_hi["pressure_drop_pa"] > o_lo["pressure_drop_pa"]


def test_valve_closed_blocks():
    v = _valve({"valve_position": 0.0})
    out = v.step(1.0, inlet_stream=_oil())
    assert out["blocked"] is True
    assert out["mass_flow_kg_s"] == 0.0
    assert out["outlet_stream"].mass_flow == 0.0


def test_valve_pressure_drop_is_lossless():
    v = _valve()
    s_in = _oil()
    out = v.step(1.0, inlet_stream=s_in)
    s_out = out["outlet_stream"]
    assert s_out.mass_flow == pytest.approx(s_in.mass_flow)
    assert s_out.temperature == pytest.approx(s_in.temperature)  # no heat added
    assert s_out.pressure == pytest.approx(s_in.pressure - out["pressure_drop_pa"])


def test_valve_pressure_drop_bounded():
    v = _valve({"valve_constant": 1e-6})
    out = v.step(1.0, inlet_stream=_oil())
    # k tiny => enormous drop; must still stay below inlet pressure (no negative p)
    assert out["outlet_stream"].pressure >= 0.0
