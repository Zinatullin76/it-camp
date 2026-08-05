"""
check_quality.py
================
Validation of the calculation core quality and the operator-action reaction:

  1. Baseline stability  (300 steps, no false HIGH/CRITICAL alarms)
  2. Column convergence  (conv flag true every step)
  3. Overall mass balance (feed vs sum of product sinks)
  4. Performance          (ms/step)
  5. /input feed override -> flows follow
  6. /action SET_VALUE fuel on furnace -> outlet temperature follows, monotonic
  7. /action on valve / pump -> downstream flow reacts
  8. /failure on pump / furnace / valve -> physically sensible degradation

Run:  python -m tools.check_quality
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.base import SimulationConfig, OperatorAction, ActionType
from simulation_core.digital_twin import DigitalTwin
from calculation_core.thermodynamics.fractions import HYDROCARBON_FRACTIONS
from scheme.model import load_scheme

SCHEME_PATH = ROOT / "schemes" / "process_elou_avt.json"

RES = []  # (name, ok, detail)


def record(name, ok, detail=""):
    RES.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}  {detail}")


def fresh_twin():
    scheme = load_scheme(SCHEME_PATH)
    twin = DigitalTwin(SimulationConfig(dt=1.0, random_seed=42))
    twin.create_simulation()
    twin._engine.set_scheme(scheme)
    twin._engine.set_feed_override({"flow_kg_s": 100.0, "temperature_c": 25.0, "pressure_bar": 1.01325})
    twin.load_scenario("NORMAL_OPERATION")
    twin.start()
    return twin


def run(twin, steps):
    for _ in range(steps):
        twin.step(1.0)


def act(twin, equipment_id, action_type, value=None):
    twin.apply_operator_action(OperatorAction(
        timestamp=twin._simulation_time, operator_id="tester",
        equipment_id=equipment_id, action_type=action_type,
        new_value=value, source="validation"))
    twin.step(1.0)


def fail(twin, equipment_id, mode="MECHANICAL_FAILURE"):
    twin.inject_failure(equipment_id, mode)
    twin.step(1.0)


def temp_of(twin, node_id):
    out = twin._engine.get_last_outputs().get(node_id, {})
    s = out.get("outlet_stream") or out.get("distillate") or out.get("bottoms")
    return (s.temperature - 273.15) if s else float("nan")


def flow_of(twin, node_id, key="outlet_stream"):
    out = twin._engine.get_last_outputs().get(node_id, {})
    s = out.get(key)
    return s.mass_flow if s else float("nan")


def press_of(twin, node_id, key="outlet_stream"):
    out = twin._engine.get_last_outputs().get(node_id, {})
    s = out.get(key)
    return (s.pressure / 1e5) if s else float("nan")


def column_conv(twin):
    out = twin._engine.get_last_outputs()
    return all(o.get("converged", True) for nid, o in out.items()
               if twin._engine._node_map[nid].type == "column")


def main() -> int:
    print("=" * 72)
    print("QUALITY CHECK: calculation core + operator reaction")
    print("=" * 72)

    # ---------------------------------------------------------- baseline
    twin = fresh_twin()
    t0 = time.perf_counter()
    run(twin, 300)
    dt = time.perf_counter() - t0
    st = twin.get_state()
    alarms = twin.get_alarms()
    bad = [a for a in alarms if a.severity.value in ("HIGH", "CRITICAL")]
    record("baseline 300 steps no crash", True, f"{dt:.1f}s total, {dt/300*1000:.1f} ms/step")
    record("no false HIGH/CRITICAL alarms", len(bad) == 0,
           f"{len(alarms)} alarms total" if len(alarms) else "0 alarms")
    record("all columns converged", column_conv(twin))
    nan_nodes = [nid for nid in twin._engine._node_map
                 for o in twin._engine.get_last_outputs().get(nid, {}).values()
                 if isinstance(o, float) and o != o]
    record("no NaN in outputs", len(nan_nodes) == 0, f"nan nodes: {nan_nodes[:5]}")

    # --------------------------------------------------- mass balance
    # Hydrocarbon balance: HC inputs (feed + naphtha + gas) vs HC products
    # (sinks excluding utility loops: cooling water, vapour, brine, hot return).
    # The crude feed is only ~88% hydrocarbon — the water/salt cut is removed
    # by the ELOU units, so the feed's HC mass (not its gross flow) is counted.
    nm = twin._engine._node_map
    streams = twin._engine.get_last_streams()
    utility_sinks = {"sink_cw_out", "sink_vapour", "sink_brine", "sink_hot_ret"}
    feed = streams.get("src_feed:out")
    feed_hc = 0.0
    if feed is not None:
        feed_hc = feed.mass_flow * sum(
            feed.composition.get(c, 0.0) for c in HYDROCARBON_FRACTIONS
        )
    hc_srcs = ["src_naphtha", "src_gas"]
    hc_in = feed_hc + sum(streams[f"{nid}:out"].mass_flow for nid in hc_srcs
                          if streams.get(f"{nid}:out"))
    prod = 0.0
    for nid in (n for n, nd in nm.items() if nd.type == "sink" and n not in utility_sinks):
        for edge in twin._engine._scheme.edges:
            if edge.target == nid:
                s = streams.get(f"{edge.source}:{edge.source_port}")
                if s:
                    prod += s.mass_flow
    rel = abs(prod - hc_in) / max(hc_in, 1e-6)
    record("hydrocarbon mass balance", rel < 0.02,
           f"HC in={hc_in:.2f} products={prod:.2f} rel_err={rel:.3%}")

    # ---------------------------------------------------- levels bounded
    lev = st.level
    bad_lev = [k for k, v in lev.items() if not (-1.0 < v < 15.0)]
    record("levels bounded", len(bad_lev) == 0, f"{len(lev)} levels, outliers: {bad_lev[:5]}")
    for k in sorted(lev):
        print(f"      level {k:14s} = {lev[k]:6.2f} m")

    # -------------------------------------------------------- /input
    # Temperature override must propagate through preheat/furnace/columns.
    t_p1 = temp_of(twin, "furnace_P1")
    twin._engine.set_feed_override({"flow_kg_s": 100.0, "temperature_c": 60.0})
    run(twin, 120)
    t_p1_hot = temp_of(twin, "furnace_P1")
    record("feed T override 25 -> 60 C raises P-1 outlet", t_p1_hot > t_p1 + 5.0,
           f"P-1 out {t_p1:.1f} -> {t_p1_hot:.1f} C")
    # Flow override must raise throughput (currently capped by valve FV-1).
    lev0 = twin.get_state().level.get("tank_R11")
    twin._engine.set_feed_override({"flow_kg_s": 150.0})
    run(twin, 120)
    st2 = twin.get_state()
    fv1_out = twin._engine.get_last_streams().get("valve_FV1:out")
    lev1 = st2.level.get("tank_R11")
    fv1_flow = fv1_out.mass_flow if fv1_out else float("nan")
    record("feed flow override 100 -> 150 raises throughput",
           fv1_flow > 120.0 or (lev1 > lev0 + 0.05),
           f"valve_FV1 out={fv1_flow:.2f} kg/s (was 104.96), tank_R11 level {lev0:.2f} -> {lev1:.2f} m")
    twin._engine.set_feed_override({"flow_kg_s": 100.0, "temperature_c": 25.0})
    run(twin, 60)

    # ------------------------------------------------- /action furnace
    t_before = temp_of(twin, "furnace_P1")
    act(twin, "furnace_P1", ActionType.SET_VALUE, 1.5)
    run(twin, 30)
    t_hi = temp_of(twin, "furnace_P1")
    act(twin, "furnace_P1", ActionType.SET_VALUE, 0.1)
    run(twin, 30)
    t_lo = temp_of(twin, "furnace_P1")
    record("fuel+ raises P-1 outlet T", t_hi > t_before, f"{t_before:.1f} -> {t_hi:.1f} C")
    record("fuel- lowers P-1 outlet T", t_lo < t_hi, f"{t_hi:.1f} -> {t_lo:.1f} C")
    duty = twin._engine.get_last_outputs().get("furnace_P1", {}).get("duty", 0.0)
    record("furnace duty follows fuel", duty < 30e6, f"duty after reduction = {duty/1e6:.2f} MW")

    # ------------------------------------------------- /action valve
    f_before = flow_of(twin, "valve_FV13")
    act(twin, "valve_FV13", ActionType.SET_VALUE, 0.05)
    run(twin, 20)
    f_after = flow_of(twin, "valve_FV13")
    record("closing FV-13 lowers its flow", f_after < f_before,
           f"{f_before:.3f} -> {f_after:.3f} kg/s")
    act(twin, "valve_FV13", ActionType.SET_VALUE, 0.8)
    run(twin, 20)

    # ------------------------------------------- valve position sweep
    # Closing must cut flow AND raise the throttling pressure drop (outlet
    # pressure falls) — not keep a constant 0.1 bar drop for every position.
    act(twin, "valve_FV13", ActionType.SET_VALUE, 1.0)
    run(twin, 20)
    f_open = flow_of(twin, "valve_FV13")
    p_open = press_of(twin, "valve_FV13")
    act(twin, "valve_FV13", ActionType.SET_VALUE, 0.3)
    run(twin, 20)
    f_closed = flow_of(twin, "valve_FV13")
    p_closed = press_of(twin, "valve_FV13")
    record("closing FV-13 to 0.3 cuts flow", f_closed < f_open * 0.7,
           f"{f_open:.2f} -> {f_closed:.2f} kg/s")
    record("closing FV-13 raises throttling drop", p_closed < p_open - 0.2,
           f"P_out {p_open:.3f} -> {p_closed:.3f} bar (dP no longer fixed 0.1)")
    act(twin, "valve_FV13", ActionType.SET_VALUE, 0.8)
    run(twin, 20)

    # ---------------------------------------------------- /action pump
    act(twin, "pump_H2", ActionType.TURN_OFF)
    run(twin, 20)
    f_p1 = flow_of(twin, "furnace_P1")
    record("H-2 OFF starves P-1 feed", f_p1 < 0.5,
           f"furnace_P1 inlet after pump trip = {f_p1:.3f} kg/s")
    act(twin, "pump_H2", ActionType.TURN_ON)
    run(twin, 40)

    # ------------------------------------------------------- /failure
    f1 = fresh_twin()
    run(f1, 100)
    pre_duty = f1._engine.get_last_outputs()["furnace_P1"]["duty"]
    fail(f1, "furnace_P1")
    run(f1, 60)
    post_duty = f1._engine.get_last_outputs()["furnace_P1"]["duty"]
    record("failure P-1 cuts duty", post_duty < pre_duty * 0.01,
           f"duty {pre_duty/1e6:.2f} -> {post_duty/1e6:.2f} MW (heater ignores failed state)")
    t_p1 = temp_of(f1, "furnace_P1")
    record("failure P-1 recorded active", any("furnace_P1" in f for f in f1.get_state().active_failures),
           f"active_failures={f1.get_state().active_failures}")

    f2 = fresh_twin()
    run(f2, 100)
    pre = flow_of(f2, "pump_H2")
    fail(f2, "pump_H2")
    run(f2, 20)
    post = flow_of(f2, "pump_H2")
    record("failure H-2 stops flow", post < 0.5, f"pump flow {pre:.2f} -> {post:.2f} kg/s")
    record("failure H-2 recorded active", any("pump_H2" in f for f in f2.get_state().active_failures))

    f3 = fresh_twin()
    run(f3, 100)
    pos_pre = f3._engine._equipment["valve_FV13"].position
    fail(f3, "valve_FV13")
    run(f3, 15)
    act(f3, "valve_FV13", ActionType.SET_VALUE, 0.9)
    run(f3, 30)
    pos_post = f3._engine._equipment["valve_FV13"].position
    record("failure FV-13 sticks valve (action ignored)",
           abs(pos_post - pos_pre) < 0.01, f"position {pos_pre:.2f} -> {pos_post:.2f}")

    # -------------------------------------------------- stability after disturbances
    run(twin, 100)
    al = twin.get_alarms()
    record("system stable after all actions", len(al) <= 2,
           f"alarms now: {[a.parameter for a in al][:5]}")

    # ------------------------------------------------------------ score
    print("=" * 72)
    failed = [r for r in RES if not r[1]]
    print(f"RESULT: {len(RES)-len(failed)}/{len(RES)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
