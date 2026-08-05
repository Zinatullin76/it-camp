"""
session.py
==========
Training session domain model (Training Layer, Principle #7).

A TrainingSession wraps a single run of a scenario by one operator:
  session lifecycle  CREATED -> RUNNING -> COMPLETED / ABORTED
  events log         every fault, operator action, alarm and key transition
  evaluation         performance score + qualification grade after the run

Full evaluation logic (scoring rules, qualification report generation) is
implemented in the Training Layer (Этап 7); this module defines the contract.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"


class SessionEvent(BaseModel):
    """One recorded event within a training session."""

    kind: str                       # START, SCENARIO, FAULT, ACTION, ALARM, END
    timestamp: float
    detail: Dict[str, Any] = Field(default_factory=dict)


class TrainingSession(BaseModel):
    """A single operator training run over one scenario."""

    session_id: str
    scenario_id: str
    operator_id: str
    status: SessionStatus = SessionStatus.CREATED
    started_at: float = 0.0
    finished_at: Optional[float] = None
    events: List[SessionEvent] = Field(default_factory=list)
    performance_score: Optional[float] = None
    qualification: str = ""          # ОТЛИЧНО / ХОРОШО / УДОВЛ. / НЕ СДАНО

    def start(self, at: float) -> None:
        """Transition to RUNNING and record the start event."""
        self.status = SessionStatus.RUNNING
        self.started_at = at
        self.events.append(SessionEvent(kind="START", timestamp=at))

    def record(self, kind: str, at: float, **detail: Any) -> None:
        """Append an event to the session log."""
        self.events.append(SessionEvent(kind=kind, timestamp=at, detail=dict(detail)))

    def finish(self, at: float, score: float, qualification: str = "") -> None:
        """Mark the session COMPLETED with a score and optional grade."""
        self.status = SessionStatus.COMPLETED
        self.finished_at = at
        self.performance_score = max(0.0, min(100.0, score))
        self.qualification = qualification
        self.events.append(SessionEvent(kind="END", timestamp=at,
                                        detail={"score": self.performance_score,
                                                "qualification": qualification}))

    def abort(self, at: float, reason: str = "") -> None:
        """Abort the session (operator request or unrecoverable failure)."""
        self.status = SessionStatus.ABORTED
        self.finished_at = at
        self.events.append(SessionEvent(kind="END", timestamp=at,
                                        detail={"reason": reason}))
