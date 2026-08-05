import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from controls.control_system import ControlSystem
from models.command import Command, CommandAction
from models.controller import MODE_AUTO, MODE_MANUAL


def make_cmd(tag, action, value=None):
    return Command(tag=tag, action=action, value=value)


def test_set_sp_in_range_and_out_of_range_rejected():
    """Command layer is strict: out-of-range SET_SP is rejected (no silent clamp)."""
    cs = ControlSystem()
    cs.apply_command(make_cmd("TRC 2", CommandAction.SET_SP, 130))
    assert cs.controllers["TRC 2"].sp == 130.0
    with pytest.raises(ValueError):
        cs.apply_command(make_cmd("TRC 2", CommandAction.SET_SP, 999))
    with pytest.raises(ValueError):
        cs.apply_command(make_cmd("TRC 2", CommandAction.SET_SP, 10))


def test_mode_switch_and_manual_output():
    cs = ControlSystem()
    cs.apply_command(make_cmd("TRC 2", CommandAction.SET_MODE, MODE_MANUAL))
    assert cs.controllers["TRC 2"].mode == MODE_MANUAL
    cs.apply_command(make_cmd("TRC 2", CommandAction.SET_VALUE, 70))
    assert cs.controllers["TRC 2"].out == 70.0
    cs.apply_command(make_cmd("TRC 2", CommandAction.SET_MODE, MODE_AUTO))
    assert cs.controllers["TRC 2"].mode == MODE_AUTO


def test_unknown_mode_raises():
    cs = ControlSystem()
    with pytest.raises(ValueError):
        cs.apply_command(make_cmd("TRC 2", CommandAction.SET_MODE, "OFF"))


def test_unknown_tag_raises():
    cs = ControlSystem()
    with pytest.raises(ValueError):
        cs.apply_command(make_cmd("NOPE", CommandAction.SET_SP, 100))


def test_hand_valve_rejects_auto():
    cs = ControlSystem()
    with pytest.raises(ValueError):
        cs.apply_command(make_cmd("HV 820", CommandAction.SET_MODE, MODE_AUTO))
    cs.apply_command(make_cmd("HV 820", CommandAction.SET_VALUE, 30))
    assert cs.controllers["HV 820"].out == 30.0


def test_action_not_applicable_to_controller():
    cs = ControlSystem()
    with pytest.raises(ValueError):
        cs.apply_command(make_cmd("TRC 2", CommandAction.TURN_ON))


def test_span_cascade():
    """FRC 406 sp = 60 + LRCA 605.out/100 * 140 (HMI line 267)."""
    cs = ControlSystem()
    cs.apply_command(make_cmd("LRCA 605", CommandAction.SET_MODE, MODE_MANUAL))
    cs.apply_command(make_cmd("LRCA 605", CommandAction.SET_VALUE, 100))
    cs.step_all(dt=1.0)
    assert cs.controllers["FRC 406"].sp == pytest.approx(200.0)


def test_scale_cascade():
    """FRC 408 sp = TRC 2.out/100 * 80 (HMI line 340)."""
    cs = ControlSystem()
    cs.apply_command(make_cmd("TRC 2", CommandAction.SET_MODE, MODE_MANUAL))
    cs.apply_command(make_cmd("TRC 2", CommandAction.SET_VALUE, 50))
    cs.step_all(dt=1.0)
    assert cs.controllers["FRC 408"].sp == pytest.approx(40.0)


def test_pv_cascade_clamps():
    """FRC 453 sp = clamp(0,180, 96 + (L632-50)*3.2) (HMI line 411)."""
    cs = ControlSystem()
    cs.step_all(dt=1.0, extra={"L632": 50.0})
    assert cs.controllers["FRC 453"].sp == pytest.approx(96.0)
    cs.step_all(dt=1.0, extra={"L632": 100.0})
    assert cs.controllers["FRC 453"].sp == pytest.approx(180.0)


def test_master_pv_cascade():
    """TRC 3 sp = clamp(280,340, 328 + (TRC 4.sp - T_K1bot)*1.2) (line 303)."""
    cs = ControlSystem()
    cs.step_all(dt=1.0, extra={"T_K1bot": 200.0})
    assert cs.controllers["TRC 3"].sp == pytest.approx(340.0)
    cs.step_all(dt=1.0, extra={"T_K1bot": 250.0})
    assert cs.controllers["TRC 3"].sp == pytest.approx(328.0 + (236 - 250) * 1.2)


def test_pv_minus_cascade():
    """TRC 28 sp = clamp(..,190, 171 + (162 - T_K9bot)) (line 404)."""
    cs = ControlSystem()
    cs.step_all(dt=1.0, extra={"T_K9bot": 162.0})
    assert cs.controllers["TRC 28"].sp == pytest.approx(171.0)
    cs.step_all(dt=1.0, extra={"T_K9bot": 180.0})
    assert cs.controllers["TRC 28"].sp == pytest.approx(153.0)


def test_cascade_skipped_when_slave_manual():
    cs = ControlSystem()
    cs.apply_command(make_cmd("FRC 408", CommandAction.SET_MODE, MODE_MANUAL))
    cs.apply_command(make_cmd("TRC 2", CommandAction.SET_MODE, MODE_MANUAL))
    cs.apply_command(make_cmd("TRC 2", CommandAction.SET_VALUE, 100))
    before = cs.controllers["FRC 408"].sp
    cs.step_all(dt=1.0)
    assert cs.controllers["FRC 408"].sp == before


def test_tracked_loop_tracks_setpoint():
    """FRCA 411 self-tracks: pv += (sp - pv) * 0.05 (HMI line 306)."""
    cs = ControlSystem()
    assert cs.controllers["FRCA 411"].pv == 62.0  # initial pv = sp0
    cs.apply_command(make_cmd("FRCA 411", CommandAction.SET_SP, 80))
    cs.step_all(dt=1.0)
    pv = cs.controllers["FRCA 411"].pv
    assert pv == pytest.approx(62.0 + (80.0 - 62.0) * 0.05)


def test_step_pid_drives_output_on_error():
    cs = ControlSystem()
    cs.step_all(dt=1.0, pv_map={"TRC 2": 150.0})
    out = cs.controllers["TRC 2"].out
    assert out > 50.0  # pv above sp, reverse-acting -> output rises


def test_snapshot_shape():
    cs = ControlSystem()
    snap = cs.snapshot()
    assert len(snap) == 55
    fp = snap["TRC 2"]
    for key in ("tag", "sp", "pv", "lo", "hi", "kp", "ti", "rev",
                "mode", "out", "i", "man", "cascade", "tracked"):
        assert key in fp, key
    assert fp["cascade"] is None and fp["tracked"] is False


def test_reset_restores_defaults():
    cs = ControlSystem()
    cs.apply_command(make_cmd("TRC 2", CommandAction.SET_SP, 190))
    cs.apply_command(make_cmd("TRC 2", CommandAction.SET_MODE, MODE_MANUAL))
    cs.reset()
    assert cs.controllers["TRC 2"].sp == 128.0
    assert cs.controllers["TRC 2"].mode == MODE_AUTO


def test_catalog_is_copied_not_shared():
    a, b = ControlSystem(), ControlSystem()
    a.apply_command(make_cmd("TRC 2", CommandAction.SET_SP, 190))
    assert b.controllers["TRC 2"].sp == 128.0
