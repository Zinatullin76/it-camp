"""
test_controller_model.py
========================
Unit tests for the unified Controller (PID) domain model.

Covers:
  1.  Defaults and mode
  2.  Manual mode does not move the output
  3.  Direct-acting loop raises output when PV < SP
  4.  Reverse-acting loop lowers output when PV < SP
  5.  Output clamping [0, 100]
  6.  Integral clamping [-60, +60]
  7.  Manual-only hand valves stay locked in РУЧ
  8.  Cascade setpoint field
  9.  Setpoint clamping to instrument range
  10. Serialization round-trip
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from models.controller import (
    Controller, controller, manual_valve, MODE_AUTO, MODE_MANUAL,
    INTEGRAL_CLAMP, OUTPUT_MAX, OUTPUT_MIN,
)


class TestDefaults:
    def test_factory_defaults(self):
        """Factory mirrors the HMI constructor: PV=SP, АВТ, out=50."""
        c = controller("FRC 404", "Расход сырья", "т/ч", 130, 0, 220, 1.2, 60)
        assert c.tag == "FRC 404"
        assert c.pv == c.sp == 130
        assert c.mode == MODE_AUTO
        assert c.out == 50
        assert c.i == 0.0
        assert c.man is False
        assert c.cascade_sp is None

    def test_manual_valve_defaults(self):
        """Manual-only valve: man=True, locked in РУЧ."""
        v = manual_valve("HV 820", "Нефтяное орошение К-1", "т/ч", 48)
        assert v.man is True
        assert v.mode == MODE_MANUAL
        assert v.out == 48


class TestPIDBehaviour:
    def test_manual_mode_keeps_output(self):
        """РУЧ must return the manual output without moving the integral."""
        c = controller("T1", "t", "°С", 100, 0, 200, 1.0, 60)
        c.set_mode(MODE_MANUAL)
        c.set_manual_output(70)
        out = c.step(pv=10.0, dt=1.0)
        assert out == 70
        assert c.i == 0.0

    def test_direct_raises_output_when_pv_below_sp(self):
        """Direct-acting: PV < SP must open the valve (output rises)."""
        c = controller("T1", "t", "°С", 100, 0, 200, 1.0, 60)
        for _ in range(50):
            c.step(pv=60.0, dt=1.0)
        assert c.out > 50.0
        assert c.pv == 60.0

    def test_reverse_lowers_output_when_pv_below_sp(self):
        """Reverse-acting: PV < SP must close the valve (output falls)."""
        c = controller("T2", "t", "%", 50, 0, 100, 1.0, 60, rev=True)
        for _ in range(50):
            c.step(pv=30.0, dt=1.0)
        assert c.out < 50.0

    def test_output_clamped_to_bounds(self):
        """Output must never leave [0, 100]."""
        c = controller("T3", "t", "°С", 200, 0, 200, 5.0, 1.0)
        for _ in range(500):
            c.step(pv=10.0, dt=1.0)
        assert OUTPUT_MIN <= c.out <= OUTPUT_MAX

    def test_integral_clamped(self):
        """Integral accumulator must stay within [-60, +60]."""
        c = controller("T4", "t", "°С", 200, 0, 200, 0.0, 0.5)
        for _ in range(2000):
            c.step(pv=0.0, dt=1.0)
        assert abs(c.i) <= INTEGRAL_CLAMP

    def test_at_setpoint_output_tends_to_midpoint(self):
        """At PV=SP the direct term is zero; output relaxes to 50."""
        c = controller("T5", "t", "°С", 100, 0, 200, 2.0, 30)
        for _ in range(300):
            c.step(pv=100.0, dt=1.0)
        assert abs(c.out - 50.0) < 1.0


class TestHandValves:
    def test_manual_only_stays_manual(self):
        """set_mode('АВТ') must be rejected for a manual-only valve."""
        v = manual_valve("HV 803", "Перегретый пар в К-1", "т/ч", 56)
        v.set_mode(MODE_AUTO)
        assert v.mode == MODE_MANUAL
        assert v.man is True

    def test_hand_valve_output_settable(self):
        """Manual output must be settable within [0, 100]."""
        v = manual_valve("HV 820", "Нефтяное орошение К-1", "т/ч")
        v.set_manual_output(120)
        assert v.out == OUTPUT_MAX
        v.set_manual_output(-5)
        assert v.out == OUTPUT_MIN


class TestCascadeAndSP:
    def test_cascade_sp_field(self):
        """TRC 2 -> FRC 408 cascade: slave declares its master."""
        master = controller("TRC 2", "T верха К-1", "°С", 128, 60, 190, 3.5, 90, rev=True)
        slave = controller("FRC 408", "Орошение К-1", "т/ч", 34, 0, 90, 1.5, 50,
                           rev=False)
        slave.cascade_sp = master.tag
        assert slave.cascade_sp == "TRC 2"

    def test_set_sp_clamped(self):
        """SP must be clamped to [lo, hi]."""
        c = controller("F1", "f", "т/ч", 50, 0, 100, 1.0, 60)
        c.set_sp(1000)
        assert c.sp == 100
        c.set_sp(-5)
        assert c.sp == 0


class TestSerialization:
    def test_round_trip(self):
        """model_dump -> model_validate must preserve the loop."""
        c = controller("LRCA 603А", "Уровень раздела фаз Е-1", "%", 45, 0, 100,
                       2.2, 110, rev=True)
        c.step(pv=40.0, dt=1.0)
        c2 = Controller.model_validate(c.model_dump())
        assert c2.tag == c.tag
        assert c2.rev is True
        assert c2.out == c.out
        assert c2.i == c.i
