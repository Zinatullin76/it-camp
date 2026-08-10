"""test_pump.py — изолированные физические тесты центробежного насоса (ТЗ §19-22, §32)."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from equipment.pump import Pump
from models.stream import Stream
from calculation_core.validation.balance_checker import check_energy_balance

PARAMS = {
    "nominal_volumetric_flow_m3_s": 0.1,
    "nominal_head_pa": 5e5,
    "shutoff_head_pa": 6.5e5,
    "efficiency_nominal": 1.0,
    "nominal_speed": 1450.0,
}


def _pump(over=None, **kwargs):
    params = {**PARAMS, **(over or {}), **kwargs}
    p = Pump("P001", params)
    p.apply_action("TURN_ON")
    return p


def _oil(mass_flow=10.0, pressure=101325.0):
    return Stream(temperature=300.0, pressure=pressure, mass_flow=mass_flow,
                  density=850.0, composition={"frac_mazut": 1.0})


def test_pump_pressure_rise_matches_curve():
    pump = _pump()
    out = pump.step(1.0, inlet_stream=_oil())
    expected = pump.curve.pressure_rise(10.0 / 850.0, 1.0)
    assert out["pressure_rise_pa"] == pytest.approx(expected)
    assert out["outlet_stream"].pressure == pytest.approx(101325.0 + expected)


def test_pump_energy_balance():
    pump = _pump()
    s_in = _oil()
    out = pump.step(1.0, inlet_stream=s_in)
    s_out = out["outlet_stream"]
    res = check_energy_balance([s_in], [s_out], work=out["power"])
    assert res["is_converged"] is True


def test_pump_speed_reduces_head():
    pump = _pump()
    pump.apply_action("SET_SPEED", 0.5 * pump.nominal_speed)
    out = pump.step(1.0, inlet_stream=_oil())
    assert out["pressure_rise_pa"] < 0.5 * 6.5e5  # N² -> ~0.25 of shutoff
    assert out["pressure_rise_pa"] > 0.0


def test_pump_off_no_flow():
    pump = _pump()
    pump.apply_action("TURN_OFF")
    out = pump.step(1.0, inlet_stream=_oil())
    assert out["running"] is False
    assert out["outlet_stream"].mass_flow == 0.0


def test_pump_cavitation_warning_and_flow_loss():
    pump = _pump({"npshr_pa": 3.0 * 9.81 * 1000.0})
    s_low = _oil(pressure=3e4)
    out = pump.step(1.0, inlet_stream=s_low)
    assert out["cavitating"] is True
    assert any(d.code == "PUMP_CAVITATION" for d in out["diagnostics"])
    assert out["mass_flow_kg_s"] < 10.0


def test_pump_no_cavitation_at_normal_suction():
    pump = _pump({"npshr_pa": 3.0 * 9.81 * 1000.0})
    out = pump.step(1.0, inlet_stream=_oil())
    assert out["cavitating"] is False


def test_pump_flow_higher_speed_higher_capacity():
    p1 = _pump()
    p2 = _pump()
    p2.apply_action("SET_SPEED", 1.5 * p2.nominal_speed)
    o1 = p1.step(1.0)  # standalone: design point
    o2 = p2.step(1.0)
    assert o2["volumetric_flow_m3_s"] == pytest.approx(o1["volumetric_flow_m3_s"] * 1.5, rel=1e-6)
    assert o2["pressure_rise_pa"] > o1["pressure_rise_pa"]
