"""
params_spec.py
==============
Editable physical-property specifications for each equipment type.

The API uses these to build the per-node parameter editor and to validate
operator corrections.  Values are stored in native SI units; the ``scale``
factor converts to the display unit (display = stored / scale).

Entry fields:
    label   — human-readable name (RU)
    unit    — display unit
    scale   — stored-to-display conversion factor
    min/max — allowed range in DISPLAY units
    step    — editor step in DISPLAY units
    default — stored default when the node has no value
    int     — True for integer-valued parameters
"""

from typing import Any, Dict, List, Optional

PARAM_SPEC: Dict[str, Dict[str, Dict[str, Any]]] = {
    "source": {
        "flow_kg_s": {
            "label": "Расход", "unit": "кг/с", "scale": 1.0,
            "min": 0.0, "max": 500.0, "step": 1.0, "default": 100.0,
        },
        "temperature_c": {
            "label": "Температура", "unit": "°C", "scale": 1.0,
            "min": -50.0, "max": 1000.0, "step": 1.0, "default": 25.0,
        },
        "pressure_bar": {
            "label": "Давление", "unit": "бар", "scale": 1.0,
            "min": 0.1, "max": 50.0, "step": 0.1, "default": 1.01325,
        },
        "max_pressure_bar": {
            "label": "Макс. давление", "unit": "бар", "scale": 1.0,
            "min": 0.1, "max": 100.0, "step": 0.5, "default": 10.0,
        },
    },
    "pump": {
        "delta_p": {
            "label": "Напор", "unit": "бар", "scale": 1e5,
            "min": 0.5, "max": 30.0, "step": 0.1, "default": 5e5,
        },
        "efficiency_nominal": {
            "label": "КПД насоса", "unit": "%", "scale": 0.01,
            "min": 10.0, "max": 99.0, "step": 1.0, "default": 0.75,
        },
        "nominal_flow": {
            "label": "Номинальный расход", "unit": "кг/с", "scale": 1.0,
            "min": 0.1, "max": 500.0, "step": 1.0, "default": 100.0,
        },
        "nominal_head": {
            "label": "Номинальный напор", "unit": "м", "scale": 1.0,
            "min": 1.0, "max": 300.0, "step": 1.0, "default": 50.0,
        },
        "nominal_speed": {
            "label": "Номинальная частота вращения", "unit": "об/мин", "scale": 1.0,
            "min": 100.0, "max": 5000.0, "step": 50.0, "default": 1450.0,
        },
    },
    "valve": {
        "cv": {
            "label": "Коэффициент Cv", "unit": "", "scale": 1.0,
            "min": 0.0001, "max": 10.0, "step": 0.0005, "default": 0.01,
        },
        "design_delta_p": {
            "label": "Расчётный перепад", "unit": "бар", "scale": 1e5,
            "min": 0.05, "max": 20.0, "step": 0.05, "default": 2e5,
        },
        "response_rate": {
            "label": "Скорость срабатывания", "unit": "1/с", "scale": 1.0,
            "min": 0.01, "max": 2.0, "step": 0.01, "default": 0.2,
        },
        "initial_position": {
            "label": "Начальное открытие", "unit": "%", "scale": 0.01,
            "min": 0.0, "max": 100.0, "step": 1.0, "default": 70.0,
        },
    },
    "angle_valve": {
        "cv": {
            "label": "Коэффициент Cv", "unit": "", "scale": 1.0,
            "min": 0.0001, "max": 10.0, "step": 0.0005, "default": 0.01,
        },
        "design_delta_p": {
            "label": "Расчётный перепад", "unit": "бар", "scale": 1e5,
            "min": 0.05, "max": 20.0, "step": 0.05, "default": 2e5,
        },
        "response_rate": {
            "label": "Скорость срабатывания", "unit": "1/с", "scale": 1.0,
            "min": 0.01, "max": 2.0, "step": 0.01, "default": 0.2,
        },
        "initial_position": {
            "label": "Начальное открытие", "unit": "%", "scale": 0.01,
            "min": 0.0, "max": 100.0, "step": 1.0, "default": 70.0,
        },
    },
    "gate_valve": {
        "initial_open": {
            "label": "Открыта при старте", "unit": "", "scale": 1.0,
            "min": 0.0, "max": 1.0, "step": 1.0, "default": 1.0,
        },
    },
    "heater": {
        "max_heat_duty": {
            "label": "Макс. тепловая нагрузка", "unit": "МВт", "scale": 1e6,
            "min": 1.0, "max": 300.0, "step": 1.0, "default": 50e6,
        },
        "efficiency": {
            "label": "КПД печи", "unit": "%", "scale": 0.01,
            "min": 10.0, "max": 99.0, "step": 1.0, "default": 0.85,
        },
        "heating_value": {
            "label": "Теплота сгорания топлива", "unit": "МДж/кг", "scale": 1e6,
            "min": 5.0, "max": 80.0, "step": 0.5, "default": 40e6,
        },
        "response_tau": {
            "label": "Постоянная времени", "unit": "с", "scale": 1.0,
            "min": 1.0, "max": 600.0, "step": 1.0, "default": 60.0,
        },
    },
    "heat_exchanger": {
        "u": {
            "label": "Коэф. теплопередачи U", "unit": "Вт/(м²·К)", "scale": 1.0,
            "min": 50.0, "max": 3000.0, "step": 10.0, "default": 300.0,
        },
        "area": {
            "label": "Площадь теплообмена", "unit": "м²", "scale": 1.0,
            "min": 1.0, "max": 5000.0, "step": 10.0, "default": 200.0,
        },
        "delta_p": {
            "label": "Перепад давления", "unit": "атм", "scale": 101325,
            "min": 0.0, "max": 5.0, "step": 0.05, "default": 0.1,
        },
    },
    "column": {
        "diameter_m": {
            "label": "Диаметр", "unit": "м", "scale": 1.0,
            "min": 0.5, "max": 15.0, "step": 0.1, "default": 3.0,
        },
        "height_m": {
            "label": "Высота", "unit": "м", "scale": 1.0,
            "min": 2.0, "max": 60.0, "step": 0.5, "default": 25.0,
        },
        "num_stages": {
            "label": "Число теоретических тарелок", "unit": "шт", "scale": 1.0,
            "min": 5.0, "max": 100.0, "step": 1.0, "default": 20.0, "int": True,
        },
        "feed_stage": {
            "label": "Тарелка питания", "unit": "шт", "scale": 1.0,
            "min": 1.0, "max": 99.0, "step": 1.0, "default": 10.0, "int": True,
        },
        "nominal_pressure": {
            "label": "Давление в колонне", "unit": "бар", "scale": 1e5,
            "min": 0.5, "max": 30.0, "step": 0.1, "default": 101325.0,
        },
    },
    "elou": {
        "diameter_m": {
            "label": "Диаметр", "unit": "м", "scale": 1.0,
            "min": 0.5, "max": 20.0, "step": 0.1, "default": 5.0,
        },
        "height_m": {
            "label": "Высота", "unit": "м", "scale": 1.0,
            "min": 1.0, "max": 20.0, "step": 0.1, "default": 4.0,
        },
        "salt_efficiency": {
            "label": "Эффективность обессоливания", "unit": "%", "scale": 0.01,
            "min": 0.0, "max": 100.0, "step": 1.0, "default": 0.95,
        },
        "water_efficiency": {
            "label": "Эффективность обезвоживания", "unit": "%", "scale": 0.01,
            "min": 0.0, "max": 100.0, "step": 1.0, "default": 0.90,
        },
        "wash_water_ratio": {
            "label": "Доля промывочной воды", "unit": "%", "scale": 0.01,
            "min": 0.0, "max": 50.0, "step": 1.0, "default": 0.05,
        },
        "pressure_drop": {
            "label": "Перепад давления", "unit": "бар", "scale": 1e5,
            "min": 0.01, "max": 5.0, "step": 0.05, "default": 5e4,
        },
    },
    "separator": {
        "diameter_m": {
            "label": "Диаметр", "unit": "м", "scale": 1.0,
            "min": 0.5, "max": 30.0, "step": 0.1, "default": 6.18,
        },
        "height_m": {
            "label": "Высота", "unit": "м", "scale": 1.0,
            "min": 1.0, "max": 40.0, "step": 0.1, "default": 6.0,
        },
        "vessel_area": {
            "label": "Площадь сечения", "unit": "м²", "scale": 1.0,
            "min": 1.0, "max": 500.0, "step": 1.0, "default": 30.0,
        },
        "setpoint_level": {
            "label": "Уставка уровня", "unit": "м", "scale": 1.0,
            "min": 0.0, "max": 20.0, "step": 0.1, "default": 2.0,
        },
        "level_gain": {
            "label": "Коэф. регулятора уровня", "unit": "кг/(с·м)", "scale": 1.0,
            "min": 1.0, "max": 500.0, "step": 1.0, "default": 50.0,
        },
        "nominal_pressure": {
            "label": "Давление", "unit": "бар", "scale": 1e5,
            "min": 0.5, "max": 30.0, "step": 0.1, "default": 101325.0,
        },
    },
    "tank": {
        "diameter_m": {
            "label": "Диаметр", "unit": "м", "scale": 1.0,
            "min": 0.5, "max": 30.0, "step": 0.1, "default": 6.18,
        },
        "height_m": {
            "label": "Высота", "unit": "м", "scale": 1.0,
            "min": 1.0, "max": 40.0, "step": 0.1, "default": 6.0,
        },
        "vessel_area": {
            "label": "Площадь сечения", "unit": "м²", "scale": 1.0,
            "min": 1.0, "max": 500.0, "step": 1.0, "default": 30.0,
        },
        "setpoint_level": {
            "label": "Уставка уровня", "unit": "м", "scale": 1.0,
            "min": 0.0, "max": 20.0, "step": 0.1, "default": 2.0,
        },
        "level_gain": {
            "label": "Коэф. регулятора уровня", "unit": "кг/(с·м)", "scale": 1.0,
            "min": 1.0, "max": 500.0, "step": 1.0, "default": 50.0,
        },
        "nominal_pressure": {
            "label": "Давление", "unit": "бар", "scale": 1e5,
            "min": 0.5, "max": 30.0, "step": 0.1, "default": 101325.0,
        },
    },
    "mixer": {
        "num_inputs": {
            "label": "Число входов", "unit": "", "scale": 1.0,
            "min": 1, "max": 8, "step": 1, "default": 2,
        },
    },
    "separator_s1k": {
        "diameter_m": {
            "label": "Диаметр", "unit": "м", "scale": 1.0,
            "min": 0.5, "max": 30.0, "step": 0.1, "default": 6.18,
        },
        "height_m": {
            "label": "Высота", "unit": "м", "scale": 1.0,
            "min": 1.0, "max": 40.0, "step": 0.1, "default": 6.0,
        },
        "vessel_area": {
            "label": "Площадь сечения", "unit": "м²", "scale": 1.0,
            "min": 1.0, "max": 500.0, "step": 1.0, "default": 30.0,
        },
        "setpoint_level": {
            "label": "Уставка уровня", "unit": "м", "scale": 1.0,
            "min": 0.0, "max": 20.0, "step": 0.1, "default": 2.0,
        },
        "level_gain": {
            "label": "Коэф. регулятора уровня", "unit": "кг/(с·м)", "scale": 1.0,
            "min": 1.0, "max": 500.0, "step": 1.0, "default": 50.0,
        },
        "nominal_pressure": {
            "label": "Давление", "unit": "бар", "scale": 1e5,
            "min": 0.5, "max": 30.0, "step": 0.1, "default": 101325.0,
        },
        "initial_level": {
            "label": "Начальный уровень", "unit": "м", "scale": 1.0,
            "min": 0.0, "max": 20.0, "step": 0.1, "default": 2.0,
        },
        "level_auto": {
            "label": "Регулятор уровня (AUTO)", "unit": "", "scale": 1.0,
            "min": 0, "max": 1, "step": 1, "default": True,
        },
    },
    "sink": {
        "pressure_bar": {
            "label": "Давление на стоке", "unit": "бар", "scale": 1.0,
            "min": 0.1, "max": 50.0, "step": 0.1, "default": 1.01325,
        },
    },
}

