from events.error_tracker import ErrorTracker, ExpectedAction
from models.base import ActionType, OperatorAction, SimulationState


def expected(equipment: str, action_type: str, deadline: float = 20.0, value=None):
    return ExpectedAction(
        equipment_id=equipment,
        action_type=action_type,
        value=value,
        deadline=deadline,
        description="",
        consequence="Нарушен регламент сценария.",
    )


def action(equipment: str, action_type: ActionType, timestamp: float = 10.0, value=None, old_value=None):
    return OperatorAction(
        timestamp=timestamp,
        operator_id="operator",
        equipment_id=equipment,
        action_type=action_type,
        old_value=old_value,
        new_value=value,
    )


def evaluate(tracker: ErrorTracker, actual: OperatorAction):
    return tracker.evaluate_action(actual, SimulationState(timestamp=actual.timestamp))


def test_wrong_sequence_is_recorded_in_russian():
    tracker = ErrorTracker()
    tracker.register_expected(expected("pump_H20", "TURN_ON"))
    tracker.register_expected(expected("pump_H1", "TURN_OFF"))

    error = evaluate(tracker, action("pump_H1", ActionType.TURN_OFF))

    assert error.error_type == "WRONG_SEQUENCE"
    assert "последовательность" in error.cause.lower()
    assert tracker._expected_queue[1].completed is True


def test_delayed_action_is_completed_and_recorded():
    tracker = ErrorTracker()
    tracker.register_expected(expected("pump_H20", "TURN_ON", deadline=20.0))

    error = evaluate(tracker, action("pump_H20", ActionType.TURN_ON, timestamp=27.5))

    assert error.error_type == "DELAYED_ACTION"
    assert "7.5 с" in error.cause
    assert tracker._expected_queue[0].completed is True


def test_wrong_equipment_is_recorded():
    tracker = ErrorTracker()
    tracker.register_expected(expected("pump_H20", "TURN_ON"))

    error = evaluate(tracker, action("pump_H2", ActionType.TURN_ON))

    assert error.error_type == "WRONG_EQUIPMENT"
    assert "pump_H2" in error.cause
    assert "pump_H20" in error.cause


def test_wrong_action_type_on_correct_equipment_is_recorded():
    tracker = ErrorTracker()
    tracker.register_expected(expected("pump_H20", "TURN_ON"))

    error = evaluate(tracker, action("pump_H20", ActionType.TURN_OFF))

    assert error.error_type == "WRONG_ACTION_TYPE"
    assert "TURN_OFF" in error.cause
    assert "TURN_ON" in error.cause


def test_wrong_parameter_value_is_recorded():
    tracker = ErrorTracker()
    tracker.register_expected(expected("valve_FV1", "SET_VALUE", value=0.6))

    error = evaluate(tracker, action("valve_FV1", ActionType.SET_VALUE, value=0.2))

    assert error.error_type == "WRONG_PARAMETER_VALUE"
    assert "0.2" in error.cause
    assert "0.6" in error.cause


def test_missed_action_is_emitted_only_once_in_russian():
    tracker = ErrorTracker()
    tracker.register_expected(expected("pump_H20", "TURN_ON", deadline=20.0))

    first = tracker.check_missed_actions(21.0)
    second = tracker.check_missed_actions(22.0)

    assert len(first) == 1
    assert first[0].error_type == "MISSED_ACTION"
    assert "не выполнено" in first[0].cause
    assert second == []


def test_correct_action_completes_step_without_error():
    tracker = ErrorTracker()
    tracker.register_expected(expected("pump_H20", "TURN_ON"))

    assert evaluate(tracker, action("pump_H20", ActionType.TURN_ON)) is None
    assert tracker._expected_queue[0].completed is True


def test_increase_param_matches_set_value_with_growing_value():
    tracker = ErrorTracker()
    tracker.register_expected(expected("valve_FV1", "INCREASE_PARAM", value=None))

    error = evaluate(tracker, action("valve_FV1", ActionType.SET_VALUE, value=0.6, old_value=0.3))

    assert error is None
    assert tracker._expected_queue[0].completed is True


def test_increase_param_rejects_decrease():
    tracker = ErrorTracker()
    tracker.register_expected(expected("valve_FV1", "INCREASE_PARAM", value=None))

    error = evaluate(tracker, action("valve_FV1", ActionType.SET_VALUE, value=0.2, old_value=0.6))

    assert error.error_type == "WRONG_PARAMETER_DIRECTION"
    assert "увеличиваться" in error.cause


def test_decrease_param_rejects_increase():
    tracker = ErrorTracker()
    tracker.register_expected(expected("valve_FV1", "DECREASE_PARAM", value=None))

    error = evaluate(tracker, action("valve_FV1", ActionType.SET_VALUE, value=0.8, old_value=0.5))

    assert error.error_type == "WRONG_PARAMETER_DIRECTION"
    assert "уменьшаться" in error.cause


def test_directional_action_rejects_wrong_type():
    tracker = ErrorTracker()
    tracker.register_expected(expected("valve_FV1", "INCREASE_PARAM", value=None))

    error = evaluate(tracker, action("valve_FV1", ActionType.TURN_ON))

    assert error.error_type == "WRONG_ACTION_TYPE"


def test_directional_action_requires_old_value():
    tracker = ErrorTracker()
    tracker.register_expected(expected("valve_FV1", "INCREASE_PARAM", value=None))

    error = evaluate(tracker, action("valve_FV1", ActionType.SET_VALUE, value=0.6))

    assert error.error_type == "WRONG_PARAMETER_DIRECTION"
