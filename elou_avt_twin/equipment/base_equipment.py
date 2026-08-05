"""
base_equipment.py
=================
Abstract base class for all process equipment.
Follows the Open/Closed Principle: new equipment types extend this
without modifying the simulation engine.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class EquipmentState:
    """Generic equipment state container."""
    running: bool = True
    failed: bool = False
    failure_mode: Optional[str] = None
    degradation: float = 0.0  # 0.0 = healthy, 1.0 = fully degraded
    extra: Dict[str, Any] = field(default_factory=dict)


class BaseEquipment(ABC):
    """
    Abstract base for all equipment.
    Each subclass must implement:
      - step(dt, **inputs) -> dict of output values
      - get_state() -> EquipmentState
      - apply_action(action_type, value)
    """

    def __init__(self, equipment_id: str, params: Dict[str, Any]):
        self.equipment_id = equipment_id
        self.params = params
        self.state = EquipmentState()

    @abstractmethod
    def step(self, dt: float, **inputs) -> Dict[str, Any]:
        """Advance equipment state by dt seconds."""
        ...

    @abstractmethod
    def get_state(self) -> EquipmentState:
        """Return current equipment state."""
        ...

    @abstractmethod
    def apply_action(self, action_type: str, value: Optional[float] = None) -> None:
        """Apply an operator action to this equipment."""
        ...

    def inject_failure(self, failure_mode: str) -> None:
        """Inject a failure into this equipment."""
        self.state.failed = True
        self.state.failure_mode = failure_mode

    def update_params(self, updates: Dict[str, Any]) -> None:
        """Apply physical-property corrections to the live equipment.

        Writes the new values into ``self.params`` and refreshes the cached
        instance attributes without disturbing dynamic (operational) state
        such as valve position, tank level or fuel flow.
        """
        self.params.update(updates)
        self._apply_params()

    def _apply_params(self) -> None:
        """Re-read physical properties from ``self.params`` into attributes."""
        pass

    def reset(self) -> None:
        """Reset equipment to healthy initial state."""
        self.state = EquipmentState()
