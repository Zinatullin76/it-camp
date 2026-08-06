"""Debug branched hydraulics on the fork scheme (schemes/default.json)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent.parent))

from models.base import SimulationConfig
from simulation_core.digital_twin import DigitalTwin
from scheme.model import load_scheme


def flows(eng):
    o = eng.get_last_outputs()
    s = eng.get_last_streams()

    def get(nid):
        out = o.get(nid, {})
        return {
            "flow": out.get("flow_out", s.get(f"{nid}:out").mass_flow if s.get(f"{nid}:out") else 0.0),
            "p_in": out.get("inlet_pressure", 0.0),
            "p_out": out.get("outlet_pressure", 0.0),
        }

    return {n: get(n) for n in ["source_1", "pum_2", "val_1", "val_3", "val_4", "val_5"]}


def run(actions, steps=20):
    twin = DigitalTwin(SimulationConfig(dt=1.0, random_seed=42))
    twin.create_simulation()
    eng = twin._engine
    eng.set_scheme(load_scheme(ROOT.parent.parent / "schemes" / "default.json"))
    eng.set_feed_override({"flow_kg_s": 53.0, "temperature_c": 40.0, "pressure_bar": 1.0132})
    twin.load_scenario("NORMAL_OPERATION")
    twin.start()
    for _ in range(40):
        twin.step(1.0)
    for eid, atype, val in actions:
        eng._equipment[eid].apply_action(atype, val)
    for _ in range(steps):
        twin.step(1.0)
    return twin, flows(eng)


def show(title, f):
    print(title)
    total = 0.0
    for n, v in f.items():
        total += v["flow"]
        print(f"  {n:10s} flow={v['flow']:9.3f}  P_in={v['p_in']/1e5:6.3f}  P_out={v['p_out']/1e5:6.3f}")
    print(f"  {'sum':10s} flow={total:9.3f}")


print("== pump OFF, valves closed (dead-head check) ==")
_, f = run([])
show("", f)

print("\n== pump ON, all valves OPEN (position 1.0) ==")
_, f = run([("pum_2", "TURN_ON", None)] + [(n, "SET_VALUE", 1.0) for n in ["val_1", "val_3", "val_4", "val_5"]])
show("", f)

print("\n== pump ON, val_1 throttled to 0.4 ==")
_, f = run([("pum_2", "TURN_ON", None)] + [(n, "SET_VALUE", 1.0) for n in ["val_3", "val_4", "val_5"]] + [("val_1", "SET_VALUE", 0.4)])
show("", f)

print("\n== pump ON, val_4 closed 0.0 (fork branch blocked) ==")
_, f = run([("pum_2", "TURN_ON", None)] + [(n, "SET_VALUE", 1.0) for n in ["val_1", "val_3", "val_5"]] + [("val_4", "SET_VALUE", 0.0)])
show("", f)
