"""
lms/content_models.py
=====================
Pydantic contracts of the authoring & study system (по «Обуч.txt»).

The system lets an instructor build a learning module without a programmer:

    Course -> Module -> Lesson(Теория) -> Test(Question) -> Task -> Scenario
                        -> Assessment -> Competency

Content is stored in SQLite (see lms/content_store.py) and served through
REST API (see lms/content_api.py). The frontend never embeds content; it
only renders what the API returns.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class LessonBlockKind(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    SCHEME = "scheme"
    VIDEO = "video"
    EQUIPMENT_CARD = "equipment_card"
    SCHEME_HIGHLIGHT = "scheme_highlight"
    INTERACTIVE_SCHEME = "interactive_scheme"


class LessonBlock(BaseModel):
    kind: LessonBlockKind
    title: str = ""
    content: str = ""
    url: str = ""
    node_id: str = ""


class Lesson(BaseModel):
    id: Optional[int] = None
    module_id: int
    title: str
    seq: int = 0
    blocks: List[LessonBlock] = Field(default_factory=list)
    equipment_ids: List[str] = Field(default_factory=list)
    competency_codes: List[str] = Field(default_factory=list)
    created_at: float = 0.0


class QuestionKind(str, Enum):
    SINGLE = "single"
    MULTI = "multi"
    MATCH = "match"
    SEQUENCE = "sequence"
    OBJECT = "object"


class Question(BaseModel):
    id: Optional[int] = None
    test_id: Optional[int] = None
    kind: QuestionKind
    title: str
    text: str = ""
    seq: int = 0
    options: List[Dict[str, Any]] = Field(default_factory=list)
    answer: Any = None
    max_score: float = 1.0
    penalty: float = 0.0
    required: bool = True
    hint: str = ""


class TestConfig(BaseModel):
    id: Optional[int] = None
    module_id: int
    title: str = "Контроль знаний"
    passing_score: float = 70.0
    attempts: int = 0
    retry_required: bool = False
    shuffle: bool = False
    competency_codes: List[str] = Field(default_factory=list)
    questions: List[Question] = Field(default_factory=list)


class TaskCondition(BaseModel):
    object_id: str
    attribute: str
    relation: str = "=="
    value: Any = None
    value2: Any = None


class RestrictionRule(BaseModel):
    action_type: str = ""
    object_id: str = ""
    relation: str = ""
    value: Any = None
    severity: str = "warning"
    message: str = ""


class Criterion(BaseModel):
    key: str
    title: str
    weight: float = 1.0


class ExpectedAction(BaseModel):
    seq: int = 0
    object_id: str = ""
    action_type: str = ""
    value: Any = None
    description: str = ""
    deadline_t: Optional[float] = None
    weight: float = 1.0


class TrainingTask(BaseModel):
    id: Optional[int] = None
    module_id: int
    title: str
    goal: str = ""
    scenario_id: str = ""
    duration_min: int = 10
    initial_state: Dict[str, Any] = Field(default_factory=dict)
    target_state: List[TaskCondition] = Field(default_factory=list)
    restrictions: List[RestrictionRule] = Field(default_factory=list)
    criteria: List[Criterion] = Field(default_factory=list)
    expected_actions: List[ExpectedAction] = Field(default_factory=list)
    critical_errors: List[RestrictionRule] = Field(default_factory=list)
    competency_codes: List[str] = Field(default_factory=list)
    equipment_ids: List[str] = Field(default_factory=list)
    enabled: bool = True
    created_at: float = 0.0


class ScenarioStatus(str, Enum):
    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class ScenarioEventDef(BaseModel):
    time: float = 0.0
    event_type: str = "fault"
    object_id: str = ""
    param: str = ""
    value: Any = None
    severity: str = "warning"
    message: str = ""


class ScenarioDefinition(BaseModel):
    id: Optional[int] = None
    module_id: int
    title: str
    description: str = ""
    goal: str = ""
    status: ScenarioStatus = ScenarioStatus.DRAFT
    initial_state: Dict[str, Any] = Field(default_factory=dict)
    events: List[ScenarioEventDef] = Field(default_factory=list)
    expected_actions: List[ExpectedAction] = Field(default_factory=list)
    success_criteria: List[Criterion] = Field(default_factory=list)
    critical_errors: List[RestrictionRule] = Field(default_factory=list)
    final_state: Dict[str, Any] = Field(default_factory=dict)
    competency_codes: List[str] = Field(default_factory=list)
    equipment_ids: List[str] = Field(default_factory=list)
    duration_min: int = 10
    is_exam: bool = False
    created_at: float = 0.0


class AssessmentKind(str, Enum):
    TEST = "test"
    PRACTICE = "practice"
    EXAM = "exam"


class Assessment(BaseModel):
    id: Optional[int] = None
    user_id: int
    module_id: int
    kind: AssessmentKind = AssessmentKind.TEST
    test_id: Optional[int] = None
    task_id: Optional[int] = None
    scenario_id: Optional[str] = None
    score: float = 0.0
    max_score: float = 100.0
    passed: bool = False
    criteria_scores: Dict[str, Any] = Field(default_factory=dict)
    errors_count: int = 0
    critical_errors_count: int = 0
    duration_s: float = 0.0
    answers: Any = None
    feedback_good: List[str] = Field(default_factory=list)
    feedback_bad: List[str] = Field(default_factory=list)
    session_id: Optional[str] = None
    started_at: float = 0.0
    finished_at: float = 0.0
    created_at: float = 0.0


class AssessmentView(Assessment):
    username: str = ""
    full_name: str = ""
    module_title: str = ""
    task_title: str = ""
    scenario_title: str = ""


class ActionLogEntry(BaseModel):
    id: int = 0
    timestamp: float = 0.0
    user_id: Optional[int] = None
    username: str = ""
    object_id: str = ""
    object_name: str = ""
    action: str = ""
    old_state: Any = None
    new_state: Any = None
    source: str = "operator_panel"
    session_id: Optional[str] = None
    module_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class LessonWrite(BaseModel):
    title: str
    blocks: List[LessonBlock] = Field(default_factory=list)
    equipment_ids: List[str] = Field(default_factory=list)
    competency_codes: List[str] = Field(default_factory=list)


class TestWrite(BaseModel):
    title: str = "Контроль знаний"
    passing_score: float = 70.0
    attempts: int = 0
    retry_required: bool = False
    shuffle: bool = False
    competency_codes: List[str] = Field(default_factory=list)


class QuestionWrite(BaseModel):
    kind: QuestionKind
    title: str
    text: str = ""
    options: List[Dict[str, Any]] = Field(default_factory=list)
    answer: Any = None
    max_score: float = 1.0
    penalty: float = 0.0
    required: bool = True
    hint: str = ""


class TaskWrite(BaseModel):
    title: str
    goal: str = ""
    scenario_id: str = ""
    duration_min: int = 10
    initial_state: Dict[str, Any] = Field(default_factory=dict)
    target_state: List[TaskCondition] = Field(default_factory=list)
    restrictions: List[RestrictionRule] = Field(default_factory=list)
    criteria: List[Criterion] = Field(default_factory=list)
    expected_actions: List[ExpectedAction] = Field(default_factory=list)
    critical_errors: List[RestrictionRule] = Field(default_factory=list)
    competency_codes: List[str] = Field(default_factory=list)
    equipment_ids: List[str] = Field(default_factory=list)
    enabled: bool = True


class ScenarioWrite(BaseModel):
    title: str
    description: str = ""
    goal: str = ""
    initial_state: Dict[str, Any] = Field(default_factory=dict)
    events: List[ScenarioEventDef] = Field(default_factory=list)
    expected_actions: List[ExpectedAction] = Field(default_factory=list)
    success_criteria: List[Criterion] = Field(default_factory=list)
    critical_errors: List[RestrictionRule] = Field(default_factory=list)
    final_state: Dict[str, Any] = Field(default_factory=dict)
    competency_codes: List[str] = Field(default_factory=list)
    equipment_ids: List[str] = Field(default_factory=list)
    duration_min: int = 10
    is_exam: bool = False


class StatusWrite(BaseModel):
    status: ScenarioStatus


class TestSubmit(BaseModel):
    answers: Dict[str, Any] = Field(default_factory=dict)
    duration_s: float = 0.0


class TaskStart(BaseModel):
    pass


class ModuleStudy(BaseModel):
    """Payload returned to the operator: только опубликованный контент."""
    module: Dict[str, Any]
    lessons: List[Lesson]
    test: Optional[TestConfig] = None
    task: Optional[TrainingTask] = None
    scenario: Optional[ScenarioDefinition] = None
    equipment: List[Dict[str, Any]] = Field(default_factory=list)
    competencies: List[Dict[str, Any]] = Field(default_factory=list)


class PublishWrite(BaseModel):
    published: bool = True
