"""
command.py
==========
Unified Command domain model for the KTK.

Every operator action — on equipment (pump, valve, heater) or on a control
loop (setpoint, mode) — goes through a Command. The backend Command layer
validates the command against the target before it reaches the simulation
engine; the HMI never mutates process state directly (Principle #5).

Command validation helpers:
  validate_controller_command(cmd, ctrl)  — bounds/mode checks for PID loops
  validate_value(cmd)                     — generic bounds check against lo/hi
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field

from models.controller import Controller, MODE_AUTO, MODE_MANUAL


class CommandAction(str, Enum):
    """All actions an operator may send from the HMI."""

    SET_SP = "SET_SP"                # controller setpoint
    SET_MODE = "SET_MODE"            # controller mode: АВТ / РУЧ
    SET_VALUE = "SET_VALUE"          # valve position / output [0..1 or %]
    TURN_ON = "TURN_ON"              # start pump / open valve
    TURN_OFF = "TURN_OFF"            # stop pump / close valve
    SET_SPEED = "SET_SPEED"          # pump rotation speed
    EMERGENCY_STOP = "EMERGENCY_STOP"
    ACK_ALARM = "ACK_ALARM"          # acknowledge an alarm


class Command(BaseModel):
    """A validated operator command directed at equipment or a control loop."""

    tag: str                                   # equipment id or controller tag
    action: CommandAction
    value: Optional[Union[float, str]] = None
    operator_id: str = "operator"
    timestamp: Optional[float] = None
    source: str = "hmi"


def _as_float(cmd: Command, what: str) -> float:
    """Coerce a command value to float, raising ValueError for non-numeric input."""
    try:
        return float(cmd.value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError(f"{cmd.tag}: {what} требует число, получено '{cmd.value}'")


def validate_controller_command(cmd: Command, ctrl: Controller) -> None:
    """Validate a command directed at a PID loop.

    Raises:
        ValueError when the command is not applicable or out of range.
    """
    if cmd.action == CommandAction.SET_SP:
        value = _as_float(cmd, "SET_SP")
        if not (ctrl.lo <= value <= ctrl.hi):
            raise ValueError(
                f"{cmd.tag}: задание {value} вне диапазона [{ctrl.lo}, {ctrl.hi}]")
    elif cmd.action == CommandAction.SET_MODE:
        if cmd.value not in (MODE_AUTO, MODE_MANUAL):
            raise ValueError(
                f"{cmd.tag}: режим '{cmd.value}' не из {{АВТ, РУЧ}}")
        if ctrl.man and cmd.value == MODE_AUTO:
            raise ValueError(
                f"{cmd.tag}: ручная задвижка — только режим РУЧ")
    elif cmd.action == CommandAction.SET_VALUE:
        value = _as_float(cmd, "SET_VALUE")
        if not (0.0 <= value <= 100.0):
            raise ValueError(
                f"{cmd.tag}: выход {value} вне диапазона [0, 100] %")
    else:
        raise ValueError(
            f"{cmd.tag}: действие {cmd.action} не применимо к регулятору")


def validate_value(cmd: Command, lo: float, hi: float) -> None:
    """Validate a numeric value command against an explicit [lo, hi] range."""
    value = _as_float(cmd, str(cmd.action))
    if not (lo <= value <= hi):
        raise ValueError(
            f"{cmd.tag}: значение {value} вне диапазона [{lo}, {hi}]")
