"""
smoke_test.py
=============
Run the full ELOU-AVT scheme end-to-end and report stability, key process
values and active alarms. Exits non-zero if simulation throws or if
unexpected alarms are active during normal operation.

Run from the project root (elou_avt_twin):
    python -m tools.smoke_test [steps]
"""

import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.base import SimulationConfig
from simulation_core.digital_twin import DigitalTwin
from scheme.model import load_scheme

SCHEME_PATH = ROOT / "schemes" / "process_elou_avt.json"


def main() -> int:
    steps = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    scheme = load_scheme(SCHEME_PATH)
    print(f"Scheme: {scheme.id} — {len(scheme.nodes)} nodes, {len(scheme.edges)} edges")

    twin = DigitalTwin(SimulationConfig(dt=1.0, random_seed=42))
    twin.create_simulation()
    twin._engine.set_scheme(scheme)
    twin._engine.set_feed_override({"flow_kg_s": 100.0, "temperature_c": 25.0, "pressure_bar": 1.01325})
    twin.load_scenario("NORMAL_OPERATION")
    twin.start()

    t0 = time.perf_counter()
    try:
        for _ in range(steps):
            twin.step(1.0)
    except Exception:
        print("SIMULATION FAILED:")
        traceback.print_exc()
        return 1
    dt = time.perf_counter() - t0

    st = twin.get_state()
    print(f"\nRan {steps} steps in {dt:.2f}s ({dt / steps * 1000:.1f} ms/step)")
    print(f"time={st.timestamp:.0f}s  feed_flow={st.feed_flow:.2f} kg/s  product={st.product_flow:.2f} kg/s")

    eng = twin._engine
    outputs = eng.get_last_outputs()
    streams = eng.get_last_streams()

    print("\n-- Columns --")
    for nid, node in eng._node_map.items():
        if node.type != "column":
            continue
        out = outputs.get(nid, {})
        dist, bott = out.get("distillate"), out.get("bottoms")
        tp = dist.temperature - 273.15 if dist else float("nan")
        tb = bott.temperature - 273.15 if bott else float("nan")
        dp = dist.pressure / 1e5 if dist else float("nan")
        lev = st.level.get(nid, float("nan"))
        print(f"  {nid:14s} P={dp:6.2f} bar  Ttop={tp:6.1f} C  Tbot={tb:6.1f} C  level={lev:5.2f} m  "
              f"D={dist.mass_flow:6.2f} B={bott.mass_flow:6.2f} kg/s  conv={out.get('converged')}")

    print("\n-- Heaters --")
    for nid, node in eng._node_map.items():
        if node.type != "heater":
            continue
        out = outputs.get(nid, {})
        s = out.get("outlet_stream")
        t_out = s.temperature - 273.15 if s else float("nan")
        print(f"  {nid:14s} Tout={t_out:6.1f} C  duty={out.get('duty', 0) / 1e6:7.2f} MW")

    print("\n-- ELOU / separators (levels) --")
    for nid, node in eng._node_map.items():
        if node.type in ("elou", "separator"):
            s = streams.get(f"{nid}:out")
            p = s.pressure / 1e5 if s else float("nan")
            print(f"  {nid:14s} P={p:6.2f} bar  level={st.level.get(nid, float('nan')):5.2f} m")

    alarms = twin.get_alarms()
    print(f"\n-- Active alarms: {len(alarms)} --")
    for a in alarms:
        print(f"  {a.parameter}: {a.description} [{a.severity.value}]")

    unexpected = [a for a in alarms if a.severity.value in ("HIGH", "CRITICAL")]
    print(f"\nUnexpected HIGH/CRITICAL alarms during normal operation: {len(unexpected)}")
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
