"""
lms/assessment.py
=================
Automatic assessment of tests and practical tasks («Обуч.txt» §13, §24).

Test scoring:
    * single  — exactly one correct option
    * multi   — proportion of the correct set, minus penalty per wrong pick
    * match   — proportion of correctly matched pairs
    * sequence— proportion of correctly ordered items
    * object  — match with the expected scheme node

Practice scoring compares the actual operator actions (event log) and the
final process state against the task criteria:

    sequence   Правильная последовательность
    goal       Выполнение цели (target state reached)
    expected   Соблюдение ожидаемых действий (final state matches directions)
    time       Время выполнения
    errors     Ошибочные действия
    safety     Безопасность (критические ошибки)

The weighted average of criteria gives the final X/100.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

DEFAULT_CRITERIA = [
    {"key": "sequence", "title": "Правильная последовательность", "weight": 1.0},
    {"key": "goal", "title": "Выполнение цели", "weight": 1.5},
    {"key": "expected", "title": "Соблюдение ожидаемых действий", "weight": 1.0},
    {"key": "time", "title": "Время", "weight": 0.8},
    {"key": "errors", "title": "Ошибочные действия", "weight": 1.0},
    {"key": "safety", "title": "Безопасность", "weight": 1.5},
]

_ATTR_LABELS = {
    "running": "Состояние",
    "position": "Положение",
    "fuel_flow": "Расход топлива",
    "failed": "Состояние отказа",
    "flow_kg_s": "Расход",
    "temperature_c": "Температура",
    "pressure_bar": "Давление",
    "level_m": "Уровень",
    "new_value": "Параметр",
}

_ATTR_UNITS = {
    "position": "%",
    "fuel_flow": " кг/с",
    "flow_kg_s": " кг/с",
    "temperature_c": " °C",
    "pressure_bar": " бар",
    "level_m": " м",
    "new_value": "",
}

_DIRECTION_LABEL = {"INCREASE_PARAM": "увеличение", "DECREASE_PARAM": "уменьшение"}

_RELATION_LABELS = {
    "==": "равно", "=": "равно", "eq": "равно",
    "!=": "не равно", "ne": "не равно",
    ">": "больше", "gt": "больше",
    "<": "меньше", "lt": "меньше",
    ">=": "не менее", "ge": "не менее",
    "<=": "не более", "le": "не более",
}

_ACTION_LABELS = {
    "TURN_ON": "включить",
    "TURN_OFF": "выключить",
    "OPEN_VALVE": "открыть",
    "CLOSE_VALVE": "закрыть",
    "INCREASE_PARAM": "увеличить параметр",
    "DECREASE_PARAM": "уменьшить параметр",
    "SET_PARAM": "задать параметр",
}

ERROR_PENALTY_POINTS = {
    "LOW": 5.0,
    "INFO": 5.0,
    "MEDIUM": 10.0,
    "WARNING": 10.0,
    "HIGH": 15.0,
    "CRITICAL": 30.0,
}
REJECTED_ACTION_PENALTY = 10.0


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _error_penalty(severity: Any) -> float:
    return ERROR_PENALTY_POINTS.get(str(severity or "MEDIUM").upper(), 10.0)


def _as_set(v: Any) -> set:
    if v is None:
        return set()
    if isinstance(v, (set, frozenset)):
        return set(v)
    if isinstance(v, (list, tuple)):
        return {str(x) for x in v}
    return {str(v)}


def _normalize_order(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)]


# ---------------------------------------------------------------------------
# Test assessment
# ---------------------------------------------------------------------------


def score_question(q: Dict[str, Any], user_answer: Any) -> Dict[str, Any]:
    """Score one question. Returns earned / max / correct / percent."""
    kind = q.get("kind", "single")
    max_score = max(0.0, _num(q.get("max_score"), 1.0))
    penalty = max(0.0, _num(q.get("penalty"), 0.0))
    answer = q.get("answer")

    earned = 0.0
    correct = True
    percent = 0.0

    if kind == "single":
        correct_set = _as_set(answer)
        chosen = _as_set(user_answer)
        if chosen and chosen == correct_set:
            earned = max_score
            percent = 1.0
        else:
            correct = False

    elif kind == "multi":
        correct_set = _as_set(answer)
        chosen = _as_set(user_answer)
        if correct_set:
            hit = len(chosen & correct_set)
            earned = max_score * (hit / len(correct_set))
            wrong_picks = len(chosen - correct_set)
            earned = max(0.0, earned - penalty * wrong_picks)
            correct = chosen == correct_set
        percent = earned / max_score if max_score else 0.0

    elif kind == "match":
        pairs = answer if isinstance(answer, list) else []
        user = user_answer if isinstance(user_answer, dict) else {}
        matched = sum(1 for p in pairs if _pair_matches(p, user))
        earned = max_score * (matched / len(pairs)) if pairs else 0.0
        correct = matched == len(pairs) if pairs else False
        percent = earned / max_score if max_score else 0.0

    elif kind == "sequence":
        expected = _normalize_order(answer)
        got = _normalize_order(user_answer)
        if expected:
            hit = sum(1 for i in range(min(len(expected), len(got)))
                      if expected[i] == got[i])
            earned = max_score * (hit / len(expected))
            correct = hit == len(expected) and len(got) == len(expected)
        percent = earned / max_score if max_score else 0.0

    elif kind == "object":
        chosen = _normalize_order(user_answer)
        expected = _normalize_order(answer)
        if chosen and expected and chosen[0] == expected[0]:
            earned = max_score
            percent = 1.0
        else:
            correct = False

    if not correct:
        earned = max(0.0, earned - penalty)
        percent = earned / max_score if max_score else 0.0

    return {
        "question_id": q.get("id"),
        "kind": kind,
        "earned": round(earned, 2),
        "max": max_score,
        "correct": correct,
        "percent": round(percent, 3),
    }


def _pair_matches(pair: Any, user_map: Dict[str, Any]) -> bool:
    if isinstance(pair, dict):
        left, right = pair.get("left"), pair.get("right")
    elif isinstance(pair, (list, tuple)) and len(pair) >= 2:
        left, right = pair[0], pair[1]
    else:
        return False
    return str(user_map.get(str(left), "")).strip() == str(right).strip()


def assess_test(test: Dict[str, Any], answers: Dict[str, Any],
                duration_s: float = 0.0) -> Dict[str, Any]:
    """Assess a full test submission."""
    questions: List[Dict[str, Any]] = test.get("questions", [])
    detail = []
    total_earned = 0.0
    total_max = 0.0
    unanswered_required = 0
    for q in questions:
        qid = str(q.get("id"))
        user = answers.get(qid)
        if user is None or (isinstance(user, (list, dict)) and not user and q.get("kind") not in ("match",)):
            if user is None:
                if q.get("required"):
                    unanswered_required += 1
                user = None
        res = score_question(q, user)
        detail.append({**res, "title": q.get("title", ""), "text": q.get("text", ""),
                       "required": bool(q.get("required"))})
        total_earned += res["earned"]
        total_max += res["max"]

    percent = (total_earned / total_max * 100.0) if total_max else 0.0
    passing_score = _num(test.get("passing_score"), 70.0)
    passed = percent >= passing_score and unanswered_required == 0

    feedback_good = []
    feedback_bad = []
    for r in detail:
        if r["correct"] and r["max"] > 0:
            feedback_good.append(f"Вопрос «{r['title']}» — верно ({r['earned']:.0f}/{r['max']:.0f} б.)")
        elif r["max"] > 0:
            feedback_bad.append(f"Вопрос «{r['title']}» — ошибка, получено {r['earned']:.0f} из {r['max']:.0f} б.")
    if unanswered_required:
        feedback_bad.append(f"Оставлены без ответа обязательные вопросы: {unanswered_required}")

    return {
        "score": round(percent, 1),
        "max_score": 100.0,
        "passed": bool(passed),
        "total_earned": round(total_earned, 2),
        "total_max": total_max,
        "passing_score": passing_score,
        "unanswered_required": unanswered_required,
        "questions": detail,
        "feedback_good": feedback_good,
        "feedback_bad": feedback_bad,
        "duration_s": duration_s,
    }


# ---------------------------------------------------------------------------
# Practice assessment
# ---------------------------------------------------------------------------


def evaluate_condition(cond: Dict[str, Any], telemetry: Dict[str, Any]) -> bool:
    """Evaluate one target-state / restriction condition against telemetry."""
    object_id = cond.get("object_id", "")
    attribute = cond.get("attribute", "")
    relation = cond.get("relation", "==")
    value = cond.get("value")
    value2 = cond.get("value2")

    node = telemetry.get(object_id) or telemetry.get("_global", {})
    if object_id == "_global":
        node = telemetry.get("_global", {})

    actual: Any = None
    if attribute == "running":
        actual = node.get("running")
    elif attribute == "failed":
        actual = node.get("failed")
    elif attribute == "failure_mode":
        actual = node.get("failure_mode")
    else:
        params = node.get("params", {}) if isinstance(node, dict) else {}
        if attribute in params:
            actual = params.get(attribute)
        elif attribute in node:
            actual = node.get(attribute)

    if actual is None:
        return False

    if relation == "between":
        try:
            return _num(value) <= float(actual) <= _num(value2)
        except (TypeError, ValueError):
            return False
    if relation in ("==", "=", "eq"):
        if isinstance(actual, bool):
            return actual == bool(value)
        if isinstance(actual, (int, float)):
            return abs(float(actual) - _num(value)) < 1e-6
        return str(actual) == str(value)
    if relation in ("!=", "ne"):
        return not evaluate_condition({**cond, "relation": "=="}, telemetry)
    if relation in (">", "gt"):
        return float(actual) > _num(value)
    if relation in ("<", "lt"):
        return float(actual) < _num(value)
    if relation in (">=", "ge"):
        return float(actual) >= _num(value)
    if relation in ("<=", "le"):
        return float(actual) <= _num(value)
    return False


def _target_verdict(target: List[Dict[str, Any]], telemetry: Dict[str, Any]) -> tuple[float, List[Dict[str, Any]]]:
    """Target-state score plus the list of unmet conditions (with actuals)."""
    if not target:
        return 1.0, []
    satisfied = 0
    details: List[Dict[str, Any]] = []
    for c in target:
        if evaluate_condition(c, telemetry):
            satisfied += 1
        else:
            actual = _lookup_state_value(telemetry, c.get("object_id", ""), c.get("attribute", ""))
            details.append({**c, "actual": actual})
    return satisfied / len(target), details


def target_state_score(target: List[Dict[str, Any]], telemetry: Dict[str, Any]) -> float:
    score, _ = _target_verdict(target, telemetry)
    return score


def target_state_details(target: List[Dict[str, Any]], telemetry: Dict[str, Any]) -> List[Dict[str, Any]]:
    _, details = _target_verdict(target, telemetry)
    return details


def _lookup_state_value(source: Dict[str, Any], object_id: str, attribute: str) -> Any:
    """Resolve a parameter value from a flat dict (``<object_id>_<attribute>``)
    or from a node dict (``source[object_id].params[attribute]``)."""
    if not source or not object_id:
        return None
    if not attribute:
        attribute = "value"
    flat_key = f"{object_id}_{attribute}"
    if flat_key in source:
        return source[flat_key]
    node = source.get(object_id)
    if isinstance(node, dict):
        if attribute in node:
            return node[attribute]
        params = node.get("params")
        if isinstance(params, dict) and attribute in params:
            return params[attribute]
    for alias in ("running", "position", "fuel_flow", "level_m", "flow_kg_s", "pressure_bar"):
        key = f"{object_id}_{alias}"
        if key in source:
            return source[key]
    return None


def _expected_verdict(expected: List[Dict[str, Any]], telemetry: Dict[str, Any],
                      initial_state: Optional[Dict[str, Any]] = None) -> tuple[float, List[Dict[str, Any]]]:
    """Directional expected-actions score plus the list of unmet directions.

    ``INCREASE_PARAM`` / ``DECREASE_PARAM`` encode the required direction of a
    controlled parameter (e.g. the valve opening must grow). The final value
    is compared against the initial one: if it moved the required way the
    action counts as satisfied, otherwise the operator gets a penalty.
    Actions without a direction, an object or a known initial/final value are
    skipped and do not affect the score. With no verifiable actions the
    criterion is considered fully satisfied.
    """
    if not expected:
        return 1.0, []
    initial_state = initial_state or {}
    total = 0
    satisfied = 0
    details: List[Dict[str, Any]] = []
    for e in expected:
        atype = str(e.get("action_type", "")).upper()
        if atype == "INCREASE_PARAM":
            direction = 1
        elif atype == "DECREASE_PARAM":
            direction = -1
        else:
            continue
        object_id = e.get("object_id", "")
        attribute = e.get("attribute", "") or "value"
        initial = _lookup_state_value(initial_state, object_id, attribute)
        final = _lookup_state_value(telemetry, object_id, attribute)
        if initial is None or final is None:
            continue
        # Начальное состояние клапанов хранится в долях (0..1), телеметрия — в %.
        if attribute == "position" and f"{object_id}_position" in initial_state:
            try:
                if float(initial) <= 1.0:
                    initial = float(initial) * 100.0
            except (TypeError, ValueError):
                pass
        try:
            iv, fv = float(initial), float(final)
        except (TypeError, ValueError):
            continue
        total += 1
        if (direction == 1 and fv > iv) or (direction == -1 and fv < iv):
            satisfied += 1
        else:
            details.append({
                "object_id": object_id,
                "attribute": attribute,
                "action_type": atype,
                "initial": round(iv, 2),
                "final": round(fv, 2),
            })
    if not total:
        return 1.0, []
    return satisfied / total, details


def expected_state_score(expected: List[Dict[str, Any]], telemetry: Dict[str, Any],
                         initial_state: Optional[Dict[str, Any]] = None) -> float:
    score, _ = _expected_verdict(expected, telemetry, initial_state)
    return score


def expected_state_details(expected: List[Dict[str, Any]], telemetry: Dict[str, Any],
                           initial_state: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    _, details = _expected_verdict(expected, telemetry, initial_state)
    return details


def violations_for(actions: List[Dict[str, Any]], restrictions: List[Dict[str, Any]],
                   telemetry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Detect forbidden actions among the operator actions."""
    violations = []
    op_actions = [a for a in actions
                  if a.get("source") == "operator_panel" and a.get("accepted", 1)]
    for rule in restrictions:
        rule_action = rule.get("action_type", "").upper()
        rule_object = rule.get("object_id", "")
        rule_relation = rule.get("relation", "")
        for a in op_actions:
            act = str(a.get("action_type", "")).upper()
            if rule_action and act != rule_action:
                continue
            if rule_object and a.get("equipment_id") != rule_object:
                continue
            matched = True
            if rule_relation:
                value = a.get("new_value")
                cond = {"object_id": rule_object or a.get("equipment_id", ""),
                        "attribute": "new_value",
                        "relation": rule_relation, "value": rule.get("value")}
                node = telemetry.get(a.get("equipment_id", ""), {})
                params = node.get("params", {}) if isinstance(node, dict) else {}
                actual = value if value is not None else params.get("value")
                if actual is None:
                    matched = False
                else:
                    if rule_relation in (">", "<", ">=", "<="):
                        try:
                            matched = {
                                ">": lambda: float(actual) > _num(rule.get("value")),
                                "<": lambda: float(actual) < _num(rule.get("value")),
                                ">=": lambda: float(actual) >= _num(rule.get("value")),
                                "<=": lambda: float(actual) <= _num(rule.get("value")),
                            }[rule_relation]()
                        except (TypeError, ValueError):
                            matched = False
                    else:
                        matched = str(actual) == str(rule.get("value"))
            if matched:
                violations.append({
                    **a,
                    "rule_message": rule.get("message", ""),
                    "severity": rule.get("severity", "warning"),
                })
    return violations


