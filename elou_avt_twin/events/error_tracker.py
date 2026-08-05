"""
error_tracker.py
================
Operator error and event tracking system for ELOU-AVT simulator.

Detects and records:
  - Wrong actions
  - Untimely actions
  - Missed actions
  - Wrong sequences
  - Critical actions
  - Regulatory violations

Outputs structured ErrorEvent objects for downstream AI analysis.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from models.base import ErrorEvent, OperatorAction, Severity, SimulationState


@dataclass
class ExpectedAction:
    """
    Defines an expected operator action within a time window.

    Fields:
        equipment_id  : target equipment
        action_type   : expected action type
        value         : expected value (optional)
        deadline      : simulation time by which action must occur [s]
        description   : human-readable description
        consequence   : what happens if missed
    """
    equipment_id: str
    action_type: str
    value: Optional[float]
    deadline: float
    description: str
    consequence: str
    triggered: bool = False
    completed: bool = False


class ErrorTracker:
    """
    Tracks operator actions and compares against expected reference actions.

    Usage:
        tracker.register_expected(expected_action)
        tracker.evaluate_action(operator_action, state)
        events = tracker.check_missed_actions(current_time)
    """

    def __init__(self):
        self._expected_queue: List[ExpectedAction] = []
        self._error_events: List[ErrorEvent] = []
        self._action_log: List[OperatorAction] = []

    def register_expected(self, expected: ExpectedAction) -> None:
        """Register an expected action that the operator should perform."""
        self._expected_queue.append(expected)

    def evaluate_action(
        self,
        action: OperatorAction,
        state: SimulationState,
    ) -> Optional[ErrorEvent]:
        """
        Evaluate an operator action against expected actions and process state.

        Returns ErrorEvent if the action is wrong or out of sequence, else None.
        """
        self._action_log.append(action)

        # Check against expected queue
        for expected in self._expected_queue:
            if expected.completed:
                continue
            if expected.equipment_id == action.equipment_id:
                if expected.action_type == action.action_type:
                    # Correct action — mark completed
                    expected.completed = True
                    return None
                else:
                    # Wrong action type for this equipment
                    event = ErrorEvent(
                        error_type="WRONG_ACTION",
                        severity=Severity.HIGH,
                        timestamp=action.timestamp,
                        operator_action=f"{action.action_type} on {action.equipment_id}",
                        expected_action=f"{expected.action_type} on {expected.equipment_id}",
                        cause="Operator performed incorrect action type",
                        consequence=expected.consequence,
                    )
                    self._error_events.append(event)
                    return event

        # Check for regulatory violations based on state
        violation = self._check_regulatory_violation(action, state)
        if violation:
            self._error_events.append(violation)
            return violation

        return None

    def check_missed_actions(self, current_time: float) -> List[ErrorEvent]:
        """
        Check for actions that were expected but not performed before deadline.

        Returns list of new ErrorEvent objects for missed actions.
        """
        new_events: List[ErrorEvent] = []
        for expected in self._expected_queue:
            if expected.completed or expected.triggered:
                continue
            if current_time > expected.deadline:
                expected.triggered = True
                event = ErrorEvent(
                    error_type="MISSED_ACTION",
                    severity=Severity.CRITICAL,
                    timestamp=current_time,
                    operator_action="(none)",
                    expected_action=f"{expected.action_type} on {expected.equipment_id} by t={expected.deadline:.1f}s",
                    cause="Operator did not perform required action within deadline",
                    consequence=expected.consequence,
                )
                self._error_events.append(event)
                new_events.append(event)
        return new_events

    def _check_regulatory_violation(
        self,
        action: OperatorAction,
        state: SimulationState,
    ) -> Optional[ErrorEvent]:
        """
        Check if an action violates process regulations.
        [MVP]: Basic checks — extend with scenario-specific rules.
        """
        # Example: opening a valve when pressure is critically high
        col_pressure = state.pressure.get("column", 0.0)
        if (action.action_type == "SET_VALUE"
                and action.new_value is not None
                and action.new_value > 0.8
                and col_pressure > 200000.0):
            return ErrorEvent(
                error_type="REGULATORY_VIOLATION",
                severity=Severity.HIGH,
                timestamp=action.timestamp,
                operator_action=f"Opening {action.equipment_id} to {action.new_value:.0%}",
                expected_action="Reduce pressure before opening valve",
                cause="Attempting to open valve under high pressure",
                consequence="Risk of pressure surge and equipment damage",
            )
        return None

    def get_events(self) -> List[ErrorEvent]:
        return list(self._error_events)

    def get_action_log(self) -> List[OperatorAction]:
        return list(self._action_log)

    def reset(self) -> None:
        self._expected_queue.clear()
        self._error_events.clear()
        self._action_log.clear()
