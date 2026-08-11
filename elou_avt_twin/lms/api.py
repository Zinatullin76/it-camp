"""
lms/api.py
==========
REST API of the LMS layer — кабинеты оператора / инструктора / администратора
(по «Визуал.txt»). Все маршруты защищены RBAC-правами из `auth/`; операторские
маршруты определяют вызывающего через `get_current_user`.

Дерево маршрутов:

    /lms/dashboard                      оператор   — Главная
    /lms/profile                        оператор   — Профиль
    /lms/courses                        оператор   — Мои курсы
    /lms/courses/{course_id}            оператор   — курс с прогрессом
    /lms/competencies                   оператор   — Мои компетенции
    /lms/history                        оператор   — История
    /lms/sessions/{id}/debrief          оператор   — разбор выполнения
    /lms/practice-tasks                 оператор   — Практика
    /lms/scenarios                      оператор   — каталог сценариев
    /lms/notifications                  оператор   — уведомления
    /lms/modules/{id}/start|theory|complete  оператор
    /lms/groups                         инструктор — группы
    /lms/analytics                      инструктор — аналитика
    /lms/monitoring                     инструктор — живой мониторинг
    /lms/settings                       администратор
    /lms/logs                           администратор
    /lms/courses|modules|practice-tasks администратор — CRUD справочников
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth.deps import get_current_user, require_permission
from auth.models import Principal
from auth.store import AuthStore
from persistence.session_store import SessionStore
from scenarios.scenario_registry import SCENARIO_REGISTRY

from .models import (
    AnalyticsView,
    CompetencyView,
    CourseCreate,
    CourseStatus,
    CourseUpdate,
    CourseView,
    DashboardView,
    DebriefView,
    GroupCreate,
    GroupMembersRequest,
    GroupUpdate,
    GroupView,
    HistoryRow,
    ModuleCreate,
    ModuleStatus,
    ModuleView,
    MonitorOperatorView,
    PracticeTask,
    ProfileView,
    ReportRow,
    SettingsUpdate,
    StudyGroup,
    TaskCreate,
    TaskUpdate,
    UserProgress,
)
from .content_store import LmsContentStore
from .seeds import seed
from .service import LmsService
from .store import LmsStore

router = APIRouter(prefix="/lms", tags=["lms"])

_service: Optional[LmsService] = None


def get_service() -> LmsService:
    """Lazily build the LMS service (shared SQLite `sessions.db`)."""
    global _service
    if _service is None:
        lms_store = LmsStore()
        seed(lms_store)
        auth_store = AuthStore()
        auth_store.ensure_catalog()
        auth_store.ensure_default_users()
        _service = LmsService(
            store=lms_store,
            session_store=SessionStore(),
            auth_store=auth_store,
            scenarios=SCENARIO_REGISTRY,
            content_store=LmsContentStore(),
        )
    return _service


def _user_id(service: LmsService, username: str) -> int:
    uid = service._user_id(username)
    if uid is not None:
        return uid
    if username == "system":
        # ELOU_AUTH_MODE=disabled резолвит principal="system" без записи в БД —
        # операции ведём от имени демо-аккаунтов.
        for name in ("operator", "instructor", "admin"):
            u = service.auth.get_user_by_name(name)
            if u:
                return int(u["id"])
    raise HTTPException(status_code=404, detail=f"Пользователь '{username}' не найден")


def _module_or_404(service: LmsService, module_id: int) -> Dict[str, Any]:
    m = service.store.get_module(module_id)
    if m is None:
        raise HTTPException(status_code=404, detail=f"Модуль '{module_id}' не найден")
    return m


# ---------------------------------------------------------------------------
# Оператор: Главная / Профиль / Курсы / Компетенции / История / Практика
# ---------------------------------------------------------------------------


@router.get("/dashboard", response_model=DashboardView,
            dependencies=[Depends(require_permission("view_dashboard"))])
def dashboard(current_user: Principal = Depends(get_current_user)):
    return get_service().dashboard(current_user.username)


@router.get("/profile", response_model=ProfileView,
            dependencies=[Depends(require_permission("view_profile"))])
def profile(current_user: Principal = Depends(get_current_user)):
    return get_service().profile(current_user.username)


@router.get("/courses", response_model=List[CourseView],
            dependencies=[Depends(require_permission("view_courses"))])
def courses(current_user: Principal = Depends(get_current_user)):
    return get_service().my_courses(current_user.username)


@router.get("/courses/{course_id}", response_model=CourseView,
            dependencies=[Depends(require_permission("view_courses"))])
def course_detail(course_id: int, current_user: Principal = Depends(get_current_user)):
    view = get_service().course_detail(course_id, current_user.username)
    if view is None:
        raise HTTPException(status_code=404, detail=f"Курс '{course_id}' не найден")
    return view


@router.get("/competencies", response_model=List[CompetencyView],
            dependencies=[Depends(require_permission("view_competencies"))])
def competencies(current_user: Principal = Depends(get_current_user)):
    return get_service().competencies(current_user.username)


@router.get("/history", response_model=List[HistoryRow],
            dependencies=[Depends(require_permission("view_history"))])
def history(limit: int = Query(200, ge=1, le=1000),
            current_user: Principal = Depends(get_current_user)):
    return get_service().history(current_user.username, limit=limit)


@router.get("/sessions/{session_id}/debrief", response_model=DebriefView,
            dependencies=[Depends(require_permission("view_history"))])
def session_debrief(session_id: str,
                    current_user: Principal = Depends(get_current_user)):
    view = get_service().debrief(session_id, current_user.username)
    if view is None:
        raise HTTPException(status_code=404, detail=f"Сессия '{session_id}' не найдена")
    return view


@router.get("/practice-tasks", response_model=List[PracticeTask],
            dependencies=[Depends(require_permission("view_courses"))])
def practice_tasks(include_exam: bool = True,
                   current_user: Principal = Depends(get_current_user)):
    """Библиотека практических заданий с признаком готовности оператора."""
    return get_service().list_practice_tasks(current_user.username, include_exam=include_exam)


@router.get("/practice-tasks/{task_id}", response_model=PracticeTask,
            dependencies=[Depends(require_permission("view_courses"))])
def practice_task(task_id: int, current_user: Principal = Depends(get_current_user)):
    task = get_service().practice_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Задание '{task_id}' не найдено")
    return task


@router.get("/scenarios", dependencies=[Depends(require_permission("view_courses"))])
def scenarios(current_user: Principal = Depends(get_current_user)):
    """Каталог сценариев тренажёра для запуска практики."""
    return [
        {"id": s.id, "name": s.name, "description": s.description}
        for s in SCENARIO_REGISTRY.values()
    ]


@router.get("/scenarios/mine", dependencies=[Depends(require_permission("manage_practice_tasks"))])
def my_scenarios(current_user: Principal = Depends(get_current_user)):
    """Сценарии, созданные текущим пользователем (для привязки заданий)."""
    service = get_service()
    author_id = _user_id(service, current_user.username)
    return [
        {"id": f"LMS-{s['id']}",
         "name": s.get("title") or f"LMS-{s['id']}",
         "description": s.get("description", "")}
        for s in service.content.list_scenarios_by_author(author_id)
    ]


@router.get("/notifications", dependencies=[Depends(require_permission("view_dashboard"))])
def notifications(current_user: Principal = Depends(get_current_user)):
    return get_service().notifications(current_user.username)


@router.post("/notifications/read", dependencies=[Depends(require_permission("view_dashboard"))])
def notifications_read(current_user: Principal = Depends(get_current_user)):
    get_service().mark_notifications_read(current_user.username)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Оператор: прогресс по модулям
# ---------------------------------------------------------------------------


class ModuleCompleteRequest(BaseModel):
    score: float
    session_id: Optional[str] = None


@router.post("/modules/{module_id}/start", dependencies=[Depends(require_permission("view_courses"))])
def module_start(module_id: int, current_user: Principal = Depends(get_current_user)):
    service = get_service()
    _module_or_404(service, module_id)
    service.store.mark_module_started(_user_id(service, current_user.username), module_id)
    return {"ok": True}


@router.post("/modules/{module_id}/theory", dependencies=[Depends(require_permission("view_courses"))])
def module_theory(module_id: int, current_user: Principal = Depends(get_current_user)):
    service = get_service()
    m = _module_or_404(service, module_id)
    if m["kind"] != "theory":
        raise HTTPException(status_code=422, detail="Модуль не является теоретическим")
    service.store.set_theory_completed(_user_id(service, current_user.username), module_id)
    return {"ok": True}


@router.post("/modules/{module_id}/complete", dependencies=[Depends(require_permission("view_courses"))])
def module_complete(module_id: int, req: ModuleCompleteRequest,
                    current_user: Principal = Depends(get_current_user)):
    service = get_service()
    m = _module_or_404(service, module_id)
    user_id = _user_id(service, current_user.username)
    service.store.mark_module_completed(user_id, module_id, req.score, req.session_id)
    service.store.add_notification(
        user_id, f"Модуль «{m['title']}» завершён с оценкой {req.score:.0f}.",
        kind="module")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Инструктор: группы
# ---------------------------------------------------------------------------


@router.get("/groups", response_model=List[StudyGroup],
            dependencies=[Depends(require_permission("view_group_progress"))])
def list_groups(current_user: Principal = Depends(get_current_user)):
    return get_service().list_groups()


@router.get("/groups/candidates",
            dependencies=[Depends(require_permission("view_group_progress"))])
def group_candidates(current_user: Principal = Depends(get_current_user)):
    """Операторы для добавления в группы (без manage_users)."""
    service = get_service()
    return [u for u in service.auth.list_users() if "operator" in u.roles]


@router.get("/groups/{group_id}", response_model=GroupView,
            dependencies=[Depends(require_permission("view_group_progress"))])
def group_detail(group_id: int, current_user: Principal = Depends(get_current_user)):
    view = get_service().group_view(group_id)
    if view is None:
        raise HTTPException(status_code=404, detail=f"Группа '{group_id}' не найдена")
    return view


@router.post("/groups", response_model=StudyGroup,
             dependencies=[Depends(require_permission("manage_groups"))])
def create_group(req: GroupCreate, current_user: Principal = Depends(get_current_user)):
    service = get_service()
    uid = _user_id(service, current_user.username)
    gid = service.create_group(req.name, req.description, req.course_id, uid)
    return service.store.get_group(gid)


@router.put("/groups/{group_id}", response_model=StudyGroup,
            dependencies=[Depends(require_permission("manage_groups"))])
def update_group(group_id: int, req: GroupUpdate,
                 current_user: Principal = Depends(get_current_user)):
    service = get_service()
    if service.store.get_group(group_id) is None:
        raise HTTPException(status_code=404, detail=f"Группа '{group_id}' не найдена")
    service.store.update_group(group_id, req)
    return service.store.get_group(group_id)


@router.delete("/groups/{group_id}", dependencies=[Depends(require_permission("manage_groups"))])
def delete_group(group_id: int, current_user: Principal = Depends(get_current_user)):
    service = get_service()
    if service.store.get_group(group_id) is None:
        raise HTTPException(status_code=404, detail=f"Группа '{group_id}' не найдена")
    service.store.delete_group(group_id)
    return {"ok": True}


@router.put("/groups/{group_id}/members", dependencies=[Depends(require_permission("manage_groups"))])
def set_group_members(group_id: int, req: GroupMembersRequest,
                      current_user: Principal = Depends(get_current_user)):
    service = get_service()
    if service.store.get_group(group_id) is None:
        raise HTTPException(status_code=404, detail=f"Группа '{group_id}' не найдена")
    service.store.set_members(group_id, req.user_ids)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Инструктор: аналитика и мониторинг
# ---------------------------------------------------------------------------


@router.get("/analytics", response_model=AnalyticsView,
            dependencies=[Depends(require_permission("view_analytics"))])
def analytics(current_user: Principal = Depends(get_current_user)):
    return get_service().analytics()


@router.get("/monitoring", response_model=List[MonitorOperatorView],
            dependencies=[Depends(require_permission("monitor_operators"))])
def monitoring(current_user: Principal = Depends(get_current_user)):
    return get_service().monitoring()


@router.get("/reports", response_model=List[ReportRow],
            dependencies=[Depends(require_permission("view_training_sessions"))])
def reports(limit: int = Query(200, ge=1, le=1000),
            current_user: Principal = Depends(get_current_user)):
    """Отчёты о пройденных практиках всех операторов (для инструктора)."""
    return get_service().reports(limit=limit)


@router.get("/reports/{session_id}", response_model=DebriefView,
            dependencies=[Depends(require_permission("view_training_sessions"))])
def report_detail(session_id: str,
                  current_user: Principal = Depends(get_current_user)):
    """Разбор выполнения любой практики оператора (для инструктора)."""
    view = get_service().debrief(session_id, current_user.username,
                                 allow_any=True, mutate=False)
    if view is None:
        raise HTTPException(status_code=404, detail=f"Сессия '{session_id}' не найдена")
    return view


# ---------------------------------------------------------------------------
# Администратор: настройки и журнал
# ---------------------------------------------------------------------------


@router.get("/settings", dependencies=[Depends(require_permission("manage_settings"))])
def get_settings(current_user: Principal = Depends(get_current_user)):
    return get_service().settings()


@router.put("/settings", dependencies=[Depends(require_permission("manage_settings"))])
def update_settings(req: SettingsUpdate, current_user: Principal = Depends(get_current_user)):
    get_service().update_settings(req.values, current_user.username)
    return {"ok": True}


@router.get("/logs", dependencies=[Depends(require_permission("view_logs"))])
def system_logs(limit: int = Query(200, ge=1, le=1000),
                current_user: Principal = Depends(get_current_user)):
    return get_service().logs(limit=limit)


# ---------------------------------------------------------------------------
# Администратор: CRUD курсов, модулей, заданий
# ---------------------------------------------------------------------------


@router.post("/courses", dependencies=[Depends(require_permission("manage_courses"))])
def create_course(req: CourseCreate, current_user: Principal = Depends(get_current_user)):
    service = get_service()
    cid = service.store.create_course(req.title, req.description,
                                      status=req.status.value if hasattr(req.status, "value") else req.status)
    service.store.add_log(f"Создан курс «{req.title}»", username=current_user.username, category="course")
    return service.store.get_course(cid)


@router.put("/courses/{course_id}", dependencies=[Depends(require_permission("manage_courses"))])
def update_course(course_id: int, req: CourseUpdate,
                  current_user: Principal = Depends(get_current_user)):
    service = get_service()
    if service.store.get_course(course_id) is None:
        raise HTTPException(status_code=404, detail=f"Курс '{course_id}' не найден")
    fields: Dict[str, Any] = {}
    if req.title is not None:
        fields["title"] = req.title
    if req.description is not None:
        fields["description"] = req.description
    if req.status is not None:
        fields["status"] = req.status.value if hasattr(req.status, "value") else req.status
    service.store.update_course(course_id, fields)
    return service.store.get_course(course_id)


@router.post("/courses/{course_id}/modules", dependencies=[Depends(require_permission("manage_courses"))])
def add_module(course_id: int, req: ModuleCreate,
               current_user: Principal = Depends(get_current_user)):
    service = get_service()
    if service.store.get_course(course_id) is None:
        raise HTTPException(status_code=404, detail=f"Курс '{course_id}' не найден")
    mid = service.store.add_module(course_id, req)
    service.store.add_log(f"Добавлен модуль «{req.title}» в курс #{course_id}",
                          username=current_user.username, category="course")
    return service.store.get_module(mid)


@router.delete("/courses/{course_id}/modules/{module_id}",
               dependencies=[Depends(require_permission("manage_courses"))])
def remove_module(course_id: int, module_id: int,
                  current_user: Principal = Depends(get_current_user)):
    service = get_service()
    m = service.store.get_module(module_id)
    if m is None or int(m["course_id"]) != course_id:
        raise HTTPException(status_code=404, detail=f"Модуль '{module_id}' не найден в курсе '{course_id}'")
    service.store.remove_module(module_id)
    return {"ok": True}


@router.post("/practice-tasks", dependencies=[Depends(require_permission("manage_practice_tasks"))])
def create_task(req: TaskCreate, current_user: Principal = Depends(get_current_user)):
    service = get_service()
    tid = service.store.create_task(req)
    service.store.add_log(f"Создано задание «{req.title}»", username=current_user.username, category="task")
    return service.store.get_task(tid)


@router.put("/practice-tasks/{task_id}", dependencies=[Depends(require_permission("manage_practice_tasks"))])
def update_task(task_id: int, req: TaskUpdate,
                current_user: Principal = Depends(get_current_user)):
    service = get_service()
    if service.store.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail=f"Задание '{task_id}' не найдено")
    service.store.update_task(task_id, req)
    return service.store.get_task(task_id)


@router.delete("/practice-tasks/{task_id}", dependencies=[Depends(require_permission("manage_practice_tasks"))])
def delete_task(task_id: int, current_user: Principal = Depends(get_current_user)):
    service = get_service()
    if service.store.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail=f"Задание '{task_id}' не найдено")
    service.store.delete_task(task_id)
    service.store.add_log(f"Удалено задание #{task_id}", username=current_user.username, category="task")
    return {"ok": True}
