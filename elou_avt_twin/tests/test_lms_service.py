import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from auth.store import AuthStore
from lms.models import DebriefView, Difficulty, ReportRow, TaskCategory, TaskCreate
from lms.seeds import seed
from lms.service import LmsService
from lms.store import LmsStore
from persistence.session_store import SessionStore


def _make_completed(session_store: SessionStore, scenario_id: str = "STARTUP",
                    score: float = 85.0, qualification: str = "ХОРОШО") -> str:
    sid = session_store.begin_session(scenario_id, "operator",
                                      sim_start=0.0, wall_time=1000.0)
    session_store.start_session(sid, sim_start=0.0, wall_time=1000.0)
    session_store.finish_session(sid, sim_end=300.0, score=score,
                                 qualification=qualification, wall_time=2000.0)
    return sid


@pytest.fixture()
def svc(tmp_path):
    db = str(tmp_path / "lms_test.db")
    auth_store = AuthStore(db)
    auth_store.ensure_default_users()
    lms_store = LmsStore(db)
    seed(lms_store)
    lms_store.create_task(TaskCreate(
        title="Запуск установки", description="",
        scenario_id="STARTUP", category=TaskCategory.PRACTICE,
        difficulty=Difficulty.EASY, duration_min=10,
        required_competencies=["startup_shutdown", "pumps"],
    ))
    session_store = SessionStore(db)
    service = LmsService(
        store=lms_store, session_store=session_store,
        auth_store=auth_store, scenarios={},
    )
    return service, session_store, lms_store, auth_store


def test_reports_include_only_completed_practices(svc):
    service, session_store, *_ = svc
    sid = _make_completed(session_store)
    aborted = session_store.begin_session("STARTUP", "operator",
                                          sim_start=0.0, wall_time=1000.0)
    session_store.abort_session(aborted, wall_time=1500.0)

    reports = service.reports()
    assert isinstance(reports[0], ReportRow)
    assert [r.session_id for r in reports] == [sid]
    r = reports[0]
    assert r.operator_id == "operator"
    assert r.full_name == "Консольный оператор"
    assert r.performance_score == 85.0
    assert r.scenario_id == "STARTUP"
    assert r.task_title == "Запуск установки"
    assert r.qualification == "ХОРОШО"
    assert r.duration_s == 300.0


def test_operator_can_only_view_own_debrief(svc):
    service, session_store, *_ = svc
    sid = _make_completed(session_store)
    assert service.debrief(sid, "operator") is not None
    assert service.debrief(sid, "field_operator") is None


def test_delete_task(svc):
    service, *_ = svc
    tasks = service.store.list_tasks()
    assert len(tasks) == 1
    tid = tasks[0]["id"]
    service.store.delete_task(tid)
    assert service.store.get_task(tid) is None
    assert service.store.list_tasks() == []


def test_instructor_can_view_any_operator_debrief_without_mutation(svc):
    service, session_store, lms_store, auth_store = svc
    sid = _make_completed(session_store)
    user_id = auth_store.get_user_by_name("operator")["id"]
    lms_store.set_user_competency(user_id, "startup_shutdown", 40.0)

    view = service.debrief(sid, "instructor", allow_any=True, mutate=False)
    assert isinstance(view, DebriefView)
    assert view.operator_id == "operator"
    assert view.operator_full_name == "Консольный оператор"

    # просмотр отчёта не меняет уровень компетенции оператора
    stored = [c for c in lms_store.get_user_competencies(user_id)
              if c["code"] == "startup_shutdown"][0]["level_percent"]
    assert stored == 40.0

    # дельта показывается гипотетически (blend 0.7)
    delta = [d for d in view.competency_delta if d["code"] == "startup_shutdown"][0]
    assert delta["old"] == 40.0
    assert abs(delta["new"] - (40.0 * 0.3 + 85.0 * 0.7)) < 0.01
