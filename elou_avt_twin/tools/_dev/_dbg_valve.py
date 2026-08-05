"""Verify valve closure logic: upstream dead-heading + back-pressure rise."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from models.base import SimulationConfig
from simulation_core.digital_twin import DigitalTwin
from scheme.model import load_scheme


def flows(twin):
    o = twin._engine.get_last_outputs()
    s = twin._engine.get_last_streams()
    def get(nid):
        out = o.get(nid, {})
        return {
            "flow": out.get("flow_out", s.get(f"{nid}:out").mass_flow if s.get(f"{nid}:out") else 0.0),
            "p_in": out.get("inlet_pressure", 0.0),
            "p_out": out.get("outlet_pressure", 0.0),
        }
    return {n: get(n) for n in ["src_feed", "tank_R11", "pump_H1", "valve_FV1", "elou_1"]}


def run(actions, steps=15):
    twin = DigitalTwin(SimulationConfig(dt=1.0, random_seed=42))
    twin.create_simulation()
    eng = twin._engine
    eng.set_scheme(load_scheme(ROOT / "schemes" / "process_elou_avt.json"))
    eng.set_feed_override({"flow_kg_s": 100.0, "temperature_c": 25.0, "pressure_bar": 1.01325})
    twin.load_scenario("NORMAL_OPERATION")
    twin.start()
    for _ in range(40):
        twin.step(1.0)
    for eid, atype, val in actions:
        eng._equipment[eid].apply_action(atype, val)
    for _ in range(steps):
        twin.step(1.0)
    return twin, flows(twin)


print("== steady state (valve open, position 0.6) ==")
_, f = run([])
for n, v in f.items():
    print(f"  {n:12s} flow={v['flow']:8.3f}  P_in={v['p_in']/1e5:6.3f}  P_out={v['p_out']/1e5:6.3f}")

print("\n== partially closed FV1 (position -> 0.3) ==")
_, f = run([("valve_FV1", "SET_VALUE", 0.3)])
for n, v in f.items():
    print(f"  {n:12s} flow={v['flow']:8.3f}  P_in={v['p_in']/1e5:6.3f}  P_out={v['p_out']/1e5:6.3f}")

print("\n== fully closed FV1 (position -> 0.0) ==")
twin, f = run([("valve_FV1", "SET_VALUE", 0.0)])
for n, v in f.items():
    print(f"  {n:12s} flow={v['flow']:8.3f}  P_in={v['p_in']/1e5:6.3f}  P_out={v['p_out']/1e5:6.3f}")

print("\n== open again (position -> 0.6), recovery ==")
eng = twin._engine
eng._equipment["valve_FV1"].apply_action("SET_VALUE", 0.6)
for _ in range(25):
    twin.step(1.0)
f = flows(twin)
for n, v in f.items():
    print(f"  {n:12s} flow={v['flow']:8.3f}  P_in={v['p_in']/1e5:6.3f}  P_out={v['p_out']/1e5:6.3f}")
