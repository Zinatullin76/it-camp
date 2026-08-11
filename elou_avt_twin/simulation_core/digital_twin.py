"""
digital_twin.py
===============
DigitalTwin — the public API facade for the ELOU-AVT simulation core.

This class provides the high-level interface that the KTK (training
simulator complex) front-end or a C#/.NET host application interacts with.

Public API:
    create_simulation()
    load_scenario(scenario_id)
    reset()
    start()
    pause()
    stop()
    step(dt)
    apply_operator_action(action)
    inject_failure(equipment_id, failure_mode)
    get_state()
    get_history()
    get_alarms()
    get_events()
    get_score_data()
"""

import copy
import json
import logging
import random
import time
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

from models.base import (
    SimulationState,
    SimulationConfig,
    OperatorAction,
    Alarm,
    ErrorEvent,
    Severity,
)
from models.scenario import Scenario
from events.error_tracker import ExpectedAction
from simulation_core.engine import SimulationEngine
from scenarios.scenario_registry import SCENARIO_REGISTRY

logger = logging.getLogger("elou_avt.digital_twin")


class SimulationStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class DigitalTwin:
    """
    Digital twin facade for the ELOU-AVT training simulator.

    Encapsulates the SimulationEngine and provides a clean, stable
    public API suitable for integration with a C#/.NET desktop application
    via REST API or local IPC.

    Example usage:
        config = SimulationConfig(dt=1.0, random_seed=42)
        twin = DigitalTwin(config)
        twin.load_scenario("PUMP_FAILURE_001")
        twin.start()
        state = twin.step(dt=1.0)
        twin.apply_operator_action(action)
        alarms = twin.get_alarms()
    """

    def __init__(self, config: Optional[SimulationConfig] = None):
        self._config = config or SimulationConfig()
        self._engine: Optional[SimulationEngine] = None
        self._scenario: Optional[Scenario] = None
        self._status = SimulationStatus.IDLE
        self._simulation_time = 0.0
        self._wall_clock_start: Optional[float] = None
        self._pending_actions: List[OperatorAction] = []

        # Determinism: seed numpy and random
        random.seed(self._config.random_seed)
        try:
            import numpy as np
            np.random.seed(self._config.random_seed)
        except ImportError:
            pass

        self._setup_logging()
        logger.info("DigitalTwin initialized. Config: dt=%.2f, seed=%d",
                    self._config.dt, self._config.random_seed)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def create_simulation(self) -> None:
        """Initialize or re-initialize the simulation engine."""
        self._engine = SimulationEngine(self._config)
        self._simulation_time = 0.0
        self._status = SimulationStatus.IDLE
        logger.info("Simulation created.")

    def load_scenario(self, scenario_id: str) -> None:
        """
        Load a training scenario by ID.

        Parameters:
            scenario_id : scenario identifier (e.g. "PUMP_FAILURE_001")

        Raises:
            ValueError if scenario not found
        """
        if scenario_id not in SCENARIO_REGISTRY:
            raise ValueError(f"Scenario '{scenario_id}' not found. "
                             f"Available: {list(SCENARIO_REGISTRY.keys())}")
        self._scenario = SCENARIO_REGISTRY[scenario_id]
        if self._engine is None:
            self.create_simulation()
        self._apply_initial_state(self._scenario.initial_state)
        self._register_reference_actions(self._scenario.reference_actions)
        logger.info("Scenario loaded: %s — %s", scenario_id, self._scenario.name)

    def load_scenario_object(self, scenario: Scenario) -> None:
        """Load a scenario definition built at runtime (e.g. from the LMS
        authoring system, «Обуч.txt») instead of the static registry."""
        if self._engine is None:
            self.create_simulation()
        self._scenario = scenario
        self._apply_initial_state(scenario.initial_state)
        self._register_reference_actions(scenario.reference_actions)
        logger.info("Scenario object loaded: %s — %s", scenario.id, scenario.name)

    def _register_reference_actions(self, actions: List[Dict[str, Any]]) -> None:
        """Arm online error checks from the scenario's reference plan."""
        if self._engine is None:
            return
        for item in actions:
            equipment_id = item.get("equipment") or item.get("equipment_id") or item.get("object_id")
            action_type = item.get("action") or item.get("action_type")
            if not equipment_id or not action_type:
                continue
            deadline = item.get("deadline_t", item.get("t"))
            if deadline is None:
                continue
            self._engine.register_expected_action(ExpectedAction(
                equipment_id=str(equipment_id),
                action_type=str(action_type),
                attribute=str(item.get("attribute", "")),
                value=None if item.get("value") in (None, "") else item.get("value"),
                deadline=float(deadline),
                description=str(item.get("description", "")),
                consequence=str(
                    item.get("consequence")
                    or "Невыполнение обязательного шага нарушает регламент сценария."
                ),
            ))

    def _apply_initial_state(self, initial_state: Dict[str, Any]) -> None:
        """Apply scenario initial conditions to equipment.

        Keys like '<id>_running' / '<id>_position' / '<id>_fuel_flow' target a
        specific equipment instance. If that id does not exist in the current
        scheme (e.g. a different P&ID layout), the action falls back to the
        first equipment of the same type in topological order, so scenarios
        also work on custom schemes.
        """
        if self._engine is None:
            return
        from equipment import Pump, Valve, Heater

        fallback_types: Dict[str, str] = {}

        def type_for(key: str) -> Optional[str]:
            if "_running" in key:
                return "pump"
            if "_position" in key:
                return "valve"
            if "_fuel_flow" in key:
                return "heater"
            return None

        def class_for(ntype: str):
            return {"pump": Pump, "valve": Valve, "angle_valve": Valve, "heater": Heater}.get(ntype)

        def has_explicit_initial(eq, key: str) -> bool:
            """True when the scheme node already carries an explicit initial_*
            value for the scenario key, so saved slider positions win over the
            scenario's demo defaults on reload."""
            params = getattr(eq, "params", None) or {}
            if "_running" in key:
                return "initial_running" in params
            if "_position" in key:
                return "initial_position" in params or "valve_position" in params
            if "_fuel_flow" in key:
                return "initial_fuel_flow" in params
            return False

        for key, value in initial_state.items():
            base = key.replace("_running", "").replace("_position", "").replace("_fuel_flow", "")
            # Only resolve against equipment that is actually present in the
            # current scheme; otherwise the stale demo equipment would shadow it.
            eq = (self._engine._equipment.get(base)
                  if base in self._engine._node_map else None)
            ntype = type_for(key)
            if eq is None and ntype:
                # Fallback: apply to the first equipment of the same type in the
                # current scheme (once per type) instead of stale default items.
                if fallback_types.get(ntype) == base:
                    continue
                eq = next((e for eid, e in self._engine._equipment.items()
                           if eid in self._engine._node_map
                           and isinstance(e, class_for(ntype))), None)
                if eq is not None:
                    fallback_types[ntype] = base
            if eq is None:
                continue
            if has_explicit_initial(eq, key):
                continue
            if "_running" in key:
                eq.apply_action("TURN_ON" if value else "TURN_OFF")
            elif "_position" in key:
                eq.apply_action("SET_VALUE", float(value))
            elif "_fuel_flow" in key:
                eq.apply_action("SET_VALUE", float(value))

    def reset(self) -> None:
        """Reset simulation to initial state."""
        if self._engine:
            self._engine.reset()
        self._simulation_time = 0.0
        self._status = SimulationStatus.IDLE
        self._pending_actions.clear()
        if self._scenario:
            self._apply_initial_state(self._scenario.initial_state)
        logger.info("Simulation reset.")

    def start(self) -> None:
        """Start or resume the simulation."""
        if self._engine is None:
            self.create_simulation()
        self._status = SimulationStatus.RUNNING
        self._wall_clock_start = time.time()
        logger.info("Simulation started.")

    def pause(self) -> None:
        """Pause the simulation."""
        self._status = SimulationStatus.PAUSED
        logger.info("Simulation paused at t=%.2f s", self._simulation_time)

    def stop(self) -> None:
        """Stop the simulation."""
        self._status = SimulationStatus.STOPPED
        logger.info("Simulation stopped at t=%.2f s", self._simulation_time)

    # ------------------------------------------------------------------
    # Stepping
    # ------------------------------------------------------------------

    def step(self, dt: Optional[float] = None) -> SimulationState:
        """
        Advance simulation by dt seconds.

        Parameters:
            dt : time step [s], defaults to config.dt

        Returns:
            new SimulationState

        Raises:
            RuntimeError if simulation is not running
        """
        if self._status not in (SimulationStatus.RUNNING, SimulationStatus.IDLE):
            raise RuntimeError(f"Cannot step: simulation status is {self._status}")

        if self._engine is None:
            self.create_simulation()

        dt = dt if dt is not None else self._config.dt
        self._simulation_time += dt

        # Process scenario events scheduled for this time
        if self._scenario:
            self._engine.process_scenario_events(self._scenario.events)

        # Collect pending actions
        actions = list(self._pending_actions)
        self._pending_actions.clear()

        # Advance engine
        current_state = self._engine.get_current_state()
        new_state = self._engine.step(
            state=current_state,
            operator_actions=actions,
            dt=dt,
        )

        logger.debug("Step t=%.2f: feed_flow=%.4f, col_P=%.0f Pa, col_T=%.1f K",
                     self._simulation_time,
                     new_state.feed_flow,
                     new_state.pressure.get("column", 0.0),
                     new_state.temperature.get("column", 0.0))

        return new_state

    # ------------------------------------------------------------------
    # Operator interaction
    # ------------------------------------------------------------------

    def apply_operator_action(self, action: OperatorAction) -> None:
        """
        Queue an operator action to be applied on the next step.

        Parameters:
            action : OperatorAction object
        """
        self._pending_actions.append(action)
        logger.info("Action queued: %s on %s = %s",
                    action.action_type, action.equipment_id, action.new_value)

    def inject_failure(self, equipment_id: str, failure_mode: str) -> None:
        """
        Inject a failure into a specific equipment.

        Parameters:
            equipment_id : equipment identifier
            failure_mode : failure mode string
        """
        if self._engine:
            self._engine.inject_failure(equipment_id, failure_mode)

    # ------------------------------------------------------------------
    # State and data accessors
    # ------------------------------------------------------------------

    def get_state(self) -> SimulationState:
        """Return the current simulation state."""
        if self._engine is None:
            return SimulationState()
        return self._engine.get_current_state()

    def get_history(self) -> List[SimulationState]:
        """Return the full simulation state history."""
        if self._engine is None:
            return []
        return self._engine.get_history()

    def get_alarms(self) -> List[Alarm]:
        """Return currently active alarms."""
        if self._engine is None:
            return []
        return self._engine.get_alarms()

    def get_events(self) -> List[ErrorEvent]:
        """Return all recorded operator error events."""
        if self._engine is None:
            return []
        return self._engine.get_events()

    def get_score_data(self) -> Dict[str, Any]:
        """
        Return structured data for scoring and AI analysis.

        Returns a dict containing:
          - simulation_time
          - scenario_id
          - operator_actions (log)
          - error_events
          - alarm_history
          - final_state summary
          - performance_metrics
        """
        if self._engine is None:
            return {}

        state = self._engine.get_current_state()
        events = self._engine.get_events()
        alarms = self._engine._alarm_system.get_alarm_history()
        action_log = self._engine._error_tracker.get_action_log()

        critical_alarms = [a for a in alarms if a.severity == Severity.CRITICAL]
        wrong_actions = [e for e in events if e.error_type == "WRONG_ACTION"]
        missed_actions = [e for e in events if e.error_type == "MISSED_ACTION"]

        score = max(0, 100
                    - len(critical_alarms) * 10
                    - len(wrong_actions) * 5
                    - len(missed_actions) * 15)

        return {
            "simulation_time":    self._simulation_time,
            "scenario_id":        self._scenario.id if self._scenario else None,
            "scenario_name":      self._scenario.name if self._scenario else None,
            "operator_actions":   [a.model_dump() for a in action_log],
            "error_events":       [e.model_dump() for e in events],
            "alarm_history":      [a.model_dump() for a in alarms],
            "critical_alarm_count": len(critical_alarms),
            "wrong_action_count": len(wrong_actions),
            "missed_action_count": len(missed_actions),
            "final_state": {
                "feed_flow":    state.feed_flow,
                "pressure":     state.pressure,
                "temperature":  state.temperature,
                "level":        state.level,
                "active_failures": state.active_failures,
            },
            "performance_score": score,
            "status": self._status.value,
        }

    # ------------------------------------------------------------------
    # Configuration loading
    # ------------------------------------------------------------------

    @classmethod
    def from_config_file(cls, path: str) -> "DigitalTwin":
        """
        Create a DigitalTwin from a JSON configuration file.

        Parameters:
            path : path to JSON config file

        Returns:
            DigitalTwin instance
        """
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        config = SimulationConfig(**data)
        return cls(config)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def status(self) -> SimulationStatus:
        return self._status

    @property
    def simulation_time(self) -> float:
        return self._simulation_time

    @property
    def scenario(self) -> Optional[Scenario]:
        return self._scenario

    # ------------------------------------------------------------------
    # Logging setup
    # ------------------------------------------------------------------

    @staticmethod
    def _setup_logging() -> None:
        if not logging.getLogger("elou_avt").handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            ))
            logging.getLogger("elou_avt").addHandler(handler)
            logging.getLogger("elou_avt").setLevel(logging.INFO)
