"""
lms/models.py
=============
Pydantic contracts for the LMS (learning management) layer of the КТК.

The LMS layer adds the training-program structure required by «Визуал.txt»
on top of the existing simulator:

    groups            -> instructor-managed study groups of operators
    courses           -> training programs (Теория -> Практика -> Экзамен)
    course_modules    -> building blocks of a course
    competencies      -> professional skill catalogue (map of competencies)
    practice_tasks    -> library of practical tasks bound to scenarios
    user_progress     -> per-user status inside course modules
    user_competencies -> per-user skill levels (0..100)
    notifications     -> user-facing feed
    system_log        -> administrator journal
    settings          -> key/value system settings
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CourseStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class ModuleKind(str, Enum):
    THEORY = "theory"
    PRACTICE = "practice"
    EXAM = "exam"


class ModuleStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class Difficulty(str, Enum):
    EASY = "EASY"
    MIDDLE = "MIDDLE"
    HARD = "HARD"


class TaskCategory(str, Enum):
    PRACTICE = "practice"
    EXAM = "exam"
    RANDOM = "random"


class CourseModule(BaseModel):
    """One building block of a course: theory / practice / exam."""

    id: Optional[int] = None
    course_id: int
    kind: ModuleKind
    title: str
    description: str = ""
    seq: int = 0
    content: str = ""
    scenario_id: Optional[str] = None
    practice_task_id: Optional[int] = None


class Course(BaseModel):
    id: Optional[int] = None
    title: str
    description: str = ""
    status: CourseStatus = CourseStatus.DRAFT
    created_at: float = 0.0


class Competency(BaseModel):
    code: str
    title: str
    description: str = ""


class PracticeTask(BaseModel):
    id: Optional[int] = None
    title: str
    description: str = ""
    scenario_id: str
    category: TaskCategory = TaskCategory.PRACTICE
    difficulty: Difficulty = Difficulty.MIDDLE
    duration_min: int = 10
    required_competencies: List[str] = Field(default_factory=list)
    is_random: bool = False
    enabled: bool = True
    scenario_name: str = ""
    is_ready: bool = True
    readiness_percent: float = 100.0


class UserCompetency(BaseModel):
    user_id: int
    competency_code: str
    level_percent: float = 0.0
    updated_at: float = 0.0
    competency_title: str = ""


class UserProgress(BaseModel):
    user_id: int
    module_id: int
    status: ModuleStatus = ModuleStatus.NOT_STARTED
    score: Optional[float] = None
    attempts: int = 0
    completed_at: Optional[float] = None
    last_practice_session_id: Optional[str] = None


class StudyGroup(BaseModel):
    id: Optional[int] = None
    name: str
    description: str = ""
    course_id: Optional[int] = None
    course_title: str = ""
    instructor_id: Optional[int] = None
    created_at: float = 0.0
    member_count: int = 0


class GroupMember(BaseModel):
    group_id: int
    user_id: int
    username: str = ""
    full_name: str = ""
    role_codes: List[str] = Field(default_factory=list)


class Notification(BaseModel):
    id: int
    user_id: int
    text: str
    kind: str = "info"
    is_read: bool = False
    created_at: float = 0.0


class SystemLogEntry(BaseModel):
    id: int
    timestamp: float = 0.0
    level: str = "INFO"
    username: str = ""
    message: str = ""
    category: str = "system"


# ---------------------------------------------------------------------------
# View models returned by the API
# ---------------------------------------------------------------------------


class MasteryView(BaseModel):
    index: float = 0.0
    stage_index: int = 0
    stage: str = "Стажер"
    stages: List[str] = Field(default_factory=list)
    next_stage: Optional[str] = None
    to_next: float = 0.0


class ModuleView(BaseModel):
    id: int
    kind: ModuleKind
    title: str
    description: str = ""
    seq: int = 0
    content: str = ""
    scenario_id: Optional[str] = None
    practice_task_id: Optional[int] = None
    status: ModuleStatus = ModuleStatus.NOT_STARTED
    score: Optional[float] = None
    attempts: int = 0
    percent: float = 0.0
    practice_title: str = ""


class CourseView(BaseModel):
    id: int
    title: str
    description: str = ""
    status: CourseStatus = CourseStatus.DRAFT
    progress_percent: float = 0.0
    modules: List[ModuleView] = Field(default_factory=list)


class CompetencyView(BaseModel):
    code: str
    title: str
    description: str = ""
    level_percent: float = 0.0


class HistoryRow(BaseModel):
    session_id: str
    scenario_id: str
    scenario_name: str = ""
    task_title: str = ""
    operator_id: str = ""
    status: str = ""
    performance_score: Optional[float] = None
    qualification: str = ""
    sim_start: float = 0.0
    sim_end: Optional[float] = None
    wall_start: float = 0.0
    wall_end: Optional[float] = None
    duration_s: Optional[float] = None


class Recommendation(BaseModel):
    kind: str
    text: str
    module_id: Optional[int] = None
    task_id: Optional[int] = None


class DashboardView(BaseModel):
    username: str
    full_name: str
    mastery: MasteryView
    current_course: Optional[CourseView] = None
    nearest_module: Optional[ModuleView] = None
    nearest_exam: Optional[ModuleView] = None
    recent_practices: List[HistoryRow] = Field(default_factory=list)
    recommendations: List[Recommendation] = Field(default_factory=list)
    competencies: List[CompetencyView] = Field(default_factory=list)
    notifications: List[Notification] = Field(default_factory=list)


class DebriefStep(BaseModel):
    seq: int
    kind: str = "action"
    timestamp: float = 0.0
    equipment_id: str = ""
    action_type: str = ""
    description: str = ""
    status: str = "ok"
    detail: str = ""


class DebriefError(BaseModel):
    rule_error_type: str
    severity: str = ""
    expected_action: str = ""
    cause: str = ""
    consequence: str = ""
    timestamp: float = 0.0


class DebriefView(BaseModel):
    session_id: str
    task_title: str
    scenario_id: str
    scenario_name: str
    operator_id: str
    performance_score: float = 0.0
    qualification: str = ""
    duration_s: float = 0.0
    sim_start: float = 0.0
    sim_end: float = 0.0
    steps: List[DebriefStep] = Field(default_factory=list)
    alarms: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[DebriefError] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    competency_delta: List[Dict[str, Any]] = Field(default_factory=list)


class GroupMemberProgress(BaseModel):
    user_id: int
    username: str
    full_name: str = ""
    course_progress: float = 0.0
    mastery: float = 0.0
    stage: str = ""
    competencies: List[CompetencyView] = Field(default_factory=list)
    last_session: Optional[HistoryRow] = None


class GroupView(BaseModel):
    group: StudyGroup
    course: Optional[CourseView] = None
    members: List[GroupMemberProgress] = Field(default_factory=list)


class AnalyticsView(BaseModel):
    avg_score: float = 0.0
    total_sessions: int = 0
    completed_sessions: int = 0
    avg_duration_s: float = 0.0
    group_rating: List[Dict[str, Any]] = Field(default_factory=list)
    frequent_errors: List[Dict[str, Any]] = Field(default_factory=list)
    competency_distribution: List[Dict[str, Any]] = Field(default_factory=list)
    learning_dynamics: List[Dict[str, Any]] = Field(default_factory=list)
    status_distribution: List[Dict[str, Any]] = Field(default_factory=list)


class MonitorOperatorView(BaseModel):
    username: str
    full_name: str = ""
    session_id: str = ""
    scenario_id: str = ""
    scenario_name: str = ""
    status: str = ""
    sim_time: float = 0.0
    performance_score: Optional[float] = None
    alarms: List[Dict[str, Any]] = Field(default_factory=list)
    actions_count: int = 0
    errors_count: int = 0
    last_action: Optional[Dict[str, Any]] = None
    is_system: bool = False


class SettingsView(BaseModel):
    key: str
    value: str


class ProfileView(BaseModel):
    username: str
    full_name: str = ""
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    created_at: float = 0.0
    mastery: MasteryView
    competencies: List[CompetencyView] = Field(default_factory=list)
    total_sessions: int = 0
    avg_score: float = 0.0


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class GroupCreate(BaseModel):
    name: str
    description: str = ""
    course_id: Optional[int] = None


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    course_id: Optional[int] = None


class GroupMembersRequest(BaseModel):
    user_ids: List[int] = Field(default_factory=list)


class CourseCreate(BaseModel):
    title: str
    description: str = ""
    status: CourseStatus = CourseStatus.DRAFT


class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[CourseStatus] = None


class ModuleCreate(BaseModel):
    kind: ModuleKind
    title: str
    description: str = ""
    content: str = ""
    scenario_id: Optional[str] = None
    practice_task_id: Optional[int] = None


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    scenario_id: str
    category: TaskCategory = TaskCategory.PRACTICE
    difficulty: Difficulty = Difficulty.MIDDLE
    duration_min: int = 10
    required_competencies: List[str] = Field(default_factory=list)
    is_random: bool = False
    enabled: bool = True


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    scenario_id: Optional[str] = None
    category: Optional[TaskCategory] = None
    difficulty: Optional[Difficulty] = None
    duration_min: Optional[int] = None
    required_competencies: Optional[List[str]] = None
    is_random: Optional[bool] = None
    enabled: Optional[bool] = None


class SettingsUpdate(BaseModel):
    values: Dict[str, str] = Field(default_factory=dict)
