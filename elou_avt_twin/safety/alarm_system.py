"""
alarm_system.py
===============
Alarm and safety interlock system for ELOU-AVT simulator.

Implements:
  - Warning alarms (LOW, HIGH)
  - High-high / Low-low alarms (CRITICAL)
  - Automatic protective actions (ESD triggers)

All setpoints are DEMO/MVP values — replace with real process data.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from models.base import Alarm, Severity
import time


@dataclass
class AlarmSetpoint:
    """
    Alarm setpoint definition.

    Fields:
        parameter   : process variable name
        low_low     : LL setpoint — critical low
        low         : L  setpoint — warning low
        high        : H  setpoint — warning high
        high_high   : HH setpoint — critical high
        unit        : engineering unit string
        auto_action : optional callback for automatic protective action
    """
    parameter: str
    low_low: Optional[float] = None
    low: Optional[float] = None
    high: Optional[float] = None
    high_high: Optional[float] = None
    unit: str = ""
    auto_action: Optional[Callable] = None


# ---------------------------------------------------------------------------
# Default ELOU-AVT alarm setpoints [MVP Rigorous values]
# ---------------------------------------------------------------------------
DEFAULT_SETPOINTS: Dict[str, AlarmSetpoint] = {
    "feed_flow": AlarmSetpoint(
        parameter="feed_flow",
        low_low=10.0, low=50.0, high=150.0, high_high=200.0,
        unit="kg/s",
    ),
    "column_pressure": AlarmSetpoint(
        parameter="column_pressure",
        low_low=50000.0, low=80000.0, high=150000.0, high_high=200000.0,
        unit="Pa",
    ),
    "column_temperature": AlarmSetpoint(
        parameter="column_temperature",
        low_low=300.0, low=350.0, high=650.0, high_high=700.0,
        unit="K",
    ),
    "furnace_temperature": AlarmSetpoint(
        parameter="furnace_temperature",
        high=700.0, high_high=750.0,
        unit="K",
    ),
}


class AlarmSystem:
    """
    Process alarm and safety interlock system.

    Evaluates process values against setpoints and generates Alarm objects.
    Triggers automatic protective actions for critical alarms.
    """

    def __init__(self, setpoints: Optional[Dict[str, AlarmSetpoint]] = None):
        self._setpoints: Dict[str, AlarmSetpoint] = dict(setpoints or DEFAULT_SETPOINTS)
        self._active_alarms: Dict[str, Alarm] = {}
        self._alarm_history: List[Alarm] = []
        self._alarm_counter = 0

    def configure(self, setpoints: Dict[str, AlarmSetpoint]) -> None:
        """Replace the alarm setpoint table (used for scheme-specific limits)."""
        self._setpoints = dict(setpoints)
        self._active_alarms.clear()

    def evaluate(self, timestamp: float, values: Dict[str, float]) -> List[Alarm]:
        """
        Evaluate all process values against setpoints.

        Parameters:
            timestamp : simulation time [s]
            values    : dict of {parameter_name: current_value}

        Returns:
            list of newly triggered Alarm objects
        """
        new_alarms: List[Alarm] = []

        for param, value in values.items():
            sp = self._setpoints.get(param)
            if sp is None:
                continue

            severity, description = self._check_setpoint(sp, value)
            if severity is None:
                # Clear alarm if it was active
                self._active_alarms.pop(param, None)
                continue

            alarm_id = f"ALM-{param.upper()}-{self._alarm_counter:04d}"
            alarm = Alarm(
                id=alarm_id,
                timestamp=timestamp,
                parameter=param,
                actual_value=value,
                threshold=self._get_threshold(sp, severity),
                severity=severity,
                description=description,
            )

            # Only add if not already active for this parameter at same severity
            existing = self._active_alarms.get(param)
            if existing is None or existing.severity != severity:
                self._alarm_counter += 1
                self._active_alarms[param] = alarm
                self._alarm_history.append(alarm)
                new_alarms.append(alarm)

                # Trigger automatic action if defined
                if sp.auto_action is not None and severity == Severity.CRITICAL:
                    sp.auto_action()

        return new_alarms

    def _check_setpoint(self, sp: AlarmSetpoint, value: float):
        """Return (Severity, description) or (None, None) if within limits."""
        if sp.high_high is not None and value >= sp.high_high:
            return Severity.CRITICAL, f"{sp.parameter} HIGH-HIGH: {value:.3f} >= {sp.high_high:.3f} {sp.unit}"
        if sp.low_low is not None and value <= sp.low_low:
            return Severity.CRITICAL, f"{sp.parameter} LOW-LOW: {value:.3f} <= {sp.low_low:.3f} {sp.unit}"
        if sp.high is not None and value >= sp.high:
            return Severity.HIGH, f"{sp.parameter} HIGH: {value:.3f} >= {sp.high:.3f} {sp.unit}"
        if sp.low is not None and value <= sp.low:
            return Severity.HIGH, f"{sp.parameter} LOW: {value:.3f} <= {sp.low:.3f} {sp.unit}"
        return None, None

    def _get_threshold(self, sp: AlarmSetpoint, severity: Severity) -> float:
        if severity == Severity.CRITICAL:
            return sp.high_high or sp.low_low or 0.0
        return sp.high or sp.low or 0.0

    def get_active_alarms(self) -> List[Alarm]:
        return list(self._active_alarms.values())

    def get_alarm_history(self) -> List[Alarm]:
        return list(self._alarm_history)

    def acknowledge_alarm(self, parameter: str) -> None:
        self._active_alarms.pop(parameter, None)

    def register_custom_alarm(self, timestamp: float, parameter: str,
                              actual_value: float = 1.0, threshold: float = 0.0,
                              severity: str = "HIGH", description: str = "") -> None:
        """Raise an alarm directly (scenario-driven event, «Обуч.txt» §16)."""
        from models.base import Severity
        try:
            sev = Severity(severity.upper())
        except ValueError:
            sev = Severity.HIGH
        self._alarm_counter += 1
        alarm = Alarm(
            id=f"ALM-SCENARIO-{parameter.upper()}-{self._alarm_counter:04d}",
            timestamp=timestamp,
            parameter=parameter,
            actual_value=actual_value,
            threshold=threshold,
            severity=sev,
            description=description,
        )
        self._active_alarms[parameter] = alarm
        self._alarm_history.append(alarm)

    def reset(self) -> None:
        self._active_alarms.clear()
        self._alarm_history.clear()
        self._alarm_counter = 0