def sequence_score(expected: List[Dict[str, Any]], actions: List[Dict[str, Any]]) -> float:
    """Fraction of expected actions performed in the right relative order."""
    if not expected:
        return 1.0
    op = [a for a in actions if a.get("source") == "operator_panel" and a.get("accepted", 1)]
    exp = sorted(expected, key=lambda x: int(x.get("seq", 0)))

    def matches(e: Dict[str, Any], a: Dict[str, Any]) -> bool:
        et = str(e.get("action_type", "")).upper()
        at = str(a.get("action_type", "")).upper()
        if e.get("object_id") and a.get("equipment_id") != e.get("object_id"):
            return False
        if et in ("INCREASE_PARAM", "DECREASE_PARAM"):
            if at not in ("SET_VALUE", "SET_PARAM"):
                return False
            if a.get("old_value") is None or a.get("new_value") is None:
                return False
            try:
                old = float(a["old_value"])
                new = float(a["new_value"])
            except (TypeError, ValueError):
                return False
            return new > old if et == "INCREASE_PARAM" else new < old
        if et and at != et:
            return False
        ev = e.get("value")
        if ev is not None and a.get("new_value") is not None:
            try:
                if abs(float(ev) - float(a["new_value"])) > 1e-6:
                    return False
            except (TypeError, ValueError):
                if str(ev) != str(a.get("new_value")):
                    return False
        return True

    matched = 0
    ptr = 0
    for e in exp:
        found = False
        while ptr < len(op):
            if matches(e, op[ptr]):
                found = True
                ptr += 1
                break
            ptr += 1
        if found:
            matched += 1
    return matched / len(exp)


