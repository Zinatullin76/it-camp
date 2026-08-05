from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class ScenarioEvent(BaseModel):
    timestamp: float
    event_type: str
    target_id: str
    parameters: Dict[str, Any]

class Scenario(BaseModel):
    id: str
    name: str
    description: str
    initial_state: Dict[str, Any] = Field(default_factory=dict)
    events: List[ScenarioEvent] = Field(default_factory=list)
    start_conditions: Dict[str, Any] = Field(default_factory=dict)
    end_conditions: Dict[str, Any] = Field(default_factory=dict)
    success_criteria: Dict[str, Any] = Field(default_factory=dict)
    failure_criteria: Dict[str, Any] = Field(default_factory=dict)
    reference_actions: List[Dict[str, Any]] = Field(default_factory=list)
