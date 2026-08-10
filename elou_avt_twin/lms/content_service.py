"""
lms/content_service.py
======================
Business logic of the authoring & study system («Обуч.txt»).

Covers the full loop:
    documentation -> material(Lesson) -> test -> task -> scenario
        -> SCADA run -> assessment -> competency
"""

from __future__ import annotations

import time as _time
import uuid
from typing import Any, Dict, List, Optional

from auth.store import AuthStore

from . import assessment as assess
from . import runtime
from .content_models import (
    Assessment,
    AssessmentKind,
    Lesson,
    LessonWrite,
    ModuleStudy,
    QuestionWrite,
    ScadaLogWrite,
    ScenarioDefinition,
    ScenarioWrite,
    TaskWrite,
    TestConfig,
    TestWrite,
    TestSubmit,
    TrainingTask,
)
from .content_store import LmsContentStore
from .scenario_service import to_engine_scenario
from .store import LmsStore


def _now() -> float:
    return _time.time()


class ContentService:
    def __init__(self, content_store: LmsContentStore, lms_store: LmsStore,
                 auth_store: AuthStore):
        self.store = content_store
        self.lms = lms_store
        self.auth = auth_store
        self._ready_sessions: set[str] = set()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _user_id(self, username: str) -> Optional[int]:
        u = self.auth.get_user_by_name(username)
        if u is None and username == "system":
            u = self.auth.get_user_by_name("operator")
        return int(u["id"]) if u else None

    def _full_name(self, username: str) -> str:
        u = self.auth.get_user_by_name(username)
        return u.get("full_name", "") if u else ""

    def _module_title(self, module_id: int) -> str:
        m = self.store.module(module_id)
        return m.get("title", "") if m else ""

    def _scenario_title(self, scenario_id: Optional[str]) -> str:
        if not scenario_id:
            return ""
        parts = scenario_id.split("-")
        if len(parts) == 2 and parts[0] == "LMS":
            try:
                s = self.store.get_scenario(int(parts[1]))
                return s.get("title", "") if s else ""
            except (TypeError, ValueError):
                return ""
        return scenario_id

    def _task_title(self, task_id: Optional[int]) -> str:
        if not task_id:
            return ""
        t = self.store.get_task(int(task_id))
        return t.get("title", "") if t else ""

    def _module_ok(self, module_id: int) -> Dict[str, Any]:
        m = self.store.module(module_id)
        if m is None:
            raise KeyError(f"Модуль '{module_id}' не найден")
        return m

    # ------------------------------------------------------------------
    # Equipment / competencies catalog (для привязки в конструкторе)
    # ------------------------------------------------------------------

    def equipment_catalog(self) -> List[Dict[str, Any]]:
        scheme = runtime.get_scheme()
        if scheme is None:
            return []
        return [
            {"id": n.id, "type": n.type, "name": n.name,
             "params": {k: v for k, v in (n.params or {}).items() if isinstance(v, (int, float))}}
            for n in scheme.nodes
        ]

    def competency_catalog(self) -> List[Dict[str, Any]]:
        return self.lms.list_competencies()

    # ------------------------------------------------------------------
    # Authoring views
    # ------------------------------------------------------------------

    def module_authoring_view(self, module_id: int) -> Dict[str, Any]:
        m = self._module_ok(module_id)
        lessons = self.store.list_lessons(module_id)
        test = self.store.get_test_by_module(module_id, with_answers=True)
        task = self.store.get_task_by_module(module_id)
        scenario = self.store.get_scenario_by_module(module_id)
        return {
            "module": {
                **m,
                "published": bool(m.get("published")),
                "course_id": m.get("course_id"),
            },
            "lessons": lessons,
            "test": test,
            "task": task,
            "scenario": scenario,
        }

    def publish_module(self, module_id: int, published: bool) -> Dict[str, Any]:
        m = self._module_ok(module_id)
        self.store.set_module_published(module_id, published)
        self.lms.add_log(
            f"Модуль «{m['title']}» {'опубликован' if published else 'снят с публикации'}",
            category="authoring")
        return self.module_authoring_view(module_id)

    # ------------------------------------------------------------------
    # Lessons
    # ------------------------------------------------------------------

    def create_lesson(self, module_id: int, w: LessonWrite) -> Dict[str, Any]:
        self._module_ok(module_id)
        lid = self.store.create_lesson(module_id, w)
        return self.store.get_lesson(lid)

    def update_lesson(self, lesson_id: int, w: LessonWrite) -> Dict[str, Any]:
        self.store.update_lesson(lesson_id, w)
        return self.store.get_lesson(lesson_id)

    def delete_lesson(self, lesson_id: int) -> None:
        self.store.delete_lesson(lesson_id)

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def save_test(self, module_id: int, w: TestWrite) -> Dict[str, Any]:
        self._module_ok(module_id)
        tid = self.store.upsert_test(module_id, w)
        return self.store.get_test(tid)

    def delete_test(self, test_id: int) -> None:
        self.store.delete_test(test_id)

    def create_question(self, test_id: int, w: QuestionWrite) -> Dict[str, Any]:
        qid = self.store.create_question(test_id, w)
        return self.store.get_question(qid)

    def update_question(self, question_id: int, w: QuestionWrite) -> Dict[str, Any]:
        self.store.update_question(question_id, w)
        return self.store.get_question(question_id)

    def delete_question(self, question_id: int) -> None:
        self.store.delete_question(question_id)

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def save_task(self, module_id: int, w: TaskWrite) -> Dict[str, Any]:
        self._module_ok(module_id)
        tid = self.store.upsert_task(module_id, w)
        return self.store.get_task(tid)

    def delete_task(self, task_id: int) -> None:
        self.store.delete_task(task_id)

    # ------------------------------------------------------------------
    # Scenarios
    # ------------------------------------------------------------------

    def save_scenario(self, module_id: int, w: ScenarioWrite) -> Dict[str, Any]:
        self._module_ok(module_id)
        sid = self.store.upsert_scenario(module_id, w)
        return self.store.get_scenario(sid)

    def delete_scenario(self, scenario_id: int) -> None:
        self.store.delete_scenario(scenario_id)

    def set_scenario_status(self, scenario_id: int, status: str) -> Dict[str, Any]:
        s = self.store.get_scenario(scenario_id)
        if s is None:
            raise KeyError(f"Сценарий '{scenario_id}' не найден")
        allowed = {"DRAFT", "REVIEW", "PUBLISHED", "ARCHIVED"}
        status = status.upper()
        if status not in allowed:
            raise ValueError(f"Недопустимый статус: {status}")
        self.store.set_scenario_status(scenario_id, status)
        return self.store.get_scenario(scenario_id)

    def scenario_status_flow(self, scenario_id: int) -> List[Dict[str, Any]]:
        s = self.store.get_scenario(scenario_id)
        if s is None:
            raise KeyError(f"Сценарий '{scenario_id}' не найден")
        current = s.get("status", "DRAFT")
        next_map = {
            "DRAFT": "REVIEW",
            "REVIEW": "PUBLISHED",
            "PUBLISHED": "ARCHIVED",
        }
        return [{"status": st, "current": st == current,
                 "next": next_map.get(st)} for st in ("DRAFT", "REVIEW", "PUBLISHED", "ARCHIVED")]

    # ------------------------------------------------------------------
    # Operator study view (только опубликованный контент)
    # ------------------------------------------------------------------

    def study_view(self, module_id: int) -> ModuleStudy:
        m = self._module_ok(module_id)
        if not m.get("published"):
            raise PermissionError("Модуль не опубликован — оператору недоступен")
        lessons = self.store.list_lessons(module_id)
        test = self.store.get_test_by_module(module_id, with_answers=False)
        task = self.store.get_task_by_module(module_id)
        if task and not task.get("enabled"):
            task = None
        scenario = self.store.get_scenario_by_module(module_id)
        if scenario and scenario.get("status") != "PUBLISHED":
            scenario = None
        return ModuleStudy(
            module={"id": m["id"], "title": m["title"], "description": m.get("description", ""),
                    "kind": m.get("kind"), "content": m.get("content", "")},
            lessons=[Lesson(**l) for l in lessons],
            test=TestConfig(**test) if test else None,
            task=TrainingTask(**task) if task else None,
            scenario=ScenarioDefinition(**scenario) if scenario else None,
            equipment=self.equipment_catalog(),
            competencies=self.competency_catalog(),
        )

    # ------------------------------------------------------------------
    # Practice catalog (страница «Практика» = сценарии курсов)
    # ------------------------------------------------------------------

    def _practice_task_view(self, task: Dict[str, Any], module: Dict[str, Any],
                            scenario: Dict[str, Any], comp_levels: Dict[str, float]) -> Dict[str, Any]:
        req = task.get("competency_codes", []) or []
        avg_req = (sum(comp_levels.get(c, 0.0) for c in req) / len(req)) if req else 100.0
        is_exam = bool(scenario.get("is_exam"))
        return {
            "id": task["id"],
            "module_id": int(task["module_id"]),
            "module_title": module.get("title", ""),
            "title": task.get("title", ""),
            "description": task.get("goal", ""),
            "scenario_id": f"LMS-{scenario['id']}",
            "scenario_name": scenario.get("title", ""),
            "category": "exam" if is_exam else "practice",
            "difficulty": "HARD" if is_exam else "MIDDLE",
            "duration_min": int(task.get("duration_min", 10) or 10),
            "required_competencies": req,
            "enabled": True,
            "is_random": False,
            "is_ready": avg_req >= 50.0,
            "readiness_percent": round(avg_req, 1),
        }

    def practice_catalog(self, username: str) -> List[Dict[str, Any]]:
        """Опубликованные практические задания курсов.

        «Практика» = сценарии курсов: берутся только опубликованные модули
        с заданием и опубликованным сценарием (lms_training_tasks +
        lms_scenarios). Запуск идёт тем же движком, что и в курсах.
        """
        user_id = self._user_id(username) or 0
        comp_levels = {c["code"]: float(c["level_percent"])
                       for c in self.lms.get_user_competencies(user_id)}
        out = []
        for course in self.lms.list_courses():
            for module in self.lms.get_modules(int(course["id"])):
                mid = int(module["id"])
                m = self.store.module(mid)
                if m is None or not m.get("published"):
                    continue
                task = self.store.get_task_by_module(mid)
                if task is None or not task.get("enabled"):
                    continue
                scenario = self.store.get_scenario_by_module(mid)
                if scenario is None or scenario.get("status") != "PUBLISHED":
                    continue
                out.append(self._practice_task_view(task, m, scenario, comp_levels))
        out.sort(key=lambda t: (t["category"], t["module_title"], t["title"]))
        return out

    def practice_catalog_task(self, task_id: int,
                              username: Optional[str] = None) -> Optional[Dict[str, Any]]:
        task = self.store.get_task(task_id)
        if task is None:
            return None
        module_id = int(task["module_id"])
        m = self.store.module(module_id)
        scenario = self.store.get_scenario_by_module(module_id)
        if m is None or not m.get("published"):
            return None
        if scenario is None or scenario.get("status") != "PUBLISHED":
            return None
        user_id = self._user_id(username) if username else 0
        comp_levels = {c["code"]: float(c["level_percent"])
                       for c in self.lms.get_user_competencies(user_id)}
        return self._practice_task_view(task, m, scenario, comp_levels)

    # ------------------------------------------------------------------
    # Test submission
    # ------------------------------------------------------------------

    def submit_test(self, test_id: int, username: str, req: TestSubmit) -> Dict[str, Any]:
        test = self.store.get_test(test_id, with_answers=True)
        if test is None:
            raise KeyError(f"Тест '{test_id}' не найден")
        result = assess.assess_test(test, req.answers, duration_s=req.duration_s)
        module_id = int(test["module_id"])
        user_id = self._user_id(username) or 0

        # Blending competencies + module progress are applied on the best try.
        previous = self.store.latest_assessment(user_id, module_id, "test")
        if previous is None or result["score"] > float(previous.get("score", 0.0)):
            self._apply_competencies(user_id, test.get("competency_codes", []), result["score"])
            self.lms.mark_module_completed(user_id, module_id, result["score"])

        a = Assessment(
            user_id=user_id, module_id=module_id, kind=AssessmentKind.TEST,
            test_id=test_id, score=result["score"], max_score=100.0,
            passed=result["passed"], criteria_scores={
                "test": {"score": result["score"], "passed": result["passed"]},
                "detail": result["questions"]},
            errors_count=result.get("unanswered_required", 0),
            duration_s=req.duration_s,
            answers=req.answers,
            feedback_good=result["feedback_good"],
            feedback_bad=result["feedback_bad"],
            started_at=_now() - req.duration_s,
            finished_at=_now(),
        )
        aid = self.store.create_assessment(a)
        return self._assessment_view(aid)

    # ------------------------------------------------------------------
    # Practice: scenario run + finish
    # ------------------------------------------------------------------

    def start_practice(self, module_id: int, username: str, kind: str = "practice") -> Dict[str, Any]:
        m = self._module_ok(module_id)
        task = self.store.get_task_by_module(module_id)
        scenario = self.store.get_scenario_by_module(module_id)
        if task is None:
            raise KeyError("У модуля нет практического задания")
        scenario_id = task.get("scenario_id") or (f"LMS-{scenario['id']}" if scenario else "NORMAL_OPERATION")
        scenario_name = task.get("title", scenario_id)

        twin = runtime.get_twin()
        recorder = runtime.get_session_recorder()

        if recorder is not None and recorder.active:
            recorder.abort(reason="superseded by new practice session")
        self._ready_sessions.clear()
        session_store = runtime.get_session_store()
        session_id = f"PR-{uuid.uuid4().hex}"

        # DB-сценарий -> физическое ядро; иначе библиотечный сценарий.
        if scenario is not None:
            engine_scenario = to_engine_scenario(scenario)
            twin.create_simulation()
            scheme = runtime.get_scheme()
            if scheme is not None:
                twin._engine.set_scheme(scheme)
            twin.load_scenario_object(engine_scenario)
        else:
            twin.create_simulation()
            scheme = runtime.get_scheme()
            if scheme is not None:
                twin._engine.set_scheme(scheme)
            twin.load_scenario(task.get("scenario_id") or "NORMAL_OPERATION")

        twin._engine.set_feed_override(runtime.get_inputs())

        if recorder is not None:
            recorder.begin(
                scenario_id=scenario_id,
                operator_id=username,
                scheme_version=scheme.id if scheme else "",
                reference_actions=task.get("expected_actions", []),
                sim_start=twin._simulation_time,
                session_id=session_id,
            )
            recorder.record_snapshot(twin.get_state(), reason="start")

        self.lms.mark_module_started(self._user_id(username) or 0, module_id)
        self.lms.add_log(f"Оператор {username} начал практику «{task.get('title')}»", category="practice")
        return {
            "session_id": session_id,
            "scenario_id": scenario_id,
            "scenario_name": scenario_name,
            "module_id": module_id,
            "task_id": task["id"],
            "sim_time": twin._simulation_time,
        }

    def ready_practice(self, session_id: str, username: str) -> Dict[str, Any]:
        """Start simulation time only after the operator's SCADA is rendered."""
        recorder = runtime.get_session_recorder()
        if recorder is None or recorder.session_id != session_id:
            raise KeyError(f"Сессия '{session_id}' не является активной")
        if session_id not in self._ready_sessions:
            twin = runtime.get_twin()
            twin.start()
            store = runtime.get_session_store()
            if store is not None:
                store.start_session(session_id, sim_start=twin._simulation_time)
            self._ready_sessions.add(session_id)
            self.lms.add_log(
                f"SCADA оператора {username} готова, таймер практики запущен",
                category="practice",
            )
        return {
            "session_id": session_id,
            "status": "RUNNING",
            "sim_time": runtime.get_twin()._simulation_time,
        }

    def finish_practice(self, session_id: str, username: str) -> Dict[str, Any]:
        session_store = runtime.get_session_store()
        session = session_store.get_session(session_id) if session_store else None
        if session is None:
            raise KeyError(f"Сессия '{session_id}' не найдена")
        actions = session_store.get_actions(session_id)
        tracked_errors = session_store.get_errors(session_id)
        task = None
        # find task by scenario binding
        scenario_id = session.get("scenario_id", "")
        if scenario_id.startswith("LMS-"):
            try:
                sid = int(scenario_id.split("-", 1)[1])
                task = self.store.get_scenario(sid)
                task = self.store.get_task_by_module(int(task["module_id"])) if task else None
            except (TypeError, ValueError):
                task = None
        if task is None:
            # library scenario -> first task referencing it
            for t in self.store.list_tasks_all():
                if t.get("scenario_id") == scenario_id:
                    task = t
                    break

        telemetry = runtime.node_telemetry()
        dur = 0.0
        if session.get("sim_start") is not None and session.get("sim_end") is not None:
            dur = max(0.0, float(session["sim_end"]) - float(session["sim_start"]))
        else:
            wall = (session.get("wall_end") or _time.time()) - (session.get("wall_start") or 0.0)
            dur = max(0.0, float(wall))

        if task is None:
            result = {"score": 0.0, "criteria": {}, "violations": [],
                      "feedback_good": [], "feedback_bad": ["Задание не найдено для оценки"]}
            module_id = 0
        else:
            result = assess.practice_criteria(task, actions, telemetry, dur, tracked_errors)
            module_id = int(task["module_id"])
            good, bad = assess.practice_feedback(result)
            result["feedback_good"] = good
            result["feedback_bad"] = bad

        # Журнал действий оператора («Обуч.txt» §12).
        user_id = self._user_id(username) or 0
        for a in actions:
            self.store.add_action_log({
                "timestamp": float(a.get("wall_time") or _time.time()),
                "user_id": user_id,
                "username": username,
                "object_id": a.get("equipment_id", ""),
                "object_name": a.get("equipment_id", ""),
                "action": a.get("action_type", ""),
                "old_state": a.get("old_value"),
                "new_state": a.get("new_value"),
                "source": a.get("source", "operator_panel"),
                "session_id": session_id,
                "module_id": module_id or None,
            })

        score = result.get("score", 0.0)
        errors_count = int(result.get("error_count", 0))
        critical_count = sum(1 for v in result.get("violations", [])
                             if str(v.get("severity", "")).upper() == "CRITICAL")
        critical_count += sum(
            1 for error in tracked_errors
            if str(error.get("severity", "")).upper() == "CRITICAL"
        )
        passed = score >= 70.0

        if module_id and user_id:
            self._apply_competencies(user_id, task.get("competency_codes", []), score)
            self.lms.mark_module_completed(user_id, module_id, score, session_id=session_id)

        a = Assessment(
            user_id=user_id, module_id=module_id, kind=AssessmentKind.PRACTICE,
            task_id=task["id"] if task else None,
            scenario_id=scenario_id, score=score, max_score=100.0, passed=passed,
            criteria_scores=result.get("criteria", {}),
            errors_count=errors_count, critical_errors_count=critical_count,
            duration_s=round(dur, 1), answers=None,
            feedback_good=result.get("feedback_good", []),
            feedback_bad=result.get("feedback_bad", []),
            session_id=session_id, started_at=float(session.get("wall_start", 0.0)),
            finished_at=_now(),
        )
        aid = self.store.create_assessment(a)
        self.lms.add_log(f"Оператор {username} завершил практику: {score:.0f}/100", category="assessment")

        # Закрыть общий рекордер, чтобы последующие действия оператора
        # не попадали в завершённую практику.
        recorder = runtime.get_session_recorder()
        if recorder is not None and recorder.active and recorder.session_id == session_id:
            recorder.end(sim_end=runtime.get_twin()._simulation_time, score=score)
        self._ready_sessions.discard(session_id)

        return self._assessment_view(aid)

    def _apply_competencies(self, user_id: int, codes: List[str], score: float) -> None:
        for code in codes:
            if code:
                self.lms.blend_user_competency(user_id, code, score, weight=0.7)

    # ------------------------------------------------------------------
    # Assessments
    # ------------------------------------------------------------------

    def _assessment_view(self, assessment_id: int) -> Dict[str, Any]:
        a = self.store.get_assessment(assessment_id)
        if a is None:
            raise KeyError(f"Оценка '{assessment_id}' не найдена")
        uid = a.get("user_id")
        user = self.auth.user_view(uid) if uid else None
        return {
            **a,
            "username": user.username if user else "",
            "full_name": user.full_name if user else "",
            "module_title": self._module_title(int(a.get("module_id", 0) or 0)),
            "task_title": self._task_title(a.get("task_id")),
            "scenario_title": self._scenario_title(a.get("scenario_id")),
        }

    def assessments(self, username: Optional[str] = None, module_id: Optional[int] = None,
                    limit: int = 200) -> List[Dict[str, Any]]:
        user_id = self._user_id(username) if username else None
        rows = self.store.list_assessments(user_id=user_id, module_id=module_id, limit=limit)
        users = {}
        out = []
        for r in rows:
            uid = r.get("user_id")
            if uid not in users:
                u = self.auth.user_view(uid) if uid else None
                users[uid] = (u.username if u else "", u.full_name if u else "")
            uname, fname = users[uid]
            out.append({
                **r,
                "username": uname, "full_name": fname,
                "module_title": self._module_title(int(r.get("module_id", 0) or 0)),
                "task_title": self._task_title(r.get("task_id")),
                "scenario_title": self._scenario_title(r.get("scenario_id")),
            })
        return out

    def operators(self) -> List[Dict[str, Any]]:
        """Список операторов с итогами и компетенциями (для инструктора)."""
        out = []
        for u in self.auth.list_users():
            if "operator" not in (u.roles or []) and u.username != "operator":
                continue
            uid = int(u.id)
            assessments = self.store.list_assessments(user_id=uid, limit=100)
            passed = [a for a in assessments if a.get("passed")]
            avg = (sum(float(a.get("score", 0.0)) for a in passed) / len(passed)) if passed else 0.0
            comps = [{"code": c["code"], "title": c["title"],
                      "level_percent": float(c["level_percent"])}
                     for c in self.lms.get_user_competencies(uid)]
            out.append({
                "user_id": uid,
                "username": u.username,
                "full_name": u.full_name,
                "total_assessments": len(assessments),
                "passed_assessments": len(passed),
                "avg_score": round(avg, 1),
                "last_assessment": self._assessment_view(assessments[0]["id"]) if assessments else None,
                "competencies": comps,
            })
        return out

    def action_log(self, username: Optional[str] = None, object_id: Optional[str] = None,
                   session_id: Optional[str] = None, limit: int = 500) -> List[Dict[str, Any]]:
        return self.store.list_action_log(
            username=username, object_id=object_id, session_id=session_id, limit=limit)

    # ------------------------------------------------------------------
    # SCADA interaction log (клики по объектам и время в окне)
    # ------------------------------------------------------------------

    def log_scada_event(self, username: str, req: ScadaLogWrite) -> None:
        self.store.add_scada_log({
            "timestamp": _now(),
            "user_id": self._user_id(username),
            "username": username,
            "event_type": req.event_type.value,
            "object_id": req.object_id,
            "object_name": req.object_name,
            "duration_s": req.duration_s,
            "session_id": req.session_id,
            "module_id": req.module_id,
        })

    def scada_log(self, username: Optional[str] = None, object_id: Optional[str] = None,
                  event_type: Optional[str] = None, session_id: Optional[str] = None,
                  limit: int = 500) -> List[Dict[str, Any]]:
        return self.store.list_scada_log(
            username=username, object_id=object_id, event_type=event_type,
            session_id=session_id, limit=limit)

    def log_action(self, username: str, object_id: str, action: str,
                   old_state: Any = None, new_state: Any = None,
                   source: str = "operator_panel", module_id: Optional[int] = None) -> None:
        self.store.add_action_log({
            "timestamp": _now(),
            "user_id": self._user_id(username),
            "username": username,
            "object_id": object_id,
            "object_name": object_id,
            "action": action,
            "old_state": old_state,
            "new_state": new_state,
            "source": source,
            "module_id": module_id,
        })
