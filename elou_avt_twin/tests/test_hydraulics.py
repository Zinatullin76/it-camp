"""
test_hydraulics.py
==================
Tests for the hydraulic core: pump curve + affinity laws (ТЗ 19-22),
NPSH cavitation (ТЗ 32), Darcy-Weisbach pipe drops (ТЗ 15-17) and the
water-hammer surge model (ТЗ 36).
"""

import math

import pytest

from physics.pump_curve import PumpCurve, curve_from_params
from physics.water_hammer import surge_risk, surge_diagnostic, water_hammer_overpressure_pa
from calculation_core.hydraulics import pressure_drop as pd
from equipment.pump import Pump
from models.stream import Stream


# ---------------------------------------------------------------------------
# Pump curve (ТЗ 19-22)
# ---------------------------------------------------------------------------

class TestPumpCurve:
    def test_dead_head_at_zero_flow(self):
        """At Q=0 the curve must deliver the shut-off pressure (ТЗ 20)."""
        c = PumpCurve(shutoff_head_pa=6.5e5, design_volumetric_flow_m3_s=0.1,
                      design_head_pa=5e5)
        assert c.pressure_rise(0.0) == pytest.approx(6.5e5)

    def test_passes_through_design_point(self):
        """The curve must pass through the design (BEP) point."""
        c = PumpCurve(shutoff_head_pa=6.5e5, design_volumetric_flow_m3_s=0.1,
                      design_head_pa=5e5)
        assert c.pressure_rise(0.1) == pytest.approx(5e5, rel=1e-6)

    def test_pressure_decreases_with_flow(self):
        """Centrifugal behaviour: head falls as flow grows."""
        c = PumpCurve(6.5e5, 0.1, 5e5)
        assert c.pressure_rise(0.02) > c.pressure_rise(0.08)

    def test_affinity_flow_scales_with_speed(self):
        """Q ∝ N: the design flow at speed N is N× the nominal flow."""
        c = PumpCurve(6.5e5, 0.1, 5e5)
        assert c.design_flow_at_speed(1.0) == pytest.approx(0.1)
        assert c.design_flow_at_speed(0.5) == pytest.approx(0.05)
        assert c.design_flow_at_speed(1.2) == pytest.approx(0.12)

    def test_affinity_head_scales_with_speed_squared(self):
        """ΔP ∝ N²: the dead-head at speed N is N²× the nominal dead-head."""
        c = PumpCurve(6.5e5, 0.1, 5e5)
        assert c.dead_head_pa(0.5) == pytest.approx(6.5e5 * 0.25)
        assert c.dead_head_pa(1.2) == pytest.approx(6.5e5 * 1.44)

    def test_power_scales_with_speed_cubed(self):
        """Power ∝ N³ follows from ΔP ∝ N² and Q ∝ N."""
        c = PumpCurve(6.5e5, 0.1, 5e5)
        q1, q05 = 0.1, 0.05
        p1 = c.power_w(q1, 1.0)
        p05 = c.power_w(q05, 0.5)
        assert p05 == pytest.approx(p1 * 0.5 ** 3, rel=1e-9)

    def test_curve_from_legacy_params(self):
        """Legacy 'nominal_flow'/'delta_p' still build a usable curve."""
        c = curve_from_params({"nominal_flow": 0.1, "delta_p": 5e5})
        assert c.design_flow_at_speed() == pytest.approx(0.1)
        assert c.pressure_rise(0.1) <= c.dead_head_pa()


# ---------------------------------------------------------------------------
# Pump equipment + NPSH (ТЗ 32)
# ---------------------------------------------------------------------------

