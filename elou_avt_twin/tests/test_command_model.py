"""
test_command_model.py
=====================
Unit tests for the unified Command domain model and its validation.

Covers:
  1.  Command construction
  2.  Controller SET_SP bounds validation
  3.  Controller SET_MODE validation (incl. manual-only hand valves)
  4.  SET_VALUE range validation
  5.  Unsupported action rejection for controllers
  6.  Serialization round-trip
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from models.command import (
    Command, CommandAction, validate_controller_command, validate_value,
)
from models.controller import controller, manual_valve, MODE_AUTO, MODE_MANUAL


def test_command_basic():
    """A command carries tag, action, value and operator id."""
    cmd = Command(tag="FRC 408", action=CommandAction.SET_SP, value=40.0,
                  operator_id="op1", source="hmi")
    assert cmd.tag == "FRC 408"
    assert cmd.action == CommandAction.SET_SP
    assert cmd.value == 40.0
    assert cmd.operator_id == "op1"


class TestControllerCommands:
    def test_valid_set_sp_passes(self):
        """In-range SET_SP must pass validation."""
        c = controller("FRC 408", "Орошение К-1", "т/ч", 34, 0, 90, 1.5, 50)
        cmd = Command(tag="FRC 408", action=CommandAction.SET_SP, value=45.0)
        validate_controller_command(cmd, c)  # must not raise

    def test_set_sp_out_of_range_raises(self):
        """Out-of-range SET_SP must raise ValueError."""
        c = controller("FRC 408", "Орошение К-1", "т/ч", 34, 0, 90, 1.5, 50)
        cmd = Command(tag="FRC 408", action=CommandAction.SET_SP, value=200.0)
        with pytest.raises(ValueError):
            validate_controller_command(cmd, c)

    def test_set_sp_without_value_raises(self):
        """SET_SP without a value must raise ValueError."""
        c = controller("FRC 408", "Орошение К-1", "т/ч", 34, 0, 90, 1.5, 50)
        cmd = Command(tag="FRC 408", action=CommandAction.SET_SP)
        with pytest.raises(ValueError):
            validate_controller_command(cmd, c)

    def test_valid_set_mode_passes(self):
        """Switching to РУЧ must pass for an automatic loop."""
        c = controller("TRC 2", "T верха К-1", "°С", 128, 60, 190, 3.5, 90)
        cmd = Command(tag="TRC 2", action=CommandAction.SET_MODE, value=MODE_MANUAL)
        validate_controller_command(cmd, c)  # must not raise

    def test_unknown_mode_raises(self):
        """Unknown mode must raise ValueError."""
        c = controller("TRC 2", "T верха К-1", "°С", 128, 60, 190, 3.5, 90)
        cmd = Command(tag="TRC 2", action=CommandAction.SET_MODE, value="OFF")
        with pytest.raises(ValueError):
            validate_controller_command(cmd, c)

    def test_manual_valve_rejects_auto(self):
        """Hand valves must reject switching to АВТ."""
        v = manual_valve("HV 820", "Нефтяное орошение К-1", "т/ч", 48)
        cmd = Command(tag="HV 820", action=CommandAction.SET_MODE, value=MODE_AUTO)
        with pytest.raises(ValueError):
            validate_controller_command(cmd, v)

    def test_set_value_range_raises(self):
        """SET_VALUE outside [0, 100] % must raise ValueError."""
        c = controller("FRC 408", "Орошение К-1", "т/ч", 34, 0, 90, 1.5, 50)
        cmd = Command(tag="FRC 408", action=CommandAction.SET_VALUE, value=150.0)
        with pytest.raises(ValueError):
            validate_controller_command(cmd, c)

    def test_turn_on_rejected_for_controller(self):
        """TURN_ON is not applicable to a controller."""
        c = controller("FRC 408", "Орошение К-1", "т/ч", 34, 0, 90, 1.5, 50)
        cmd = Command(tag="FRC 408", action=CommandAction.TURN_ON)
        with pytest.raises(ValueError):
            validate_controller_command(cmd, c)


class TestGenericValidation:
    def test_validate_value_in_range(self):
        """Generic bounds check passes for an in-range value."""
        cmd = Command(tag="valve_FV1", action=CommandAction.SET_VALUE, value=0.6)
        validate_value(cmd, 0.0, 1.0)  # must not raise

    def test_validate_value_out_of_range(self):
        """Generic bounds check raises out-of-range ValueError."""
        cmd = Command(tag="valve_FV1", action=CommandAction.SET_VALUE, value=1.5)
        with pytest.raises(ValueError):
            validate_value(cmd, 0.0, 1.0)


class TestSerialization:
    def test_round_trip(self):
        """Command must survive model_dump -> model_validate."""
        cmd = Command(tag="TRC 9", action=CommandAction.SET_SP, value=352.0,
                      operator_id="op2", timestamp=12.5)
        cmd2 = Command.model_validate(cmd.model_dump())
        assert cmd2.action == CommandAction.SET_SP
        assert cmd2.timestamp == 12.5
