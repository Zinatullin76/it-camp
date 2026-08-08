"""
generate_full_scheme.py
=======================
Generate the full ELOU-AVT-4 P&ID scheme (all major equipment from
"Оборудование.txt") and persist it to schemes/process_elou_avt.json.

Run from the project root (elou_avt_twin):
    python -m tools.generate_full_scheme

The scheme carries per-node physical boundaries in node.params["limits"]:
    pressure_low / pressure_high / pressure_high_high   [Pa]
    temperature_*                                       [K]
    level_low / level_low_low / level_high              [m]
where 1 kgf/cm2 = 98066.5 Pa. Column temperature limits are calibrated to the
lumped distillation model (bubble-point driven) rather than to literal
"Оборудование.txt" values, because the simulator's temperatures are functions
of the model's Antoine constants and the column operating pressure.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scheme.model import ProcessScheme, SchemeNode, SchemeEdge, save_scheme

KGFCM2 = 98066.5


def C(temp_c: float) -> float:
    """Celsius -> Kelvin."""
    return temp_c + 273.15


def kgf(n: float) -> float:
    """kgf/cm2 -> Pa."""
    return n * KGFCM2


def node(node_id, ntype, name, x, y, params=None):
    return SchemeNode(id=node_id, type=ntype, name=name, x=x, y=y, params=params or {})


def edge(edge_id, source, target, source_port="out", target_port="in", kind="process"):
    return SchemeEdge(id=edge_id, source=source, target=target,
                      source_port=source_port, target_port=target_port, kind=kind)


def build_scheme() -> ProcessScheme:
    scheme = ProcessScheme(id="process_elou_avt", name="ЭЛОУ-АВТ-4 / полная технологическая схема")

    # ----------------------------------------------------------------
    # Sources
    # ----------------------------------------------------------------
    scheme.add_node(node("src_feed", "source", "Сырая нефть (сырьё)", 40, 420, {
        "flow_kg_s": 100.0, "temperature_c": 25.0, "pressure_bar": 1.01325,
        "composition": {"frac_nk62": 0.02, "frac_62_105": 0.04, "frac_105_180": 0.10,
                        "frac_180_240": 0.13, "frac_240_300": 0.12, "frac_300_350": 0.10,
                        "frac_mazut": 0.40, "water": 0.06, "salt": 0.03},
    }))
    scheme.add_node(node("src_hot_pogo", "source", "Горячие погоны К-2/К-3 (рекуперация)", 40, 60, {
        "flow_kg_s": 60.0, "temperature_c": 200.0, "pressure_bar": 1.5,
        "composition": {"frac_105_180": 0.30, "frac_180_240": 0.40, "frac_240_300": 0.20,
                        "frac_300_350": 0.08, "water": 0.02},
    }))
    scheme.add_node(node("src_mazut", "source", "Мазут (циркуляция)", 40, 160, {
        "flow_kg_s": 60.0, "temperature_c": 300.0, "pressure_bar": 2.0,
        "composition": {"frac_mazut": 0.96, "water": 0.02, "salt": 0.02},
    }))
    scheme.add_node(node("src_cw", "source", "Оборотная вода", 40, 640, {
        "flow_kg_s": 300.0, "temperature_c": 20.0, "pressure_bar": 3.0,
        "composition": {"water": 1.0},
    }))
    scheme.add_node(node("src_gas", "source", "Газ из Е-1 / топливный газ", 1960, 40, {
        "flow_kg_s": 10.0, "temperature_c": 40.0, "pressure_bar": 2.0,
        "composition": {"frac_nk62": 0.60, "frac_62_105": 0.30, "water": 0.10},
    }))
    scheme.add_node(node("src_brine", "source", "Солёная вода с ЭЛОУ", 40, 560, {
        "flow_kg_s": 8.0, "temperature_c": 100.0, "pressure_bar": 3.0,
        "composition": {"water": 0.9, "salt": 0.1},
    }))
    scheme.add_node(node("src_naphtha", "source", "Нестабильный бензин с установок", 2050, 700, {
        "flow_kg_s": 30.0, "temperature_c": 40.0, "pressure_bar": 1.5,
        "composition": {"frac_nk62": 0.30, "frac_62_105": 0.40, "frac_105_180": 0.20,
                        "water": 0.10},
    }))

    # ----------------------------------------------------------------
    # Pumps
    # ----------------------------------------------------------------
    scheme.add_node(node("pump_H1", "pump", "Н-1 сырьевые насосы", 300, 420, {
        "nominal_flow": 0.12, "efficiency_nominal": 0.75,
    }))
    scheme.add_node(node("pump_H20", "pump", "Н-20 подача обессоленной нефти в К-1", 1500, 420, {
        "nominal_flow": 0.12,
    }))
    scheme.add_node(node("pump_H6", "pump", "Н-6 нестабильный бензин в К-4", 820, 260, {
        "nominal_flow": 0.05,
    }))
    scheme.add_node(node("pump_H2", "pump", "Н-2/Н-3 отбензиненная нефть в печи", 1820, 580, {
        "nominal_flow": 0.1,
    }))
    scheme.add_node(node("pump_H4", "pump", "Н-4 откачка мазута из К-2", 2380, 480, {
        "nominal_flow": 0.08,
    }))
    scheme.add_node(node("pump_H58", "pump", "Н-58 фр. 105–180 °С из К-10", 3700, 380, {
        "nominal_flow": 0.03,
    }))

    # ----------------------------------------------------------------
    # Control valves
    # ----------------------------------------------------------------
    scheme.add_node(node("valve_FV1", "valve", "FV-1/2/3 подача сырья", 480, 420, {
        "cv": 0.02, "response_rate": 0.2, "initial_position": 0.6,
    }))
    scheme.add_node(node("valve_PV1", "valve", "PV-1 давление верха К-1", 1480, 180, {
        "cv": 0.0022, "response_rate": 0.15, "initial_position": 0.5,
    }))
    scheme.add_node(node("valve_PV2", "valve", "PV-2 давление верха К-2", 2320, 60, {
        "cv": 0.0022, "response_rate": 0.15, "initial_position": 0.5,
    }))
    scheme.add_node(node("valve_PV4", "valve", "PV-4 давление верха К-4", 1980, 160, {
        "cv": 0.0012, "response_rate": 0.15, "initial_position": 0.5,
    }))
    scheme.add_node(node("valve_FV12", "valve", "FV-12 орошение/отбор НК–62 (К-9)", 2920, 120, {
        "cv": 0.0022, "response_rate": 0.2, "initial_position": 0.7,
    }))
    scheme.add_node(node("valve_FV11", "valve", "FV-11 орошение/отбор 62–105 (К-10)", 3520, 120, {
        "cv": 0.0021, "response_rate": 0.2, "initial_position": 0.7,
    }))
    scheme.add_node(node("valve_FV13", "valve", "FV-13 отбор фр. 140–240 на К-12", 2600, 620, {
        "cv": 0.0019, "response_rate": 0.2, "initial_position": 0.8,
    }))

    # ----------------------------------------------------------------
    # Heat exchangers / condensers
    # ----------------------------------------------------------------
    scheme.add_node(node("hx_T1", "heat_exchanger", "Т-1…Т-11 подогрев сырой нефти", 680, 420, {
        "u": 300.0, "area": 250.0,
    }))
    scheme.add_node(node("hx_T17", "heat_exchanger", "Т-17/Т-19/Т-22 подогрев обессоленной нефти", 1680, 420, {
        "u": 300.0, "area": 300.0,
    }))
    scheme.add_node(node("hx_cond1", "heat_exchanger", "Х-1/3–Х-1/5, АВЗ-3 конденсация верха К-1", 900, 140, {
        "u": 400.0, "area": 200.0,
    }))
    scheme.add_node(node("hx_cond2", "heat_exchanger", "Х-2/3–Х-2/5, АВЗ-4/5 конденсация верха К-2", 2440, 140, {
        "u": 400.0, "area": 200.0,
    }))
    scheme.add_node(node("hx_cond4", "heat_exchanger", "Х-4/1–Х-4/3 конденсация ПБФ (К-4)", 2050, 240, {
        "u": 400.0, "area": 150.0,
    }))
    scheme.add_node(node("hx_cond9", "heat_exchanger", "АВЗ-1/2, Х-20, Х-21/1 конденсация НК–62 (К-9)", 3120, 120, {
        "u": 400.0, "area": 120.0,
    }))
    scheme.add_node(node("hx_cond10", "heat_exchanger", "Х-22, Х-21/2 конденсация 62–105 (К-10)", 3720, 120, {
        "u": 400.0, "area": 120.0,
    }))

    # ----------------------------------------------------------------
    # ELOU (electrodehydrators)
    # ----------------------------------------------------------------
    scheme.add_node(node("elou_1", "elou", "Э-1/Э-3/Э-5 ЭЛОУ 1-я ступень", 900, 420, {
        "vessel_area": 9.08, "salt_efficiency": 0.9, "water_efficiency": 0.8, "initial_level": 4.0,
        "limits": {
            "pressure_low": kgf(4.5), "pressure_low_low": kgf(4.0),
            "pressure_high": kgf(10.0), "pressure_high_high": kgf(12.0),
            "temperature_high": C(140.0), "temperature_high_high": C(150.0),
            "level_low": 3.8, "level_low_low": 3.5,
        },
    }))
    scheme.add_node(node("elou_2", "elou", "Э-2/Э-4/Э-6 ЭЛОУ 2-я ступень", 1120, 420, {
        "vessel_area": 9.08, "salt_efficiency": 0.8, "water_efficiency": 0.7, "initial_level": 4.0,
        "limits": {
            "pressure_low": kgf(4.5), "pressure_low_low": kgf(4.0),
            "pressure_high": kgf(10.0), "pressure_high_high": kgf(12.0),
            "temperature_high": C(140.0), "temperature_high_high": C(150.0),
            "level_low": 3.8, "level_low_low": 3.5,
        },
    }))

    # ----------------------------------------------------------------
    # Vessels / separators
    # ----------------------------------------------------------------
    scheme.add_node(node("tank_R11", "separator", "Р-11/Р-12 сырьевые резервуары", 180, 420, {
        "vessel_area": 30.0, "initial_level": 2.5,
        "limits": {"level_low": 1.0, "level_low_low": 0.6},
    }))
    scheme.add_node(node("tank_R13", "separator", "Р-13/Р-14/Р-15 резервуары бензина", 2600, 700, {
        "vessel_area": 30.0, "initial_level": 2.0,
        "limits": {"level_low": 1.0, "level_low_low": 0.6},
    }))
    scheme.add_node(node("sep_E15", "separator", "Е-15 буферная ёмкость обессоленной нефти", 1340, 420, {
        "vessel_area": 12.6, "initial_level": 2.5,
        "limits": {"level_low": 1.0, "level_low_low": 0.6},
    }))
    scheme.add_node(node("sep_E16", "separator", "Е-16 сбор солёной воды с ЭЛОУ", 180, 560, {
        "vessel_area": 9.08, "initial_level": 1.5,
        "limits": {"level_low": 0.8, "level_low_low": 0.5},
    }))
    scheme.add_node(node("sep_E1", "separator", "Е-1 водоотделитель верха К-1", 1180, 200, {
        "vessel_area": 7.07, "initial_level": 1.5,
        "limits": {"level_low": 0.8, "level_low_low": 0.5},
    }))
    scheme.add_node(node("sep_E2", "separator", "Е-2 водоотделитель верха К-2", 2600, 200, {
        "vessel_area": 7.07, "initial_level": 1.5,
        "limits": {"level_low": 0.8, "level_low_low": 0.5},
    }))
    scheme.add_node(node("sep_E3", "separator", "Е-3 рефлюксная ёмкость К-4", 2360, 300, {
        "vessel_area": 3.14, "initial_level": 1.5,
        "limits": {"level_low": 0.8, "level_low_low": 0.5},
    }))
    scheme.add_node(node("sep_E18", "separator", "Е-18 рефлюкс верха К-9", 3360, 120, {
        "vessel_area": 4.52, "initial_level": 1.5,
        "limits": {"level_low": 0.8, "level_low_low": 0.5},
    }))
    scheme.add_node(node("sep_E17", "separator", "Е-17 рефлюкс верха К-10", 4000, 120, {
        "vessel_area": 2.01, "initial_level": 1.5,
        "limits": {"level_low": 0.8, "level_low_low": 0.5},
    }))
    scheme.add_node(node("sep_C1K", "separator", "С-1К сепаратор после демеркаптанизации", 3260, 640, {
        "vessel_area": 2.01, "initial_level": 1.5,
        "limits": {"level_low": 0.8, "level_low_low": 0.5},
    }))
    scheme.add_node(node("reactor_K124", "separator", "К-12/4 реактор демеркаптанизации", 2900, 640, {
        "vessel_area": 7.07, "initial_level": 2.0,
        "limits": {
            "pressure_low": kgf(1.0), "pressure_high": kgf(7.0), "pressure_high_high": kgf(8.0),
            "temperature_low": C(150.0), "temperature_high": C(300.0), "temperature_high_high": C(320.0),
            "level_low": 1.0, "level_low_low": 0.6,
        },
    }))

    # ----------------------------------------------------------------
    # Columns
    # ----------------------------------------------------------------
    scheme.add_node(node("column_K1", "column", "К-1 атмосферная ректификация", 1900, 420, {
        "preset": "k1", "num_stages": 28, "feed_stage": 16, "nominal_pressure": kgf(2.0), "sump_area": 15.9, "initial_level": 2.5,
        "top_cut": ["frac_nk62", "frac_62_105", "water"],
        "solver_n_iter": 80,
        "limits": {
            "pressure_low": kgf(1.0), "pressure_low_low": kgf(0.8),
            "pressure_high": kgf(4.5), "pressure_high_high": kgf(4.8),
            "temperature_top_high": C(250.0), "temperature_top_high_high": C(270.0),
            "temperature_bottom_high": C(300.0), "temperature_bottom_high_high": C(320.0),
            "level_low": 1.0, "level_low_low": 0.6,
        },
    }))
    scheme.add_node(node("column_K2", "column", "К-2 ректификация (разделение мазута)", 2200, 420, {
        "num_stages": 30, "feed_stage": 6, "nominal_pressure": kgf(0.6), "sump_area": 19.63, "initial_level": 2.5,
        "top_cut": ["frac_105_180"],
        "solver_n_iter": 80, "solver_tol": 3e-3,
        "limits": {
            "pressure_low": kgf(0.2), "pressure_low_low": kgf(0.15),
            "pressure_high": kgf(1.0), "pressure_high_high": kgf(1.5),
            "temperature_top_high": C(180.0), "temperature_top_high_high": C(200.0),
            "temperature_bottom_high": C(280.0), "temperature_bottom_high_high": C(300.0),
            "level_low": 1.0, "level_low_low": 0.6,
        },
    }))
    scheme.add_node(node("column_K31", "column", "К-3/1 отпарная фр. 140–240 °С", 2700, 460, {
        "num_stages": 10, "feed_stage": 5, "nominal_pressure": kgf(3.0), "sump_area": 3.14, "initial_level": 2.0,
        "top_cut": ["frac_180_240"],
        "solver_n_iter": 80, "solver_tol": 3e-3,
        "limits": {
            "pressure_low": kgf(1.5), "pressure_high": kgf(4.5), "pressure_high_high": kgf(5.0),
            "temperature_top_high": C(310.0), "temperature_top_high_high": C(330.0),
            "temperature_bottom_high": C(340.0), "temperature_bottom_high_high": C(360.0),
            "level_low": 0.8, "level_low_low": 0.5,
        },
    }))
    scheme.add_node(node("column_K32", "column", "К-3/2 отпарная фр. 240–300 °С", 2880, 460, {
        "num_stages": 10, "feed_stage": 5, "nominal_pressure": kgf(3.0), "sump_area": 3.14, "initial_level": 2.0,
        "top_cut": ["frac_240_300"],
        "solver_n_iter": 80, "solver_tol": 3e-3,
        "limits": {
            "pressure_low": kgf(1.5), "pressure_high": kgf(4.5), "pressure_high_high": kgf(5.0),
            "temperature_top_high": C(320.0), "temperature_top_high_high": C(340.0),
            "temperature_bottom_high": C(360.0), "temperature_bottom_high_high": C(380.0),
            "level_low": 0.8, "level_low_low": 0.5,
        },
    }))
    scheme.add_node(node("column_K33", "column", "К-3/3 отпарная фр. 300–350 °С", 3060, 460, {
        "num_stages": 10, "feed_stage": 5, "nominal_pressure": kgf(3.0), "sump_area": 3.14, "initial_level": 2.0,
        "top_cut": ["frac_300_350"],
        "solver_n_iter": 80, "solver_tol": 3e-3,
        "limits": {
            "pressure_low": kgf(1.5), "pressure_high": kgf(4.5), "pressure_high_high": kgf(5.0),
            "temperature_top_high": C(380.0), "temperature_top_high_high": C(400.0),
            "temperature_bottom_high": C(400.0), "temperature_bottom_high_high": C(420.0),
            "level_low": 0.8, "level_low_low": 0.5,
        },
    }))
    scheme.add_node(node("column_K4", "column", "К-4 стабилизация бензина", 2080, 340, {
        "num_stages": 25, "feed_stage": 12, "nominal_pressure": kgf(8.0), "sump_area": 4.52, "initial_level": 2.0,
        "top_cut": ["frac_nk62"],
        "solver_n_iter": 80, "solver_tol": 3e-3,
        "limits": {
            "pressure_low": kgf(6.0), "pressure_low_low": kgf(5.5),
            "pressure_high": kgf(11.0), "pressure_high_high": kgf(12.0),
            "temperature_top_high": C(260.0), "temperature_top_high_high": C(280.0),
            "temperature_bottom_high": C(330.0), "temperature_bottom_high_high": C(350.0),
            "level_low": 0.8, "level_low_low": 0.5,
        },
    }))
    scheme.add_node(node("column_K7", "column", "К-7 газосепаратор/абсорбер", 2140, 40, {
        "num_stages": 25, "feed_stage": 12, "nominal_pressure": kgf(2.0), "sump_area": 3.14, "initial_level": 1.5,
        "top_cut": ["frac_nk62"],
        "solver_n_iter": 80, "solver_tol": 3e-3,
        "limits": {
            "pressure_low": kgf(1.0), "pressure_low_low": kgf(0.8),
            "pressure_high": kgf(4.5), "pressure_high_high": kgf(5.0),
            "temperature_top_high": C(180.0), "temperature_top_high_high": C(200.0),
            "temperature_bottom_high": C(200.0), "temperature_bottom_high_high": C(220.0),
            "level_low": 0.8, "level_low_low": 0.5,
        },
    }))
    scheme.add_node(node("column_K9", "column", "К-9 вторичная перегонка (НК–62)", 2700, 240, {
        "num_stages": 30, "feed_stage": 15, "nominal_pressure": kgf(2.0), "sump_area": 7.07, "initial_level": 2.0,
        "top_cut": ["frac_nk62"],
        "solver_n_iter": 80, "solver_tol": 3e-3,
        "limits": {
            "pressure_low": kgf(1.0), "pressure_low_low": kgf(0.8),
            "pressure_high": kgf(3.0), "pressure_high_high": kgf(3.5),
            "temperature_top_high": C(200.0), "temperature_top_high_high": C(220.0),
            "temperature_bottom_high": C(260.0), "temperature_bottom_high_high": C(280.0),
            "level_low": 0.8, "level_low_low": 0.5,
        },
    }))
    scheme.add_node(node("column_K10", "column", "К-10 вторичная перегонка (62–105)", 3300, 240, {
        "num_stages": 30, "feed_stage": 15, "nominal_pressure": kgf(0.6), "sump_area": 7.07, "initial_level": 2.0,
        "top_cut": ["frac_62_105"],
        "solver_n_iter": 80, "solver_tol": 3e-3,
        "limits": {
            "pressure_low": kgf(0.2), "pressure_low_low": kgf(0.15),
            "pressure_high": kgf(1.0), "pressure_high_high": kgf(1.5),
            "temperature_top_high": C(180.0), "temperature_top_high_high": C(200.0),
            "temperature_bottom_high": C(260.0), "temperature_bottom_high_high": C(280.0),
            "level_low": 0.8, "level_low_low": 0.5,
        },
    }))
    scheme.add_node(node("column_K12", "column", "К-12/3 отпарная демеркаптанизации", 3100, 640, {
        "num_stages": 4, "feed_stage": 2, "nominal_pressure": kgf(6.0), "sump_area": 5.3, "initial_level": 1.5,
        "top_cut": ["frac_180_240"],
        "solver_n_iter": 80, "solver_tol": 3e-3,
        "limits": {
            "pressure_low": kgf(3.0), "pressure_low_low": kgf(2.5),
            "pressure_high": kgf(10.0), "pressure_high_high": kgf(11.0),
            "temperature_top_high": C(340.0), "temperature_top_high_high": C(360.0),
            "temperature_bottom_high": C(360.0), "temperature_bottom_high_high": C(380.0),
            "level_low": 0.8, "level_low_low": 0.5,
        },
    }))

    # ----------------------------------------------------------------
    # Furnaces
    # ----------------------------------------------------------------
    scheme.add_node(node("furnace_P1", "heater", "П-1 печь нагрева отбензиненной нефти", 2080, 540, {
        "max_heat_duty": 60e6, "response_tau": 60.0, "initial_fuel_flow": 0.8,
        "limits": {"temperature_high": C(365.0), "temperature_high_high": C(380.0)},
    }))
    scheme.add_node(node("furnace_P3", "heater", "П-3 печь К-4 (рибойлер)", 2200, 700, {
        "max_heat_duty": 40e6, "response_tau": 60.0, "initial_fuel_flow": 0.15,
        "limits": {"temperature_high": C(365.0), "temperature_high_high": C(380.0)},
    }))
    scheme.add_node(node("furnace_P4a", "heater", "П-4 контур К-9 (циркуляция)", 2880, 300, {
        "max_heat_duty": 40e6, "response_tau": 60.0, "initial_fuel_flow": 0.15,
        "limits": {"temperature_high": C(350.0), "temperature_high_high": C(365.0)},
    }))
    scheme.add_node(node("furnace_P4b", "heater", "П-4 контур К-10 (циркуляция)", 3480, 380, {
        "max_heat_duty": 40e6, "response_tau": 60.0, "initial_fuel_flow": 0.04,
        "limits": {"temperature_high": C(350.0), "temperature_high_high": C(365.0)},
    }))

    # ----------------------------------------------------------------
    # Sinks
    # ----------------------------------------------------------------
    scheme.add_node(node("sink_vapour", "sink", "Газы/пары верха К-1, К-2", 1680, 60, {}))
    scheme.add_node(node("sink_offgas", "sink", "Сухой газ верха К-7", 2480, 40, {}))
    scheme.add_node(node("sink_benzene", "sink", "Бензин 85–180 °С (защелачивание/товар)", 2700, 120, {}))
    scheme.add_node(node("sink_kerosene", "sink", "Обессеренный керосин (К-12)", 3400, 640, {}))
    scheme.add_node(node("sink_diesel", "sink", "Фр. 240–300 °С (дизельное топливо)", 3020, 300, {}))
    scheme.add_node(node("sink_gasoil", "sink", "Фр. 300–350 °С (компонент мазута)", 3300, 400, {}))
    scheme.add_node(node("sink_fuel_oil", "sink", "Мазут", 3360, 500, {}))
    scheme.add_node(node("sink_stabgas", "sink", "ПБФ (верха К-4)", 2500, 360, {}))
    scheme.add_node(node("sink_62", "sink", "Фр. НК–62 °С", 3620, 240, {}))
    scheme.add_node(node("sink_105", "sink", "Фр. 62–105 °С", 4280, 140, {}))
    scheme.add_node(node("sink_105_180", "sink", "Фр. 105–180 °С", 3860, 420, {}))
    scheme.add_node(node("sink_cw_out", "sink", "Оборотная вода (выход)", 1400, 640, {}))
    scheme.add_node(node("sink_brine", "sink", "Солёная вода → канализация", 380, 560, {}))
    scheme.add_node(node("sink_hot_ret", "sink", "Возврат горячего теплоносителя", 40, 100, {}))

    # ----------------------------------------------------------------
    # Edges
    # ----------------------------------------------------------------
    add = scheme.add_edge

    # Feed train: crude -> tank -> pump -> valve -> preheat -> ELOU -> E-15 -> pump -> HX -> K-1
    add(edge("e_feed_tank", "src_feed", "tank_R11"))
    add(edge("e_tank_h1", "tank_R11", "pump_H1"))
    add(edge("e_h1_fv1", "pump_H1", "valve_FV1"))
    add(edge("e_fv1_hx1", "valve_FV1", "hx_T1", target_port="cold_in"))
    add(edge("e_pogo_hx1", "src_hot_pogo", "hx_T1", target_port="hot_in", kind="hot"))
    add(edge("e_hx1_elou1", "hx_T1", "elou_1", source_port="cold_out"))
    add(edge("e_elou1_elou2", "elou_1", "elou_2"))
    add(edge("e_elou2_e15", "elou_2", "sep_E15"))
    add(edge("e_e15_h20", "sep_E15", "pump_H20"))
    add(edge("e_h20_hx17", "pump_H20", "hx_T17", target_port="cold_in"))
    add(edge("e_mazut_hx17", "src_mazut", "hx_T17", target_port="hot_in", kind="hot"))
    add(edge("e_hx17_k1", "hx_T17", "column_K1", source_port="cold_out"))
    # Closed hot-side returns: hot oil must continue somewhere, not vanish.
    add(edge("e_hx1_hot_ret", "hx_T1", "sink_hot_ret", source_port="hot_out"))
    add(edge("e_hx17_hot_ret", "hx_T17", "sink_hot_ret", source_port="hot_out"))
    # ELOU brine drains to the brine sewer instead of disappearing.
    add(edge("e_elou1_brine", "elou_1", "sink_brine", source_port="brine"))
    add(edge("e_elou2_brine", "elou_2", "sink_brine", source_port="brine"))

    # Brine collection
    add(edge("e_brine_e16", "src_brine", "sep_E16"))
    add(edge("e_e16_brine", "sep_E16", "sink_brine"))

    # K-1 overhead: condenser -> E-1 -> pump H-6 -> K-4 ; pressure control vent
    add(edge("e_k1_cond1", "column_K1", "hx_cond1", source_port="distillate", target_port="hot_in"))
    add(edge("e_cw_cond1", "src_cw", "hx_cond1", target_port="cold_in", kind="cooling"))
    add(edge("e_cond1_cw", "hx_cond1", "sink_cw_out", source_port="cold_out"))
    add(edge("e_cond1_e1", "hx_cond1", "sep_E1", source_port="hot_out"))
    add(edge("e_e1_h6", "sep_E1", "pump_H6"))
    add(edge("e_h6_k4", "pump_H6", "column_K4"))
    add(edge("e_k1_pv1", "column_K1", "valve_PV1", source_port="distillate"))
    add(edge("e_pv1_vap", "valve_PV1", "sink_vapour"))

    # K-7 gas separator: gas -> absorber -> dry gas / rich absorbent back to K-1
    add(edge("e_gas_k7", "src_gas", "column_K7"))
    add(edge("e_k7_offgas", "column_K7", "sink_offgas", source_port="distillate"))
    add(edge("e_k7_k1", "column_K7", "column_K1", source_port="bottoms"))

    # K-1 bottoms -> pump H-2 -> furnace P-1 -> K-2
    add(edge("e_k1_h2", "column_K1", "pump_H2", source_port="bottoms"))
    add(edge("e_h2_p1", "pump_H2", "furnace_P1"))
    add(edge("e_p1_k2", "furnace_P1", "column_K2"))

    # K-2 overhead -> condenser -> E-2 -> benzene ; vent
    add(edge("e_k2_cond2", "column_K2", "hx_cond2", source_port="distillate", target_port="hot_in"))
    add(edge("e_cw_cond2", "src_cw", "hx_cond2", target_port="cold_in", kind="cooling"))
    add(edge("e_cond2_cw", "hx_cond2", "sink_cw_out", source_port="cold_out"))
    add(edge("e_cond2_e2", "hx_cond2", "sep_E2", source_port="hot_out"))
    add(edge("e_e2_benzene", "sep_E2", "sink_benzene"))
    add(edge("e_k2_pv2", "column_K2", "valve_PV2", source_port="distillate"))
    add(edge("e_pv2_vap", "valve_PV2", "sink_vapour"))

    # K-2 bottoms -> pump H-4 -> stripping columns K-3/1..3
    add(edge("e_k2_h4", "column_K2", "pump_H4", source_port="bottoms"))
    add(edge("e_h4_k31", "pump_H4", "column_K31"))

    # K-3/1: kerosene cut -> K-12 demercaptanization ; residue -> K-3/2
    add(edge("e_k31_fv13", "column_K31", "valve_FV13", source_port="distillate"))
    add(edge("e_fv13_reactor", "valve_FV13", "reactor_K124"))
    add(edge("e_reactor_k12", "reactor_K124", "column_K12"))
    add(edge("e_k31_k32", "column_K31", "column_K32", source_port="bottoms"))
    add(edge("e_k32_diesel", "column_K32", "sink_diesel", source_port="distillate"))
    add(edge("e_k32_k33", "column_K32", "column_K33", source_port="bottoms"))
    add(edge("e_k33_gasoil", "column_K33", "sink_gasoil", source_port="distillate"))
    add(edge("e_k33_fuel", "column_K33", "sink_fuel_oil", source_port="bottoms"))

    # K-12 demercaptanization: stripped -> C-1K separator -> product
    add(edge("e_k12_c1k", "column_K12", "sep_C1K", source_port="distillate"))
    add(edge("e_k12_product", "column_K12", "sink_kerosene", source_port="bottoms"))
    add(edge("e_c1k_product", "sep_C1K", "sink_kerosene"))

    # K-4 stabilizer: PBF overhead -> condenser -> E-3 ; bottoms -> P-3 -> K-9
    add(edge("e_k4_cond4", "column_K4", "hx_cond4", source_port="distillate", target_port="hot_in"))
    add(edge("e_cw_cond4", "src_cw", "hx_cond4", target_port="cold_in", kind="cooling"))
    add(edge("e_cond4_cw", "hx_cond4", "sink_cw_out", source_port="cold_out"))
    add(edge("e_cond4_e3", "hx_cond4", "sep_E3", source_port="hot_out"))
    add(edge("e_e3_stabgas", "sep_E3", "sink_stabgas"))
    add(edge("e_k4_pv4", "column_K4", "valve_PV4", source_port="distillate"))
    add(edge("e_pv4_stabgas", "valve_PV4", "sink_vapour"))
    add(edge("e_k4_p3", "column_K4", "furnace_P3", source_port="bottoms"))
    add(edge("e_p3_k9", "furnace_P3", "column_K9"))

    # K-9: overhead NK-62 -> condenser -> E-18 ; bottoms -> P-4a -> K-10
    add(edge("e_naphtha_r13", "src_naphtha", "tank_R13"))
    add(edge("e_r13_k9", "tank_R13", "column_K9"))
    add(edge("e_k9_fv12", "column_K9", "valve_FV12", source_port="distillate"))
    add(edge("e_fv12_cond9", "valve_FV12", "hx_cond9", target_port="hot_in"))
    add(edge("e_cw_cond9", "src_cw", "hx_cond9", target_port="cold_in", kind="cooling"))
    add(edge("e_cond9_cw", "hx_cond9", "sink_cw_out", source_port="cold_out"))
    add(edge("e_cond9_e18", "hx_cond9", "sep_E18", source_port="hot_out"))
    add(edge("e_e18_62", "sep_E18", "sink_62"))
    add(edge("e_k9_p4a", "column_K9", "furnace_P4a", source_port="bottoms"))
    add(edge("e_p4a_k10", "furnace_P4a", "column_K10"))

    # K-10: overhead 62-105 -> condenser -> E-17 ; bottoms -> P-4b -> product
    add(edge("e_k10_fv11", "column_K10", "valve_FV11", source_port="distillate"))
    add(edge("e_fv11_cond10", "valve_FV11", "hx_cond10", target_port="hot_in"))
    add(edge("e_cw_cond10", "src_cw", "hx_cond10", target_port="cold_in", kind="cooling"))
    add(edge("e_cond10_cw", "hx_cond10", "sink_cw_out", source_port="cold_out"))
    add(edge("e_cond10_e17", "hx_cond10", "sep_E17", source_port="hot_out"))
    add(edge("e_e17_105", "sep_E17", "sink_105"))
    add(edge("e_k10_h58", "column_K10", "pump_H58", source_port="bottoms"))
    add(edge("e_h58_p4b", "pump_H58", "furnace_P4b"))
    add(edge("e_p4b_105_180", "furnace_P4b", "sink_105_180"))

    return scheme


if __name__ == "__main__":
    scheme = build_scheme()
    path = save_scheme(scheme, ROOT / "schemes" / "process_elou_avt.json")
    print(f"Generated {path}")
    print(f"  nodes: {len(scheme.nodes)}")
    print(f"  edges: {len(scheme.edges)}")