class TestPumpNpsh:
    def _pump(self, params=None):
        base = {
            "nominal_volumetric_flow_m3_s": 0.1,
            "nominal_head_pa": 5e5,
            "shutoff_head_pa": 6.5e5,
            "efficiency_nominal": 1.0,
        }
        if params:
            base.update(params)
        p = Pump("P001", base)
        p.apply_action("TURN_ON")
        return p

    def test_pressure_rise_matches_curve(self):
        pump = self._pump()
        s_in = Stream(temperature=300.0, pressure=101325.0, mass_flow=10.0,
                      composition={"oil": 1.0}, density=850.0)
        out = pump.step(1.0, inlet_stream=s_in)
        assert out["pressure_rise_pa"] == pytest.approx(
            pump.curve.pressure_rise(10.0 / 850.0, 1.0))

    def test_cavitation_when_suction_pressure_low(self):
        pump = self._pump({"npshr_pa": 3.0 * 9.81 * 1000.0})
        s_low = Stream(temperature=300.0, pressure=3.0e4, mass_flow=10.0,
                       composition={"oil": 1.0}, density=850.0)
        out = pump.step(1.0, inlet_stream=s_low)
        assert out["cavitating"] is True
        codes = {d.code for d in out["diagnostics"]}
        assert "PUMP_CAVITATION" in codes
        assert out["mass_flow_kg_s"] < 10.0

    def test_no_cavitation_when_suction_pressure_high(self):
        pump = self._pump({"npshr_pa": 3.0 * 9.81 * 1000.0})
        s_ok = Stream(temperature=300.0, pressure=4e5, mass_flow=10.0,
                      composition={"oil": 1.0}, density=850.0)
        out = pump.step(1.0, inlet_stream=s_ok)
        assert out["cavitating"] is False

    def test_injected_cavitation_is_degredation_not_failure(self):
        pump = self._pump()
        pump.inject_failure("CAVITATION")
        assert pump.state.failed is False
        out = pump.step(1.0)
        assert out["running"] is True
        assert out["cavitating"] is True

    def test_speed_scales_flow(self):
        pump = self._pump()
        pump.apply_action("SET_SPEED", 0.5 * pump.nominal_speed)
        out = pump.step(1.0)
        assert out["volumetric_flow_m3_s"] == pytest.approx(0.05, rel=1e-6)


# ---------------------------------------------------------------------------
# Darcy-Weisbach pressure drop (ТЗ 15-17)
# ---------------------------------------------------------------------------

class TestPressureDrop:
    def test_laminar_friction_factor(self):
        """Laminar f = 64/Re."""
        f = pd.friction_factor(1000.0)
        assert f == pytest.approx(64.0 / 1000.0)

    def test_turbulent_factor_reasonable(self):
        f = pd.friction_factor(1e5, roughness_m=0.000045, diameter_m=0.1)
        assert 0.01 < f < 0.05

    def test_dp_increases_with_flow(self):
        d1 = pd.calculate_pipe_pressure_drop(1.0, 850.0, 0.001, 100.0, 0.1)
        d2 = pd.calculate_pipe_pressure_drop(2.0, 850.0, 0.001, 100.0, 0.1)
        assert d2 > d1
        assert d2 > 2.5 * d1  # superlinear (turbulent f falls slightly with Re)

    def test_minor_losses_add(self):
        d_no = pd.calculate_pipe_pressure_drop(1.0, 850.0, 0.001, 100.0, 0.1)
        d_yes = pd.calculate_pipe_pressure_drop(
            1.0, 850.0, 0.001, 100.0, 0.1, minor_loss_k=2.0)
        assert d_yes > d_no

    def test_static_head_sign(self):
        """Rising pipe costs pressure, falling pipe gains it."""
        rise = pd.static_head_pressure(850.0, 10.0)
        fall = pd.static_head_pressure(850.0, -10.0)
        assert rise > 0.0
        assert fall < 0.0
        assert rise == pytest.approx(-fall)

    def test_valve_resistance_grows_as_valve_closes(self):
        k_open = pd.valve_resistance(850.0, cv=0.01, opening=1.0)
        k_closed = pd.valve_resistance(850.0, cv=0.01, opening=0.1)
        assert k_closed > k_open


