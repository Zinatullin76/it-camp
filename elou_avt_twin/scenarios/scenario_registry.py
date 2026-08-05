"""
scenario_registry.py
====================
Updated scenarios for ELOU-AVT simulator with rigorous physics.
"""

from models.scenario import Scenario, ScenarioEvent
from typing import Dict

def build_scenarios() -> Dict[str, Scenario]:
    scenarios: Dict[str, Scenario] = {}

    # 1. Normal operation
    scenarios["NORMAL_OPERATION"] = Scenario(
        id="NORMAL_OPERATION",
        name="Нормальная работа (Rigorous)",
        description="Установка работает в штатном режиме с использованием термодинамических расчётов.",
        initial_state={
            "pump_P101_running": True,
            "valve_FV101_position": 0.6,
            "furnace_F101_fuel_flow": 0.8,
        },
        events=[],
        start_conditions={"all_equipment_ready": True},
        end_conditions={"simulation_time": 3600.0},
        success_criteria={"no_alarms": True, "stable_operation": True},
        failure_criteria={"critical_alarm": True},
        reference_actions=[],
    )

    # 4. Pump failure
    scenarios["PUMP_FAILURE_001"] = Scenario(
        id="PUMP_FAILURE_001",
        name="Отказ насоса подачи сырья (Rigorous)",
        description="Внезапный отказ основного насоса подачи сырья P-101. Требуется переход на резервный P-102.",
        initial_state={
            "pump_P101_running": True,
            "pump_P102_running": False,
            "valve_FV101_position": 0.6,
        },
        events=[
            ScenarioEvent(
                timestamp=60.0,
                event_type="INJECT_FAILURE",
                target_id="pump_P101",
                parameters={"failure_mode": "MECHANICAL_FAILURE"},
            ),
        ],
        start_conditions={"normal_operation": True},
        end_conditions={"simulation_time": 600.0},
        success_criteria={"pump_P102_started": True, "feed_flow_restored": True},
        failure_criteria={"feed_loss_duration": 120.0},
        reference_actions=[
            {"t": 65.0,  "action": "TURN_ON",  "equipment": "pump_P102"},
            {"t": 70.0,  "action": "SET_VALUE", "equipment": "valve_FV101", "value": 0.6},
        ],
    )

    # Additional MVP training scenarios
    for sid, name, desc in [
        ("STARTUP", "Пуск установки", "Безопасный запуск оборудования и выход на стабильный режим."),
        ("SHUTDOWN", "Останов установки", "Плановый останов установки с соблюдением последовательности."),
        ("VALVE_FAILURE_001", "Отказ клапана FV-101", "Клапан регулирования подачи не отвечает на команду."),
        ("PRESSURE_DEVIATION_001", "Отклонение давления", "Давление в колонне выходит за рабочий диапазон."),
        ("TEMPERATURE_DEVIATION_001", "Отклонение температуры", "Температура печи растёт выше заданного диапазона."),
        ("FEED_LOSS_001", "Потеря подачи сырья", "Потеря входного потока и восстановление подачи."),
        ("COMBINED_EMERGENCY_001", "Комбинированная авария", "Сочетание отказа насоса и отклонения давления."),
    ]:
        scenarios[sid] = Scenario(
            id=sid, name=name, description=desc, initial_state={"pump_P101_running": True, "pump_P102_running": False, "valve_FV101_position": 0.6},
            events=[], start_conditions={"normal_operation": True}, end_conditions={"simulation_time": 300.0},
            success_criteria={"operator_response": True}, failure_criteria={"critical_alarm": True}, reference_actions=[]
        )

    return scenarios

SCENARIO_REGISTRY: Dict[str, Scenario] = build_scenarios()