def practice_criteria(task: Dict[str, Any], actions: List[Dict[str, Any]],
                      telemetry: Dict[str, Any], duration_s: float,
                      tracked_errors: Optional[List[Dict[str, Any]]] = None,
                      initial_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    criteria_conf = task.get("criteria") or DEFAULT_CRITERIA

    seq = sequence_score(task.get("expected_actions", []), actions)
    goal, goal_details = _target_verdict(task.get("target_state", []), telemetry)
    expected, expected_details = _expected_verdict(
        task.get("expected_actions", []), telemetry, initial_state
    )

    duration_min = max(1, int(task.get("duration_min", 10)))
    limit = duration_min * 60.0
    if duration_s <= limit:
        time_s = 1.0
    else:
        overshoot = (duration_s - limit) / limit
        time_s = max(0.0, 1.0 - overshoot)

    violations = violations_for(actions, task.get("restrictions", []), telemetry)
    critical_violations = [
        v for v in violations if str(v.get("severity", "")).upper() == "CRITICAL"
    ]
    rejected = [a for a in actions if a.get("source") == "operator_panel" and not a.get("accepted", 1)]
    tracked_errors = tracked_errors or []
    penalty_breakdown: List[Dict[str, Any]] = []
    for error in tracked_errors:
        penalty_breakdown.append({
            "source": "error_tracker",
            "code": error.get("rule_error_type", ""),
            "severity": str(error.get("severity", "MEDIUM")).upper(),
            "points": _error_penalty(error.get("severity")),
            "message": error.get("cause", ""),
        })
    for violation in violations:
        penalty_breakdown.append({
            "source": "scenario_rule",
            "code": "RULE_VIOLATION",
            "severity": str(violation.get("severity", "WARNING")).upper(),
            "points": _error_penalty(violation.get("severity")),
            "message": violation.get("rule_message", ""),
        })
    for action in rejected:
        penalty_breakdown.append({
            "source": "rejected_action",
            "code": "REJECTED_ACTION",
            "severity": "MEDIUM",
            "points": REJECTED_ACTION_PENALTY,
            "message": action.get("reject_reason", "Команда отклонена системой"),
        })
    error_penalty = min(100.0, sum(item["points"] for item in penalty_breakdown))
    errors = max(0.0, 1.0 - error_penalty / 100.0)

    safety = 1.0
    for cv in critical_violations:
        safety -= 0.5
    for error in tracked_errors:
        if str(error.get("severity", "")).upper() == "CRITICAL":
            safety -= 0.5
    safety = max(0.0, safety)
    for a in actions:
        if a.get("source") == "scenario" and str(a.get("action_type", "")).upper() in ("EMERGENCY_STOP",):
            pass

    by_key = {
        "sequence": seq,
        "goal": goal,
        "parameters": goal,
        "expected": expected,
        "time": time_s,
        "errors": errors,
        "safety": safety,
    }
    out: Dict[str, Dict[str, Any]] = {}
    total_weight = 0.0
    weighted = 0.0
    for c in criteria_conf:
        key = c.get("key")
        weight = max(0.0, _num(c.get("weight"), 1.0))
        if not key:
            continue
        val = by_key.get(key, 0.0)
        criterion = {"title": c.get("title", key), "score": round(val * 100.0, 1), "weight": weight}
        if key == "errors":
            criterion.update({
                "error_count": len(penalty_breakdown),
                "penalty": round(error_penalty, 1),
                "breakdown": penalty_breakdown,
            })
        elif key == "goal" and goal_details:
            criterion["details"] = goal_details
        elif key == "expected" and expected_details:
            criterion["details"] = expected_details
        out[key] = criterion
        total_weight += weight
        weighted += val * weight
    score = (weighted / total_weight * 100.0) if total_weight else 0.0

    expected_count = len(task.get("expected_actions", []))
    completed_expected = round(seq * expected_count)
    # Expected actions are mandatory. Good timing and a stable initial state
    # must not make an untouched scenario pass.
    if expected_count:
        score = min(score, seq * 100.0)

    return {
        "criteria": out,
        "score": round(score, 1),
        "violations": violations,
        "tracked_errors": tracked_errors,
        "error_count": len(penalty_breakdown),
        "error_penalty": round(error_penalty, 1),
        "expected_count": expected_count,
        "completed_expected": completed_expected,
    }


def _fmt_value(value: Any, attribute: str) -> str:
    if isinstance(value, bool):
        return "включён" if value else "выключен"
    if value is None:
        return "неизвестно"
    unit = _ATTR_UNITS.get(attribute, "")
    try:
        return f"{float(value):g}{unit}"
    except (TypeError, ValueError):
        return f"{value}{unit}"


def _goal_failure_message(d: Dict[str, Any]) -> str:
    obj = d.get("object_id", "")
    attr = d.get("attribute", "")
    label = _ATTR_LABELS.get(attr, attr or "параметр")
    actual = _fmt_value(d.get("actual"), attr)
    required = _fmt_value(d.get("value"), attr)
    rel = _RELATION_LABELS.get(str(d.get("relation", "")), str(d.get("relation", "")))
    return f"Цель не достигнута: {label} {obj} — сейчас {actual}, требуется {rel} {required}."


def _expected_failure_message(d: Dict[str, Any]) -> str:
    obj = d.get("object_id", "")
    attr = d.get("attribute", "")
    label = _ATTR_LABELS.get(attr, attr or "параметр")
    need = _DIRECTION_LABEL.get(str(d.get("action_type", "")).upper(), "изменение")
    unit = _ATTR_UNITS.get(attr, "")
    return (f"Ожидаемое действие не выполнено: требуется {need} — {label} {obj} "
            f"изменилось с {d.get('initial')}{unit} до {d.get('final')}{unit}.")


def practice_feedback(result: Dict[str, Any]) -> tuple[List[str], List[str]]:
    good, bad = [], []
    criteria = result.get("criteria", {})
    for key, val in criteria.items():
        s = _num(val.get("score"))
        if s >= 80:
            good.append(f"{val.get('title')} — {s:.0f}%")
        elif s < 60:
            bad.append(f"{val.get('title')} — только {s:.0f}%")
        for d in val.get("details", []) or []:
            if key == "goal":
                bad.append(_goal_failure_message(d))
            elif key == "expected":
                bad.append(_expected_failure_message(d))
    for v in result.get("violations", []):
        msg = v.get("rule_message") or f"Запрещённое действие {v.get('action_type')} на {v.get('object_id')}"
        bad.append(msg)
    for error in result.get("tracked_errors", []):
        if error.get("cause"):
            bad.append(str(error["cause"]))
    penalty = _num(result.get("error_penalty"))
    if penalty > 0:
        bad.append(
            f"Учтено ошибок: {int(result.get('error_count', 0))}; "
            f"штраф по критерию «Ошибочные действия»: −{penalty:.0f} баллов."
        )
    expected_count = int(result.get("expected_count", 0))
    completed_expected = int(result.get("completed_expected", 0))
    if completed_expected < expected_count:
        bad.append(f"Обязательные действия: выполнено {completed_expected} из {expected_count}.")
    if not bad:
        good.append("Действия выполнены без нарушений требований безопасности.")
    return good, bad
