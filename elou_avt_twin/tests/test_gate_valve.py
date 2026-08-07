"""test_gate_valve.py — изолированные физические тесты задвижки (ТЗ §26)."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from equipment.gate_valve import GateValve
from models.stream import Stream


def _gv(**over):
    return GateValve("GV001", over)


def _oil():
    return Stream(temperature=300.0, pressure=10e5, mass_flow=10.0,
                  density=850.0, composition={"frac_mazut": 1.0})


def test_gate_valve_open_passes_through():
    gv = _gv()
    out = gv.step(1.0, inlet_stream=_oil())
    assert out["open"] is True
    assert out["blocked"] is False
    assert out["flow_out"] == pytest.approx(10.0)
    assert out["outlet_stream"].mass_flow == pytest.approx(10.0)


def test_gate_valve_closed_blocks():
    gv = _gv()
    gv.apply_action("CLOSE")
    out = gv.step(1.0, inlet_stream=_oil())
    assert out["open"] is False
    assert out["blocked"] is True
    assert out["flow_out"] == 0.0
    assert out["outlet_stream"].mass_flow == 0.0


def test_gate_valve_fail_closed():
    gv = _gv()
    gv.apply_action("FAIL")
    out = gv.step(1.0, inlet_stream=_oil())
    assert out["open"] is False
    assert out["blocked"] is True


def test_gate_valve_no_inlet():
    gv = _gv()
    out = gv.step(1.0)
    assert out["flow_out"] == 0.0
    assert out["open"] is True


def test_gate_valve_sets_open_state():
    gv = _gv()
    assert gv.get_state().extra["open"] is True
    gv.apply_action("CLOSE")
    assert gv.get_state().extra["open"] is False


def test_gate_valve_set_value_threshold():
    gv = _gv()
    gv.apply_action("SET_VALUE", 0.4)
    assert gv.is_open is False
    gv.apply_action("SET_VALUE", 0.5)
    assert gv.is_open is True
