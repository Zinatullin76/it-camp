from lms.content_service import _assess_context
from lms.assessment import practice_criteria, practice_feedback


SCENARIO = {
    "module_id": 7,
    "initial_state": {},
    "target_state": [{"object_id": "col_32", "attribute": "level_m", "relation": ">=", "value": 2.5}],
    "expected_actions": [
        {"seq": 1, "object_id": "val_44", "action_type": "INCREASE_PARAM", "attribute": "position"},
        {"seq": 2, "object_id": "val_46", "action_type": "INCREASE_PARAM", "attribute": "position"},
        {"seq": 3, "object_id": "val_5", "action_type": "DECREASE_PARAM", "attribute": "position"},
    ],
    "success_criteria": [
        {"key": "goal", "title": "", "weight": 3.0},
        {"key": "expected", "title": "", "weight": 1.0},
    ],
}


STALE_TASK = {
    "module_id": 7,
    "scenario_id": "LMS-1",
    "duration_min": 10,
    "initial_state": {},
    "target_state": [],
    "criteria": [
        {"key": "sequence", "title": "Правильная последовательность", "weight": 1.0},
        {"key": "parameters", "title": "Контроль параметров", "weight": 1.0},
        {"key": "time", "title": "Время", "weight": 1.0},
        {"key": "errors", "title": "Ошибочные действия", "weight": 1.0},
        {"key": "safety", "title": "Безопасность", "weight": 1.0},
    ],
    "expected_actions": [],
}


START_SNAPSHOT = {
    "valve_positions": {"val_44": 0.75, "val_46": 0.75, "val_5": 0.75},
    "pump_states": {"pump_H20": True},
    "levels": {"col_32": 0.5},
    "equipment_states": {"h1": {"fuel_flow": 0.2}},
}


def _telemetry(level, v44, v46, v5):
    return {
        "col_32": {"params": {"level_m": level}},
        "val_44": {"params": {"position": v44}},
        "val_46": {"params": {"position": v46}},
        "val_5": {"params": {"position": v5}},
    }


def _actions(*pairs):
    return [
        {"source": "operator_panel", "accepted": 1, "equipment_id": oid,
         "action_type": "SET_VALUE", "old_value": old, "new_value": new}
        for oid, old, new in pairs
    ]


RIGHT = _actions(("val_44", 0.75, 1.0), ("val_46", 0.75, 1.0), ("val_5", 0.75, 0.3))


def _grade(level, v44, v46, v5, actions=RIGHT):
    eval_task, initial_state = _assess_context(STALE_TASK, SCENARIO, START_SNAPSHOT)
    return practice_criteria(eval_task, actions, _telemetry(level, v44, v46, v5),
                             duration_s=60.0, initial_state=initial_state)


def test_assess_context_uses_scenario_definition():
    eval_task, initial_state = _assess_context(STALE_TASK, SCENARIO, START_SNAPSHOT)

    assert [c["key"] for c in eval_task["criteria"]] == ["goal", "expected"]
    assert eval_task["criteria"][0]["title"] == "Выполнение цели"
    assert eval_task["criteria"][1]["title"] == "Соблюдение ожидаемых действий"
    assert len(eval_task["expected_actions"]) == 3
    assert eval_task["target_state"][0]["object_id"] == "col_32"
    assert initial_state["val_44_position"] == 0.75
    assert initial_state["pump_H20_running"] is True
    assert initial_state["col_32_level_m"] == 0.5


def test_all_correct_scores_full():
    result = _grade(level=3.0, v44=100, v46=100, v5=30)
    assert result["score"] == 100.0
    assert result["criteria"]["goal"]["score"] == 100.0
    assert result["criteria"]["expected"]["score"] == 100.0


def test_goal_violated_only_scores_partial():
    result = _grade(level=1.0, v44=100, v46=100, v5=30)
    assert result["criteria"]["goal"]["score"] == 0.0
    assert result["criteria"]["expected"]["score"] == 100.0
    assert result["score"] == 25.0


def test_expected_violated_penalizes():
    result = _grade(level=3.0, v44=30, v46=30, v5=90)
    assert result["criteria"]["goal"]["score"] == 100.0
    assert result["criteria"]["expected"]["score"] == 0.0
    assert result["score"] == 75.0


def test_violated_goal_and_actions_score_zero():
    result = _grade(level=1.0, v44=30, v46=30, v5=90)
    assert result["score"] == 0.0
    assert result["criteria"]["goal"]["score"] == 0.0
    assert result["criteria"]["expected"]["score"] == 0.0
    good, bad = practice_feedback(result)
    assert any("Выполнение цели" in message for message in bad)
    assert any("Соблюдение ожидаемых действий" in message for message in bad)


def test_feedback_explains_zero_score_reasons():
    result = _grade(level=1.0, v44=30, v46=30, v5=90)
    _, bad = practice_feedback(result)
    goal_msg = next((m for m in bad if m.startswith("Цель не достигнута")), None)
    assert goal_msg is not None
    assert "col_32" in goal_msg and "1 м" in goal_msg and "2.5 м" in goal_msg
    exp_msgs = [m for m in bad if m.startswith("Ожидаемое действие не выполнено")]
    assert len(exp_msgs) == 3
    assert any("val_44" in m for m in exp_msgs)
    assert any("val_46" in m for m in exp_msgs)
    assert any("val_5" in m and "уменьшение" in m for m in exp_msgs)


def test_regression_no_80_percent_with_violations():
    # Раньше оценка считалась по устаревшему набору критериев записи задания
    # (sequence/parameters/time/errors/safety) с пустым списком ожидаемых
    # действий: нарушение цели давало ровно 80%.
    result = _grade(level=1.0, v44=30, v46=30, v5=90)
    assert result["score"] == 0.0
    assert result["score"] != 80.0