# ---------------------------------------------------------------------------
# Water hammer (ТЗ 36)
# ---------------------------------------------------------------------------

class TestWaterHammer:
    def test_joukowsky_formula(self):
        dp = water_hammer_overpressure_pa(2.0, density=850.0, wave_speed_m_s=1000.0)
        assert dp == pytest.approx(850.0 * 1000.0 * 2.0)

    def test_high_risk_when_maop_exceeded(self):
        risk = surge_risk(1.0e5, 3.0, maop_pa=1.0e6)  # surge ~25.5 bar
        assert risk["risk_band"] == "HIGH"
        assert risk["ratio_to_maop"] > 1.0

    def test_low_risk_when_small_change(self):
        risk = surge_risk(1.0e5, 0.1, maop_pa=1.0e6)
        assert risk["risk_band"] == "LOW"

    def test_diagnostic_codes(self):
        high = surge_diagnostic("valve_FV13", 1.0e5, 3.0, 1.0e6)
        assert high.code == "SURGE_HIGH_RISK"
        assert high.severity == "error"
        low = surge_diagnostic("valve_FV13", 1.0e5, 0.1, 1.0e6)
        assert low.code == "SURGE_OK"


# ---------------------------------------------------------------------------
# Network solver: resistance element with static head (ТЗ 15-17)
# ---------------------------------------------------------------------------

class TestNetworkSolverRes:
    def test_pipe_resistance_lowers_downstream_pressure(self):
        from calculation_core.hydraulics.line_hydraulics import solve_branched_network
        nodes = {
            "SRC": {"type": "source"},
            "PIPE": {"type": "res", "k": 500.0, "head": 0.0},
            "SNK": {"type": "sink", "sink_p": 1.01325e5},
        }
        children = {"SRC": ["PIPE"], "PIPE": ["SNK"]}
        res = solve_branched_network(1.2e5, None, nodes, children, "SRC")
        assert res["PIPE"]["flow"] > 0.0
        assert res["PIPE"]["p_out"] < res["PIPE"]["p_in"]

    def test_static_head_raises_outlet_pressure(self):
        from calculation_core.hydraulics.line_hydraulics import solve_branched_network
        nodes = {
            "SRC": {"type": "source"},
            "PIPE": {"type": "res", "k": 100.0, "head": 850.0 * 9.81 * 20.0},
            "SNK": {"type": "sink", "sink_p": 1.2e5},
        }
        children = {"SRC": ["PIPE"], "PIPE": ["SNK"]}
        res = solve_branched_network(1.2e5, None, nodes, children, "SRC")
        assert res["PIPE"]["flow"] > 0.0

    def test_pump_fed_vessel_branch_solves(self):
        """A pump whose branch leads straight to a vessel sink must solve.

        The pump 'head' is a Q -> Pa characteristic (a callable); the branch
        demand code used to treat it as a scalar and crashed with a TypeError
        for topologies like pump -> separator / tank.
        """
        from calculation_core.hydraulics.line_hydraulics import solve_branched_network

        def pump_head(q: float) -> float:
            return max(0.0, 6.0e5 - 1.0e6 * q)

        nodes = {
            "SRC": {"type": "source"},
            "PMP": {"type": "pump", "head": pump_head},
            "VSL": {"type": "sink", "sink_p": 1.7e5},
        }
        children = {"SRC": ["PMP"], "PMP": ["VSL"]}
        res = solve_branched_network(1.01325e5, None, nodes, children, "SRC")
        assert res["PMP"]["flow"] > 0.0
        # The pump discharge sits exactly at the vessel boundary pressure.
        assert res["PMP"]["p_out"] == pytest.approx(1.7e5, rel=1e-6)
        assert res["VSL"]["p_in"] == pytest.approx(1.7e5, rel=1e-6)
        assert res["VSL"]["flow"] == pytest.approx(res["PMP"]["flow"])
