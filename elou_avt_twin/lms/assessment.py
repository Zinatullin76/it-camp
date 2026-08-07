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
    parameters Контроль параметров (target state reached)
    time       Время выполнения
    errors     Ошибочные действия
    safety     Безопасность (критические ошибки)

The weighted average of criteria gives the final X/100.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

DEFAULT_CRITERIA = [
    {"key": "sequence", "title": "Правильная последовательность", "weight": 1.0},
    {"key": "parameters", "title": "Контроль параметров", "weight": 1.0},
    {"key": "time", "title": "Время", "weight": 0.8},
    {"key": "errors", "title": "Ошибочные действия", "weight": 1.0},
    {"key": "safety", "title": "Безопасность", "weight": 1.5},
]


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


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


def target_state_score(target: List[Dict[str, Any]], telemetry: Dict[str, Any]) -> float:
    if not target:
        return 1.0
    satisfied = sum(1 for c in target if evaluate_condition(c, telemetry))
    return satisfied / len(target)


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
        if e.get("object_id") and a.get("equipment_id") != e.get("object_id"):
            return False
        if e.get("action_type") and str(a.get("action_type", "")).upper() != str(e.get("action_type", "")).upper():
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
                      telemetry: Dict[str, Any], duration_s: float) -> Dict[str, Dict[str, Any]]:
    criteria_conf = task.get("criteria") or DEFAULT_CRITERIA

    seq = sequence_score(task.get("expected_actions", []), actions)
    params = target_state_score(task.get("target_state", []), telemetry)

    duration_min = max(1, int(task.get("duration_min", 10)))
    limit = duration_min * 60.0
    if duration_s <= limit:
        time_s = 1.0
    else:
        overshoot = (duration_s - limit) / limit
        time_s = max(0.0, 1.0 - overshoot)

    violations = violations_for(actions, task.get("restrictions", []), telemetry)
    critical_violations = [v for v in violations if v.get("severity") == "critical"]
    rejected = [a for a in actions if a.get("source") == "operator_panel" and not a.get("accepted", 1)]
    errors_n = len(violations) + len(rejected)
    errors = max(0.0, 1.0 - min(1.0, errors_n * 0.15))

    safety = 1.0
    for cv in critical_violations:
        safety -= 0.5
    safety = max(0.0, safety)
    for a in actions:
        if a.get("source") == "scenario" and str(a.get("action_type", "")).upper() in ("EMERGENCY_STOP",):
            pass

    by_key = {
        "sequence": seq,
        "parameters": params,
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
        out[key] = {"title": c.get("title", key), "score": round(val * 100.0, 1), "weight": weight}
        total_weight += weight
        weighted += val * weight
    score = (weighted / total_weight * 100.0) if total_weight else 0.0

    return {"criteria": out, "score": round(score, 1), "violations": violations}


def practice_feedback(result: Dict[str, Dict[str, Any]]) -> tuple[List[str], List[str]]:
    good, bad = [], []
    criteria = result.get("criteria", {})
    for key, val in criteria.items():
        s = _num(val.get("score"))
        if s >= 80:
            good.append(f"{val.get('title')} — {s:.0f}%")
        elif s < 60:
            bad.append(f"{val.get('title')} — только {s:.0f}%")
    for v in result.get("violations", []):
        msg = v.get("rule_message") or f"Запрещённое действие {v.get('action_type')} на {v.get('object_id')}"
        bad.append(msg)
    if not bad:
        bad.append("Действия выполнены без нарушений требований безопасности.")
    return good, bad
