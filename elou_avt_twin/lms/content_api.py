"""
lms/content_api.py
==================
REST API of the authoring & study system («Обуч.txt»).

Дерево маршрутов:

    Конструктор (инструктор, manage_courses):
        GET    /lms/authoring/modules/{id}        сводка модуля (теория/тест/задание/сценарий)
        POST   /lms/modules/{id}/publish          публикация модуля
        POST   /lms/modules/{id}/lessons          создать урок
        PUT    /lms/lessons/{id}                  изменить урок
        DELETE /lms/lessons/{id}
        PUT    /lms/modules/{id}/test             сохранить тест
        DELETE /lms/tests/{id}
        POST   /lms/tests/{id}/questions          добавить вопрос
        PUT    /lms/questions/{id}                изменить вопрос
        DELETE /lms/questions/{id}
        PUT    /lms/modules/{id}/task             сохранить практическое задание
        DELETE /lms/tasks/{id}
        PUT    /lms/modules/{id}/scenario         сохранить сценарий
        DELETE /lms/scenarios/{id}
        POST   /lms/scenarios/{id}/status         DRAFT/REVIEW/PUBLISHED/ARCHIVED
        GET    /lms/authoring/equipment           каталог оборудования схемы
        GET    /lms/authoring/scenarios           все сценарии всех модулей
        GET    /lms/authoring/scenario-status/{id}

    Оператор (view_courses / view_own_results):
        GET    /lms/modules/{id}/study            только опубликованный контент
        POST   /lms/tests/{id}/submit             ответы -> оценка
        POST   /lms/modules/{id}/practice/start   запуск практики на физическом ядре
        POST   /lms/practice/{session_id}/finish  автооценка практики
        GET    /lms/assessments                   свои результаты
        GET    /lms/assessments/{id}

    Инструктор (view_analytics / view_history):
        GET    /lms/instructor/operators          список операторов и итоги
        GET    /lms/instructor/assessments        все результаты
        GET    /lms/instructor/assessments/{id}
        GET    /lms/action-log                    журнал действий оператора
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from auth.deps import get_current_user, require_permission
from auth.models import Principal
from auth.store import AuthStore

from .content_models import (
    LessonWrite,
    PublishWrite,
    QuestionWrite,
    ScenarioWrite,
    ScadaLogWrite,
    StatusWrite,
    TaskWrite,
    TestSubmit,
    TestWrite,
)
from .content_service import ContentService
from .content_store import LmsContentStore
from .store import LmsStore

router = APIRouter(prefix="/lms", tags=["lms-content"])

_service: Optional[ContentService] = None


def get_service() -> ContentService:
    global _service
    if _service is None:
        _service = ContentService(
            content_store=LmsContentStore(),
            lms_store=LmsStore(),
            auth_store=AuthStore(),
        )
    return _service


def _not_found(e: Exception) -> HTTPException:
    return HTTPException(status_code=404, detail=str(e))


def _call(fn):
    try:
        return fn()
    except KeyError as e:
        raise _not_found(e)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


def _ensure_session_layer() -> None:
    """Ensure the shared training session store/recorder exists.

    IMPORTANT: must NOT `import api_server` here. When the server runs as
    `python api_server.py` the module is loaded as `__main__`, so importing
    `api_server` would execute the module a second time and create a *second*
    DigitalTwin, a second simulation loop and a second session recorder.
    The practice runs against that orphan twin while /state, SCADA and the
    WebSocket keep reading the __main__ twin -- so scenario events never show
    up and sessions finish with sim_end=0.0.
    """
    try:
        from __main__ import ensure_session_layer as _fn
    except ImportError:
        from api_server import ensure_session_layer as _fn
    _fn()


# ---------------------------------------------------------------------------
# Конструктор: сводка модуля, публикация, оборудование
# ---------------------------------------------------------------------------


@router.get("/authoring/modules/{module_id}",
            dependencies=[Depends(require_permission("manage_courses"))])
def authoring_module(module_id: int, current_user: Principal = Depends(get_current_user)):
    return _call(lambda: get_service().module_authoring_view(module_id))


@router.post("/modules/{module_id}/publish",
             dependencies=[Depends(require_permission("manage_courses"))])
def publish_module(module_id: int, req: PublishWrite,
                   current_user: Principal = Depends(get_current_user)):
    return _call(lambda: get_service().publish_module(module_id, req.published))


@router.get("/authoring/equipment",
            dependencies=[Depends(require_permission("manage_courses"))])
def authoring_equipment(current_user: Principal = Depends(get_current_user)):
    return get_service().equipment_catalog()


@router.get("/authoring/scenarios",
            dependencies=[Depends(require_permission("manage_courses"))])
def authoring_scenarios(current_user: Principal = Depends(get_current_user)):
    """Все сценарии всех модулей (для администратора)."""
    return get_service().scenarios_catalog()


@router.get("/authoring/scenario-status/{scenario_id}",
            dependencies=[Depends(require_permission("manage_courses"))])
def scenario_status_flow(scenario_id: int, current_user: Principal = Depends(get_current_user)):
    return _call(lambda: get_service().scenario_status_flow(scenario_id))


# ---------------------------------------------------------------------------
# Конструктор: уроки (теория)
# ---------------------------------------------------------------------------


@router.post("/modules/{module_id}/lessons",
             dependencies=[Depends(require_permission("manage_courses"))])
def create_lesson(module_id: int, req: LessonWrite,
                  current_user: Principal = Depends(get_current_user)):
    return _call(lambda: get_service().create_lesson(module_id, req))


@router.put("/lessons/{lesson_id}",
            dependencies=[Depends(require_permission("manage_courses"))])
def update_lesson(lesson_id: int, req: LessonWrite,
                  current_user: Principal = Depends(get_current_user)):
    return _call(lambda: get_service().update_lesson(lesson_id, req))


@router.delete("/lessons/{lesson_id}",
               dependencies=[Depends(require_permission("manage_courses"))])
def delete_lesson(lesson_id: int, current_user: Principal = Depends(get_current_user)):
    get_service().delete_lesson(lesson_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Конструктор: тесты и вопросы
# ---------------------------------------------------------------------------


@router.put("/modules/{module_id}/test",
            dependencies=[Depends(require_permission("manage_courses"))])
def save_test(module_id: int, req: TestWrite,
              current_user: Principal = Depends(get_current_user)):
    return _call(lambda: get_service().save_test(module_id, req))


@router.delete("/tests/{test_id}",
               dependencies=[Depends(require_permission("manage_courses"))])
def delete_test(test_id: int, current_user: Principal = Depends(get_current_user)):
    get_service().delete_test(test_id)
    return {"ok": True}


@router.post("/tests/{test_id}/questions",
             dependencies=[Depends(require_permission("manage_courses"))])
def create_question(test_id: int, req: QuestionWrite,
                    current_user: Principal = Depends(get_current_user)):
    return _call(lambda: get_service().create_question(test_id, req))


@router.put("/questions/{question_id}",
            dependencies=[Depends(require_permission("manage_courses"))])
def update_question(question_id: int, req: QuestionWrite,
                    current_user: Principal = Depends(get_current_user)):
    return _call(lambda: get_service().update_question(question_id, req))


@router.delete("/questions/{question_id}",
               dependencies=[Depends(require_permission("manage_courses"))])
def delete_question(question_id: int, current_user: Principal = Depends(get_current_user)):
    get_service().delete_question(question_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Конструктор: практическое задание
# ---------------------------------------------------------------------------


@router.put("/modules/{module_id}/task",
            dependencies=[Depends(require_permission("manage_courses"))])
def save_task(module_id: int, req: TaskWrite,
              current_user: Principal = Depends(get_current_user)):
    return _call(lambda: get_service().save_task(module_id, req))


@router.delete("/tasks/{task_id}",
               dependencies=[Depends(require_permission("manage_courses"))])
def delete_task(task_id: int, current_user: Principal = Depends(get_current_user)):
    get_service().delete_task(task_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Конструктор: сценарий
# ---------------------------------------------------------------------------


@router.put("/modules/{module_id}/scenario",
            dependencies=[Depends(require_permission("manage_courses"))])
def save_scenario(module_id: int, req: ScenarioWrite,
                  current_user: Principal = Depends(get_current_user)):
    return _call(lambda: get_service().save_scenario(module_id, req))


@router.delete("/scenarios/{scenario_id}",
               dependencies=[Depends(require_permission("manage_courses"))])
def delete_scenario(scenario_id: int, current_user: Principal = Depends(get_current_user)):
    get_service().delete_scenario(scenario_id)
    return {"ok": True}


@router.post("/scenarios/{scenario_id}/status",
             dependencies=[Depends(require_permission("manage_courses"))])
def set_scenario_status(scenario_id: int, req: StatusWrite,
                        current_user: Principal = Depends(get_current_user)):
    return _call(lambda: get_service().set_scenario_status(scenario_id, req.status.value))


# ---------------------------------------------------------------------------
# Оператор: изучение модуля (только опубликованный контент)
# ---------------------------------------------------------------------------


@router.get("/modules/{module_id}/study",
            dependencies=[Depends(require_permission("view_courses"))])
def study_module(module_id: int, current_user: Principal = Depends(get_current_user)):
    return _call(lambda: get_service().study_view(module_id))


@router.get("/practice-library",
            dependencies=[Depends(require_permission("view_courses"))])
def practice_library(current_user: Principal = Depends(get_current_user)):
    """Библиотека практики оператора: сценарии опубликованных курсов."""
    return get_service().practice_catalog(current_user.username)


@router.get("/practice-library/{task_id}",
            dependencies=[Depends(require_permission("view_courses"))])
def practice_library_task(task_id: int, current_user: Principal = Depends(get_current_user)):
    task = get_service().practice_catalog_task(task_id, current_user.username)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Задание '{task_id}' не найдено")
    return task


@router.post("/tests/{test_id}/submit",
             dependencies=[Depends(require_permission("view_courses"))])
def submit_test(test_id: int, req: TestSubmit,
                current_user: Principal = Depends(get_current_user)):
    return _call(lambda: get_service().submit_test(test_id, current_user.username, req))


@router.post("/modules/{module_id}/practice/start",
             dependencies=[Depends(require_permission("start_training"))])
def start_practice(module_id: int, current_user: Principal = Depends(get_current_user)):
    _ensure_session_layer()
    return _call(lambda: get_service().start_practice(
        module_id, current_user.username))


@router.post("/practice/{session_id}/ready",
             dependencies=[Depends(require_permission("start_training"))])
def ready_practice(session_id: str, current_user: Principal = Depends(get_current_user)):
    _ensure_session_layer()
    return _call(lambda: get_service().ready_practice(session_id, current_user.username))


@router.post("/practice/{session_id}/finish",
             dependencies=[Depends(require_permission("start_training"))])
def finish_practice(session_id: str, current_user: Principal = Depends(get_current_user)):
    _ensure_session_layer()
    return _call(lambda: get_service().finish_practice(session_id, current_user.username))


# ---------------------------------------------------------------------------
# Оператор: свои результаты
# ---------------------------------------------------------------------------


@router.get("/assessments", dependencies=[Depends(require_permission("view_own_results"))])
def my_assessments(limit: int = Query(100, ge=1, le=500),
                   current_user: Principal = Depends(get_current_user)):
    return get_service().assessments(username=current_user.username, limit=limit)


@router.get("/assessments/{assessment_id}",
            dependencies=[Depends(require_permission("view_own_results"))])
def assessment_detail(assessment_id: int,
                      current_user: Principal = Depends(get_current_user)):
    rows = [a for a in get_service().assessments(username=current_user.username)
            if a.get("id") == assessment_id]
    if not rows:
        raise HTTPException(status_code=404, detail=f"Оценка '{assessment_id}' не найдена")
    return rows[0]


# ---------------------------------------------------------------------------
# Инструктор: операторы, результаты, журнал действий
# ---------------------------------------------------------------------------


@router.get("/instructor/operators",
            dependencies=[Depends(require_permission("view_analytics"))])
def instructor_operators(current_user: Principal = Depends(get_current_user)):
    return get_service().operators()


@router.get("/instructor/assessments",
            dependencies=[Depends(require_permission("view_analytics"))])
def instructor_assessments(limit: int = Query(300, ge=1, le=1000),
                           current_user: Principal = Depends(get_current_user)):
    return get_service().assessments(limit=limit)


@router.get("/instructor/assessments/{assessment_id}",
            dependencies=[Depends(require_permission("view_analytics"))])
def instructor_assessment(assessment_id: int,
                          current_user: Principal = Depends(get_current_user)):
    return _call(lambda: get_service()._assessment_view(assessment_id))


@router.get("/action-log", dependencies=[Depends(require_permission("view_history"))])
def action_log(username: Optional[str] = None,
               object_id: Optional[str] = None,
               session_id: Optional[str] = None,
               limit: int = Query(500, ge=1, le=2000),
               current_user: Principal = Depends(get_current_user)):
    return get_service().action_log(username=username, object_id=object_id,
                                    session_id=session_id, limit=limit)


# ---------------------------------------------------------------------------
# SCADA: журнал кликов по объектам и время в окне
# ---------------------------------------------------------------------------


@router.post("/scada-log", dependencies=[Depends(require_permission("view_scheme"))])
def scada_log_write(req: ScadaLogWrite,
                    current_user: Principal = Depends(get_current_user)):
    get_service().log_scada_event(current_user.username, req)
    return {"ok": True}


@router.get("/scada-log", dependencies=[Depends(require_permission("view_history"))])
def scada_log(username: Optional[str] = None,
              object_id: Optional[str] = None,
              event_type: Optional[str] = None,
              session_id: Optional[str] = None,
              limit: int = Query(500, ge=1, le=5000),
              current_user: Principal = Depends(get_current_user)):
    return get_service().scada_log(username=username, object_id=object_id,
                                   event_type=event_type, session_id=session_id,
                                   limit=limit)
