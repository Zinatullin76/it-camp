"""Rule-based detection of operator errors against a scenario action plan."""

from dataclasses import dataclass
from typing import List, Optional

from models.base import ErrorEvent, OperatorAction, Severity, SimulationState


@dataclass
class ExpectedAction:
    equipment_id: str
    action_type: str
    value: Optional[float]
    deadline: float
    description: str
    consequence: str
    attribute: str = ""
    value_tolerance: float = 1e-6
    triggered: bool = False
    completed: bool = False


DIRECTIONAL_ACTIONS = ("INCREASE_PARAM", "DECREASE_PARAM")
PARAM_ACTIONS = ("SET_VALUE", "SET_PARAM")


class ErrorTracker:
    """Compare each operator action with the first pending reference step."""

    def __init__(self):
        self._expected_queue: List[ExpectedAction] = []
        self._error_events: List[ErrorEvent] = []
        self._action_log: List[OperatorAction] = []

    def register_expected(self, expected: ExpectedAction) -> None:
        self._expected_queue.append(expected)

    def evaluate_action(
        self,
        action: OperatorAction,
        state: SimulationState,
    ) -> Optional[ErrorEvent]:
        self._action_log.append(action)
        pending = [expected for expected in self._expected_queue if not expected.completed]

        if pending:
            current = pending[0]

            # An exact match with a later step is specifically a sequence error.
            for later in pending[1:]:
                if self._matches(later, action):
                    later.completed = True
                    return self._append_error(
                        "WRONG_SEQUENCE",
                        Severity.HIGH,
                        action,
                        current,
                        f"Нарушена последовательность: сначала требовалось выполнить «{self._expected_text(current)}».",
                    )

            if action.equipment_id != current.equipment_id:
                return self._append_error(
                    "WRONG_EQUIPMENT",
                    Severity.HIGH,
                    action,
                    current,
                    f"Выбрано оборудование «{action.equipment_id}», но требовалось воздействовать на «{current.equipment_id}».",
                )

            if not self._type_matches(current, action):
                return self._append_error(
                    "WRONG_ACTION_TYPE",
                    Severity.HIGH,
                    action,
                    current,
                    f"Для оборудования «{current.equipment_id}» выбрано действие «{self._action_type(action)}» "
                    f"вместо «{self._expected_action_label(current)}».",
                )

            if not self._value_matches(current, action):
                return self._append_error(
                    "WRONG_PARAMETER_VALUE",
                    Severity.HIGH,
                    action,
                    current,
                    f"Для оборудования «{current.equipment_id}» задано значение {self._value_text(action.new_value)} вместо {self._value_text(current.value)}.",
                )

            if not self._direction_ok(current, action):
                return self._append_error(
                    "WRONG_PARAMETER_DIRECTION",
                    Severity.HIGH,
                    action,
                    current,
                    f"Для оборудования «{current.equipment_id}» параметр {self._attr_text(current)} должен "
                    f"{'увеличиваться' if current.action_type == 'INCREASE_PARAM' else 'уменьшаться'}.",
                )

            current.completed = True
            if action.timestamp > current.deadline:
                delay = action.timestamp - current.deadline
                return self._append_error(
                    "DELAYED_ACTION",
                    Severity.HIGH,
                    action,
                    current,
                    f"Обязательное действие выполнено с задержкой {delay:.1f} с после срока {current.deadline:.1f} с.",
                )
            return None

        violation = self._check_regulatory_violation(action, state)
        if violation:
            self._error_events.append(violation)
            return violation
        return None

    @staticmethod
    def _action_type(action: OperatorAction) -> str:
        value = action.action_type
        return str(value.value if hasattr(value, "value") else value)

    def _type_matches(self, expected: ExpectedAction, action: OperatorAction) -> bool:
        at = self._action_type(action)
        if expected.action_type in DIRECTIONAL_ACTIONS:
            return at in PARAM_ACTIONS
        return at == expected.action_type

    def _direction_ok(self, expected: ExpectedAction, action: OperatorAction) -> bool:
        if expected.action_type not in DIRECTIONAL_ACTIONS:
            return True
        if action.old_value is None or action.new_value is None:
            return False
        try:
            old = float(action.old_value)
            new = float(action.new_value)
        except (TypeError, ValueError):
            return False
        if expected.action_type == "INCREASE_PARAM":
            return new > old
        return new < old

    @staticmethod
    def _attr_text(expected: ExpectedAction) -> str:
        if expected.attribute:
            return f"«{expected.attribute}»"
        return "параметр"

    def _expected_action_label(self, expected: ExpectedAction) -> str:
        if expected.action_type == "INCREASE_PARAM":
            return f"увеличить {self._attr_text(expected)}"
        if expected.action_type == "DECREASE_PARAM":
            return f"уменьшить {self._attr_text(expected)}"
        return expected.action_type

    @staticmethod
    def _value_text(value: object) -> str:
        if isinstance(value, float):
            return f"{value:g}"
        return "не задано" if value is None else str(value)

    def _value_matches(self, expected: ExpectedAction, action: OperatorAction) -> bool:
        if expected.value is None:
            return True
        if action.new_value is None:
            return False
        try:
            return abs(float(expected.value) - float(action.new_value)) <= expected.value_tolerance
        except (TypeError, ValueError):
            return str(expected.value) == str(action.new_value)

    def _matches(self, expected: ExpectedAction, action: OperatorAction) -> bool:
        return (
            expected.equipment_id == action.equipment_id
            and self._type_matches(expected, action)
            and self._value_matches(expected, action)
            and self._direction_ok(expected, action)
        )

    def _expected_text(self, expected: ExpectedAction) -> str:
        if expected.action_type in DIRECTIONAL_ACTIONS:
            return f"{self._expected_action_label(expected)} для {expected.equipment_id}"
        text = f"{expected.action_type} для {expected.equipment_id}"
        if expected.attribute:
            text += f" по параметру {self._attr_text(expected)}"
        if expected.value is not None:
            text += f" со значением {self._value_text(expected.value)}"
        return text

    def _append_error(
        self,
        error_type: str,
        severity: Severity,
        action: OperatorAction,
        expected: ExpectedAction,
        cause: str,
    ) -> ErrorEvent:
        actual = f"{self._action_type(action)} для {action.equipment_id}"
        if action.new_value is not None:
            actual += f" со значением {self._value_text(action.new_value)}"
        event = ErrorEvent(
            error_type=error_type,
            severity=severity,
            timestamp=action.timestamp,
            operator_action=actual,
            expected_action=self._expected_text(expected),
            cause=cause,
            consequence=expected.consequence or "Отклонение от установленного алгоритма действий оператора.",
        )
        self._error_events.append(event)
        return event

    def check_missed_actions(self, current_time: float) -> List[ErrorEvent]:
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
                    operator_action="Действие отсутствует",
                    expected_action=f"{self._expected_text(expected)} до {expected.deadline:.1f} с",
                    cause=f"Обязательное действие «{self._expected_text(expected)}» не выполнено до установленного срока.",
                    consequence=expected.consequence or "Обязательный шаг сценария пропущен.",
                )
                self._error_events.append(event)
                new_events.append(event)
        return new_events

    def _check_regulatory_violation(
        self,
        action: OperatorAction,
        state: SimulationState,
    ) -> Optional[ErrorEvent]:
        col_pressure = state.pressure.get("column", 0.0)
        if (
            self._action_type(action) == "SET_VALUE"
            and action.new_value is not None
            and action.new_value > 0.8
            and col_pressure > 200000.0
        ):
            return ErrorEvent(
                error_type="REGULATORY_VIOLATION",
                severity=Severity.HIGH,
                timestamp=action.timestamp,
                operator_action=f"Открытие {action.equipment_id} до {action.new_value:.0%}",
                expected_action="Снизить давление перед открытием клапана",
                cause="Попытка открыть клапан при недопустимо высоком давлении.",
                consequence="Риск скачка давления и повреждения оборудования.",
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
