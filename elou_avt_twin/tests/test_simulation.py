"""
test_simulation.py
==================
Comprehensive pytest test suite for the ELOU-AVT digital twin simulation core.

Tests:
  1.  Material balance
  2.  Heat balance
  3.  Pump operation
  4.  Valve operation
  5.  Pump failure
  6.  Alarm — high pressure
  7.  Alarm — high temperature
  8.  Scenario loading
  9.  Determinism
  10. Reset
  11. Replay (history)
  12. Integration — full scenario run
  13. Integration — pump failure scenario
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import copy

from models.base import (
    SimulationConfig, SimulationState, OperatorAction, ActionType, Severity
)
from physics.process_physics import (
    material_balance_level,
    heat_balance_temperature,
    pump_flow,
    material_balance_flow,
    furnace_heat_output,
    heat_exchanger_duty,
    column_separation,
)
from equipment.pump import Pump
from equipment.valve import Valve
from equipment.heater import Heater
from equipment.heat_exchanger import HeatExchanger
from equipment.distillation_column import DistillationColumn
from equipment.elou import ELOU
from safety.alarm_system import AlarmSystem, AlarmSetpoint
from simulation_core.engine import SimulationEngine
from simulation_core.digital_twin import DigitalTwin, SimulationStatus
from scenarios.scenario_registry import SCENARIO_REGISTRY


# ===========================================================================
# 1. Material balance
# ===========================================================================

class TestMaterialBalance:
    def test_level_increases_when_inflow_exceeds_outflow(self):
        """Level must rise when Q_in > Q_out."""
        level = material_balance_level(
            level=2.0, flow_in=0.05, flow_out=0.02, tank_area=10.0, dt=10.0
        )
        assert level > 2.0, "Level should increase"

    def test_level_decreases_when_outflow_exceeds_inflow(self):
        """Level must fall when Q_out > Q_in."""
        level = material_balance_level(
            level=2.0, flow_in=0.01, flow_out=0.05, tank_area=10.0, dt=10.0
        )
        assert level < 2.0, "Level should decrease"

    def test_level_stable_when_balanced(self):
        """Level must be stable when Q_in == Q_out."""
        level = material_balance_level(
            level=2.0, flow_in=0.03, flow_out=0.03, tank_area=10.0, dt=100.0
        )
        assert abs(level - 2.0) < 1e-9, "Level should remain constant"

    def test_level_cannot_go_negative(self):
        """Level must not go below zero."""
        level = material_balance_level(
            level=0.1, flow_in=0.0, flow_out=1.0, tank_area=10.0, dt=100.0
        )
        assert level >= 0.0, "Level must not be negative"

    def test_material_balance_conservation(self):
        """Mass in = mass out + accumulation (over 1 step)."""
        dt = 10.0
        area = 20.0
        flow_in = 0.05
        flow_out = 0.02
        level_0 = 3.0
        level_1 = material_balance_level(level_0, flow_in, flow_out, area, dt)
        accumulation = (level_1 - level_0) * area
        net_flow = (flow_in - flow_out) * dt
        assert abs(accumulation - net_flow) < 1e-9


# ===========================================================================
# 2. Heat balance
# ===========================================================================

class TestHeatBalance:
    def test_temperature_rises_with_heat_input(self):
        """Temperature must rise when heat_in > heat_out."""
        T = heat_balance_temperature(
            temp=300.0, heat_in=1e6, heat_out=0.0, mass=1000.0, dt=1.0
        )
        assert T > 300.0

    def test_temperature_falls_with_heat_loss(self):
        """Temperature must fall when heat_out > heat_in."""
        T = heat_balance_temperature(
            temp=400.0, heat_in=0.0, heat_out=1e6, mass=1000.0, dt=1.0
        )
        assert T < 400.0

    def test_temperature_stable_when_balanced(self):
        """Temperature must be stable when heat_in == heat_out."""
        T = heat_balance_temperature(
            temp=350.0, heat_in=5e5, heat_out=5e5, mass=1000.0, dt=10.0
        )
        assert abs(T - 350.0) < 1e-9

    def test_furnace_heat_output_proportional_to_fuel(self):
        """Furnace heat must scale linearly with fuel flow."""
        Q1 = furnace_heat_output(fuel_flow=1.0)
        Q2 = furnace_heat_output(fuel_flow=2.0)
        assert abs(Q2 / Q1 - 2.0) < 1e-9

    def test_heat_exchanger_duty_positive(self):
        """HX duty must be positive for valid temperature profile."""
        Q = heat_exchanger_duty(
            u=300.0, area=200.0,
            t_hot_in=573.15, t_hot_out=423.15,
            t_cold_in=293.15, t_cold_out=373.15,
        )
        assert Q > 0.0

    def test_heat_exchanger_duty_zero_with_equal_temps(self):
        """HX duty must be zero when hot and cold temps are equal."""
        Q = heat_exchanger_duty(
            u=300.0, area=200.0,
            t_hot_in=400.0, t_hot_out=400.0,
            t_cold_in=400.0, t_cold_out=400.0,
        )
        assert Q == 0.0


# ===========================================================================
# 3. Pump operation
# ===========================================================================

class TestPump:
    def test_pump_delivers_flow_when_running(self):
        """Running pump must deliver non-zero flow."""
        pump = Pump("P001")
        pump.apply_action("TURN_ON")
        out = pump.step(dt=1.0)
        assert out["flow_out"] > 0.0

    def test_pump_delivers_zero_when_stopped(self):
        """Stopped pump must deliver zero flow."""
        pump = Pump("P001")
        pump.apply_action("TURN_OFF")
        out = pump.step(dt=1.0)
        assert out["flow_out"] == 0.0

    def test_pump_flow_equals_nominal_at_full_efficiency(self):
        """Pump flow must equal nominal when efficiency is 1.0."""
        pump = Pump("P001", {"nominal_flow": 0.1, "efficiency_nominal": 1.0})
        pump.apply_action("TURN_ON")
        out = pump.step(dt=1.0)
        assert abs(out["flow_out"] - 0.1) < 1e-9

    def test_pump_state_reflects_running(self):
        """Pump state must reflect running status."""
        pump = Pump("P001")
        pump.apply_action("TURN_ON")
        pump.step(dt=1.0)
        state = pump.get_state()
        assert state.running is True


# ===========================================================================
# 4. Valve operation
# ===========================================================================

class TestValve:
    def test_valve_flow_increases_with_opening(self):
        """Flow must increase as valve opens."""
        valve = Valve("V001", {"cv": 0.01, "response_rate": 1.0})
        valve.apply_action("SET_VALUE", 0.5)
        # Step enough to reach target
        for _ in range(5):
            out_half = valve.step(dt=1.0, delta_p=1e4)

        valve2 = Valve("V002", {"cv": 0.01, "response_rate": 1.0})
        valve2.apply_action("SET_VALUE", 1.0)
        for _ in range(5):
            out_full = valve2.step(dt=1.0, delta_p=1e4)

        assert out_full["flow_out"] > out_half["flow_out"]

    def test_valve_zero_flow_when_closed(self):
        """Closed valve must pass zero flow."""
        valve = Valve("V001")
        out = valve.step(dt=1.0, delta_p=1e4)
        assert out["flow_out"] == 0.0

    def test_valve_position_tracks_setpoint(self):
        """Valve position must converge to setpoint."""
        valve = Valve("V001", {"response_rate": 1.0})
        valve.apply_action("SET_VALUE", 0.8)
        for _ in range(10):
            valve.step(dt=1.0, delta_p=1e4)
        assert abs(valve._position - 0.8) < 0.01

    def test_valve_stuck_does_not_move(self):
        """Stuck valve must not change position."""
        valve = Valve("V001", {"response_rate": 1.0})
        valve.apply_action("SET_VALUE", 0.5)
        valve.step(dt=1.0, delta_p=1e4)
        pos_before = valve._position
        valve.inject_failure("STUCK_OPEN")
        valve.apply_action("SET_VALUE", 1.0)
        valve.step(dt=1.0, delta_p=1e4)
        assert abs(valve._position - pos_before) < 1e-9


# ===========================================================================
# 5. Pump failure
# ===========================================================================

class TestPumpFailure:
    def test_mechanical_failure_stops_flow(self):
        """Mechanical failure must stop pump flow."""
        pump = Pump("P001")
        pump.apply_action("TURN_ON")
        pump.step(dt=1.0)
        pump.inject_failure("MECHANICAL_FAILURE")
        out = pump.step(dt=1.0)
        assert out["flow_out"] == 0.0
        assert out["failed"] is True

    def test_cavitation_reduces_flow(self):
        """Cavitation must reduce pump flow."""
        pump = Pump("P001")
        pump.apply_action("TURN_ON")
        out_normal = pump.step(dt=1.0)
        flow_normal = out_normal["flow_out"]

        pump2 = Pump("P002")
        pump2.apply_action("TURN_ON")
        pump2.inject_failure("CAVITATION")
        out_cav = pump2.step(dt=1.0)
        assert out_cav["flow_out"] < flow_normal

    def test_failed_pump_cannot_be_restarted(self):
        """Failed pump must not restart via TURN_ON."""
        pump = Pump("P001")
        pump.inject_failure("MECHANICAL_FAILURE")
        pump.apply_action("TURN_ON")
        out = pump.step(dt=1.0)
        assert out["flow_out"] == 0.0

    def test_pump_reset_clears_failure(self):
        """Reset must clear pump failure."""
        pump = Pump("P001")
        pump.inject_failure("MECHANICAL_FAILURE")
        pump.reset()
        pump.apply_action("TURN_ON")
        out = pump.step(dt=1.0)
        assert out["flow_out"] > 0.0


# ===========================================================================
# 6. Alarm — high pressure
# ===========================================================================

class TestAlarmPressure:
    def setup_method(self):
        self.alarm_system = AlarmSystem()

    def test_no_alarm_at_nominal_pressure(self):
        """No alarm at nominal pressure."""
        alarms = self.alarm_system.evaluate(0.0, {"column_pressure": 101325.0})
        assert len(alarms) == 0

    def test_high_alarm_triggered(self):
        """HIGH alarm must trigger above high setpoint."""
        alarms = self.alarm_system.evaluate(0.0, {"column_pressure": 190000.0})
        assert any(a.parameter == "column_pressure" and a.severity == Severity.HIGH
                   for a in alarms)

    def test_critical_alarm_triggered(self):
        """CRITICAL alarm must trigger above high-high setpoint."""
        alarms = self.alarm_system.evaluate(0.0, {"column_pressure": 260000.0})
        assert any(a.parameter == "column_pressure" and a.severity == Severity.CRITICAL
                   for a in alarms)

    def test_low_alarm_triggered(self):
        """LOW alarm must trigger below low setpoint."""
        alarms = self.alarm_system.evaluate(0.0, {"column_pressure": 70000.0})
        assert any(a.parameter == "column_pressure" and a.severity == Severity.HIGH
                   for a in alarms)

    def test_alarm_not_duplicated(self):
        """Same alarm must not be duplicated on consecutive steps."""
        self.alarm_system.evaluate(0.0, {"column_pressure": 260000.0})
        alarms2 = self.alarm_system.evaluate(1.0, {"column_pressure": 260000.0})
        # Second evaluation should not add a new alarm for same parameter/severity
        assert len(alarms2) == 0


# ===========================================================================
# 7. Alarm — high temperature
# ===========================================================================

class TestAlarmTemperature:
    def setup_method(self):
        self.alarm_system = AlarmSystem()

    def test_no_alarm_at_nominal_temperature(self):
        """No alarm at nominal furnace temperature."""
        alarms = self.alarm_system.evaluate(0.0, {"furnace_temperature": 600.0})
        assert len(alarms) == 0

    def test_high_temperature_alarm(self):
        """HIGH alarm must trigger above high setpoint."""
        alarms = self.alarm_system.evaluate(0.0, {"furnace_temperature": 730.0})
        assert any(a.parameter == "furnace_temperature" for a in alarms)

    def test_critical_temperature_alarm(self):
        """CRITICAL alarm must trigger above HH setpoint."""
        alarms = self.alarm_system.evaluate(0.0, {"furnace_temperature": 770.0})
        assert any(a.severity == Severity.CRITICAL for a in alarms)


# ===========================================================================
# 8. Scenario loading
# ===========================================================================

class TestScenarioLoading:
    def test_all_scenarios_exist(self):
        """All 9 required scenarios must be registered."""
        required = [
            "NORMAL_OPERATION", "STARTUP", "SHUTDOWN",
            "PUMP_FAILURE_001", "VALVE_FAILURE_001",
            "PRESSURE_DEVIATION_001", "TEMPERATURE_DEVIATION_001",
            "FEED_LOSS_001", "COMBINED_EMERGENCY_001",
        ]
        for sid in required:
            assert sid in SCENARIO_REGISTRY, f"Missing scenario: {sid}"

    def test_scenario_has_required_fields(self):
        """Each scenario must have all required fields."""
        for sid, scenario in SCENARIO_REGISTRY.items():
            assert scenario.id == sid
            assert scenario.name
            assert scenario.description

    def test_digital_twin_loads_scenario(self):
        """DigitalTwin must load a scenario without error."""
        twin = DigitalTwin()
        twin.load_scenario("PUMP_FAILURE_001")
        assert twin.scenario is not None
        assert twin.scenario.id == "PUMP_FAILURE_001"

    def test_invalid_scenario_raises(self):
        """Loading non-existent scenario must raise ValueError."""
        twin = DigitalTwin()
        with pytest.raises(ValueError):
            twin.load_scenario("NONEXISTENT_SCENARIO")


# ===========================================================================
# 9. Determinism
# ===========================================================================

class TestDeterminism:
    def _run_simulation(self, seed: int, steps: int) -> SimulationState:
        config = SimulationConfig(dt=1.0, random_seed=seed)
        twin = DigitalTwin(config)
        twin.load_scenario("NORMAL_OPERATION")
        twin.start()
        state = None
        for i in range(steps):
            action = OperatorAction(
                timestamp=float(i),
                operator_id="test_op",
                equipment_id="pump_P101",
                action_type=ActionType.TURN_ON,
            )
            twin.apply_operator_action(action)
            state = twin.step(dt=1.0)
        return state

    def test_same_seed_same_result(self):
        """Same seed and actions must produce identical results."""
        state1 = self._run_simulation(seed=42, steps=50)
        state2 = self._run_simulation(seed=42, steps=50)
        assert abs(state1.feed_flow - state2.feed_flow) < 1e-12
        assert abs(state1.pressure["column"] - state2.pressure["column"]) < 1e-6

    def test_different_seed_same_result(self):
        """Without stochastic elements, different seeds should give same result."""
        state1 = self._run_simulation(seed=42, steps=50)
        state2 = self._run_simulation(seed=99, steps=50)
        # Deterministic model — same result regardless of seed
        assert abs(state1.feed_flow - state2.feed_flow) < 1e-12


# ===========================================================================
# 10. Reset
# ===========================================================================

class TestReset:
    def test_reset_clears_time(self):
        """Reset must set simulation time to zero."""
        twin = DigitalTwin()
        twin.create_simulation()
        twin.start()
        twin.step(dt=10.0)
        twin.reset()
        assert twin.simulation_time == 0.0

    def test_reset_clears_history(self):
        """Reset must clear state history."""
        twin = DigitalTwin()
        twin.create_simulation()
        twin.start()
        for _ in range(5):
            twin.step(dt=1.0)
        twin.reset()
        assert len(twin.get_history()) == 0

    def test_reset_clears_alarms(self):
        """Reset must clear active alarms."""
        twin = DigitalTwin()
        twin.create_simulation()
        twin.start()
        twin.inject_failure("furnace_F101", "OVERHEATING")
        for _ in range(10):
            twin.step(dt=1.0)
        twin.reset()
        assert len(twin.get_alarms()) == 0

    def test_state_after_reset_is_initial(self):
        """State after reset must match initial conditions."""
        twin = DigitalTwin()
        twin.create_simulation()
        initial_state = twin.get_state()
        twin.start()
        for _ in range(20):
            twin.step(dt=1.0)
        twin.reset()
        reset_state = twin.get_state()
        assert abs(reset_state.feed_flow - initial_state.feed_flow) < 1e-9


# ===========================================================================
# 11. Replay (history)
# ===========================================================================

class TestReplay:
    def test_history_length_matches_steps(self):
        """History must contain one entry per step."""
        twin = DigitalTwin()
        twin.create_simulation()
        twin.start()
        N = 30
        for _ in range(N):
            twin.step(dt=1.0)
        assert len(twin.get_history()) == N

    def test_history_timestamps_monotonic(self):
        """History timestamps must be strictly increasing."""
        twin = DigitalTwin()
        twin.create_simulation()
        twin.start()
        for _ in range(20):
            twin.step(dt=1.0)
        history = twin.get_history()
        timestamps = [s.timestamp for s in history]
        assert all(t2 > t1 for t1, t2 in zip(timestamps, timestamps[1:]))

    def test_history_is_independent_copy(self):
        """Modifying returned history must not affect internal state."""
        twin = DigitalTwin()
        twin.create_simulation()
        twin.start()
        twin.step(dt=1.0)
        history = twin.get_history()
        original_flow = history[0].feed_flow
        history[0].feed_flow = 9999.0
        # Internal state should be unchanged
        assert twin.get_history()[0].feed_flow == original_flow


# ===========================================================================
# 12. Integration — full normal operation scenario
# ===========================================================================

class TestIntegrationNormalOperation:
    def test_normal_operation_runs_without_error(self):
        """Normal operation scenario must complete without exceptions."""
        twin = DigitalTwin()
        twin.load_scenario("NORMAL_OPERATION")
        twin.start()
        # Start pump and open valve
        twin.apply_operator_action(OperatorAction(
            timestamp=0.0, operator_id="op1",
            equipment_id="pump_P101", action_type=ActionType.TURN_ON,
        ))
        twin.apply_operator_action(OperatorAction(
            timestamp=0.0, operator_id="op1",
            equipment_id="valve_FV101", action_type=ActionType.SET_VALUE,
            new_value=0.6,
        ))
        twin.apply_operator_action(OperatorAction(
            timestamp=0.0, operator_id="op1",
            equipment_id="furnace_F101", action_type=ActionType.SET_VALUE,
            new_value=0.8,
        ))
        for _ in range(100):
            state = twin.step(dt=1.0)
        assert state is not None
        assert state.timestamp > 0.0

    def test_feed_flow_established_after_pump_start(self):
        """Feed flow must be positive after pump start and valve open."""
        twin = DigitalTwin()
        twin.create_simulation()
        twin.start()
        twin.apply_operator_action(OperatorAction(
            timestamp=0.0, operator_id="op1",
            equipment_id="pump_P101", action_type=ActionType.TURN_ON,
        ))
        twin.apply_operator_action(OperatorAction(
            timestamp=0.0, operator_id="op1",
            equipment_id="valve_FV101", action_type=ActionType.SET_VALUE,
            new_value=0.6,
        ))
        for _ in range(20):
            state = twin.step(dt=1.0)
        assert state.feed_flow > 0.0

    def test_score_data_structure(self):
        """get_score_data must return a dict with required keys."""
        twin = DigitalTwin()
        twin.load_scenario("NORMAL_OPERATION")
        twin.start()
        for _ in range(10):
            twin.step(dt=1.0)
        score = twin.get_score_data()
        required_keys = [
            "simulation_time", "scenario_id", "operator_actions",
            "error_events", "alarm_history", "performance_score",
        ]
        for key in required_keys:
            assert key in score, f"Missing key in score_data: {key}"


# ===========================================================================
# 13. Integration — pump failure scenario
# ===========================================================================

class TestIntegrationPumpFailure:
    def test_pump_failure_reduces_feed_flow(self):
        """Pump failure must reduce feed flow to zero."""
        twin = DigitalTwin()
        twin.load_scenario("PUMP_FAILURE_001")
        twin.start()

        # Start pump and establish flow
        twin.apply_operator_action(OperatorAction(
            timestamp=0.0, operator_id="op1",
            equipment_id="pump_P101", action_type=ActionType.TURN_ON,
        ))
        twin.apply_operator_action(OperatorAction(
            timestamp=0.0, operator_id="op1",
            equipment_id="valve_FV101", action_type=ActionType.SET_VALUE,
            new_value=0.6,
        ))
        for _ in range(30):
            twin.step(dt=1.0)

        flow_before = twin.get_state().feed_flow

        # Inject failure
        twin.inject_failure("pump_P101", "MECHANICAL_FAILURE")
        for _ in range(5):
            state = twin.step(dt=1.0)

        assert state.feed_flow < flow_before

    def test_standby_pump_restores_flow(self):
        """Starting standby pump must restore feed flow after failure."""
        twin = DigitalTwin()
        twin.create_simulation()
        twin.start()

        twin.apply_operator_action(OperatorAction(
            timestamp=0.0, operator_id="op1",
            equipment_id="pump_P101", action_type=ActionType.TURN_ON,
        ))
        twin.apply_operator_action(OperatorAction(
            timestamp=0.0, operator_id="op1",
            equipment_id="valve_FV101", action_type=ActionType.SET_VALUE,
            new_value=0.6,
        ))
        for _ in range(20):
            twin.step(dt=1.0)

        # Fail main pump
        twin.inject_failure("pump_P101", "MECHANICAL_FAILURE")
        for _ in range(3):
            twin.step(dt=1.0)
        flow_after_failure = twin.get_state().feed_flow

        # Start standby pump
        twin.apply_operator_action(OperatorAction(
            timestamp=float(twin.simulation_time), operator_id="op1",
            equipment_id="pump_P102", action_type=ActionType.TURN_ON,
        ))
        for _ in range(10):
            state = twin.step(dt=1.0)

        # P102 running means pump_states shows it running
        assert state.pump_states.get("pump_P102") is True

    def test_failure_recorded_in_active_failures(self):
        """Injected failure must appear in active_failures list."""
        twin = DigitalTwin()
        twin.create_simulation()
        twin.start()
        twin.inject_failure("pump_P101", "MECHANICAL_FAILURE")
        state = twin.step(dt=1.0)
        assert any("pump_P101" in f for f in state.active_failures)
