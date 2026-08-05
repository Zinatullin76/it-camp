"""
demo.py
=======
Demonstration of the RIGOROUS ELOU-AVT Digital Twin simulation core.
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.base import SimulationConfig, OperatorAction, ActionType
from simulation_core.digital_twin import DigitalTwin

def separator(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def print_state(state) -> None:
    print(f"  Время симуляции : {state.timestamp:.1f} с")
    print(f"  Расход сырья    : {state.feed_flow:.2f} кг/с")
    print(f"  Выход продуктов : {state.product_flow:.2f} кг/с")
    print(f"  Давление колонны: {state.pressure.get('column', 0)/1000:.1f} кПа")
    print(f"  Темп. печи      : {state.temperature.get('furnace_outlet', 0)-273.15:.1f} °C")
    print(f"  Темп. колонны   : {state.temperature.get('column', 0)-273.15:.1f} °C")
    print(f"  Насос P101      : {'РАБОТАЕТ' if state.pump_states.get('pump_P101') else 'СТОП'}")
    print(f"  Клапан FV101    : {state.valve_positions.get('valve_FV101', 0)*100:.0f}%")
    print(f"  Активные отказы : {state.active_failures or 'нет'}")
    print(f"  Активные аварии : {len(state.alarms)}")

def main():
    separator("1. СОЗДАНИЕ СТРОГОГО ЦИФРОВОГО ДВОЙНИКА")
    
    config = SimulationConfig(dt=1.0, random_seed=42)
    twin = DigitalTwin(config)
    print(f"  Цифровой двойник создан. Статус: {twin.status.value}")

    separator("2. ЗАГРУЗКА СЦЕНАРИЯ: НОРМАЛЬНАЯ РАБОТА")
    twin.load_scenario("NORMAL_OPERATION")
    twin.start()

    print("\n  Выполнение 30 шагов симуляции...")
    for _ in range(30):
        state = twin.step(dt=1.0)
    
    print_state(state)

    separator("3. ДАННЫЕ ДЛЯ AI-АНАЛИЗА (get_score_data)")
    score_data = twin.get_score_data()
    print(f"  Сценарий: {score_data['scenario_name']}")
    print(f"  Оценка (0-100): {score_data['performance_score']}")
    
    # Show composition in final state
    print("\n  Пример данных телеметрии:")
    print(f"  - Температура печи: {state.temperature.get('furnace_outlet'):.2f} K")
    print(f"  - Тепловая нагрузка: {state.heat_duty.get('furnace')/1e6:.2f} МВт")

    separator("ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА")
    print("  Все расчёты базируются на термодинамике и балансах массы/энергии.")

if __name__ == "__main__":
    main()
