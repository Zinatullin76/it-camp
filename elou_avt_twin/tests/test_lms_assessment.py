from lms.assessment import practice_criteria, practice_feedback


def _task():
    return {
        "duration_min": 10,
        "expected_actions": [
            {"seq": 1, "object_id": "pump_H20", "action_type": "TURN_ON"},
            {"seq": 2, "object_id": "pump_H1", "action_type": "TURN_OFF"},
        ],
        "target_state": [],
        "restrictions": [],
    }


def test_missing_all_required_actions_cannot_pass():
    result = practice_criteria(_task(), [], {}, duration_s=10.0)

    assert result["criteria"]["sequence"]["score"] == 0.0
    assert result["score"] == 0.0
    assert result["completed_expected"] == 0
    good, bad = practice_feedback(result)
    assert any("0 из 2" in message for message in bad)
    assert not any("без нарушений" in message for message in good)


def test_partial_required_actions_cap_total_score():
    actions = [{
        "source": "operator_panel",
        "accepted": 1,
        "equipment_id": "pump_H20",
        "action_type": "TURN_ON",
    }]

    result = practice_criteria(_task(), actions, {}, duration_s=10.0)

    assert result["criteria"]["sequence"]["score"] == 50.0
    assert result["score"] <= 50.0


def test_every_tracked_error_reduces_score_and_is_explained():
    actions = [
        {"source": "operator_panel", "accepted": 1, "equipment_id": "pump_H20", "action_type": "TURN_ON"},
        {"source": "operator_panel", "accepted": 1, "equipment_id": "pump_H1", "action_type": "TURN_OFF"},
    ]
    errors = [
        {"rule_error_type": "WRONG_SEQUENCE", "severity": "HIGH", "cause": "Нарушена последовательность."},
        {"rule_error_type": "MISSED_ACTION", "severity": "CRITICAL", "cause": "Пропущено обязательное действие."},
    ]

    result = practice_criteria(_task(), actions, {}, duration_s=10.0, tracked_errors=errors)
    _, bad = practice_feedback(result)

    assert result["error_count"] == 2
    assert result["error_penalty"] == 45.0
    assert result["criteria"]["errors"]["score"] == 55.0
    assert result["criteria"]["safety"]["score"] == 50.0
    assert result["score"] < 100.0
    assert any("Нарушена последовательность" in message for message in bad)
    assert any("штраф" in message for message in bad)