# Types that have no adjustable physical properties yet.
NON_EDITABLE_TYPES = ()


def spec_for(node_type: str) -> Dict[str, Dict[str, Any]]:
    """Return the editable-parameter spec for a node type (empty if none)."""
    return PARAM_SPEC.get(node_type, {})


def stored_value(node_type: str, eq: Any, node: Any, key: str) -> Any:
    """Current stored (SI) value for a parameter of a scheme node."""
    meta = PARAM_SPEC.get(node_type, {}).get(key)
    if meta is None:
        return None
    if eq is not None and key in getattr(eq, "params", {}):
        return eq.params[key]
    if node is not None and key in getattr(node, "params", {}):
        return node.params[key]
    return meta.get("default")


def editor_spec(node_type: str, eq: Any, node: Any) -> List[Dict[str, Any]]:
    """Build the editor row list for one node (values in display units)."""
    rows: List[Dict[str, Any]] = []
    for key, meta in PARAM_SPEC.get(node_type, {}).items():
        stored = stored_value(node_type, eq, node, key)
        rows.append(
            {
                "key": key,
                "label": meta["label"],
                "unit": meta.get("unit", ""),
                "value": round(float(stored) / meta["scale"], 4) if stored is not None else None,
                "min": meta.get("min", 0.0),
                "max": meta.get("max", 1e9),
                "step": meta.get("step", 0.1),
                "int": bool(meta.get("int")),
            }
        )
    return rows


def coerce(key: str, display_value: float, node_type: str) -> Optional[float]:
    """Convert a display-unit value back to stored SI, clamped to spec."""
    meta = PARAM_SPEC.get(node_type, {}).get(key)
    if meta is None:
        return None
    stored = float(display_value) * meta["scale"]
    if meta.get("int"):
        stored = int(round(stored))
    lo = meta["min"] * meta["scale"]
    hi = meta["max"] * meta["scale"]
    return min(max(stored, lo), hi)
