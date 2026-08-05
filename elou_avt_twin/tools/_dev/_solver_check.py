import sys, time
sys.path.insert(0, ".")
import numpy as np
from models.stream import Stream, Phase
from calculation_core.thermodynamics.pr_eos import PengRobinsonThermodynamics
from calculation_core.thermodynamics.fractions import FRACTION_COMPONENTS
from calculation_core.solver.mesh_solver import DistillationSolver

thermo = PengRobinsonThermodynamics(FRACTION_COMPONENTS)

feed = Stream(
    name="feed",
    temperature=523.0,
    pressure=196133.0,
    mass_flow=100.0,
    composition={
        "frac_nk62": 0.02, "frac_62_105": 0.04, "frac_105_180": 0.10,
        "frac_180_240": 0.13, "frac_240_300": 0.12, "frac_300_350": 0.10,
        "frac_mazut": 0.45, "water": 0.03, "salt": 0.01,
    },
)

t0 = time.perf_counter()
solver = DistillationSolver(28, 16, thermo, pressure=196133.0)
res = solver.solve(feed, reflux_ratio=2.0, boilup_ratio=1.5, n_iter=50, tol=1e-3)
dt = time.perf_counter() - t0

print("converged:", res["converged"], "iters:", res["temperature_iterations"])
print(f"time: {dt*1000:.1f} ms   energy_res_max: {res['energy_residual_max']:.3e} W")
print("T top/bot: %.1f / %.1f K" % (res["T_profile"][0], res["T_profile"][-1]))
D, B = res["distillate_molar"], res["bottoms_molar"]
print(f"D={D:.3f} mol/s B={B:.3f} mol/s D+B={D+B:.3f} vs F")
print("distillate mass:", {k: round(v, 3) for k, v in res["distillate_comp_mass"].items()})
print("bottoms mass:", {k: round(v, 3) for k, v in res["bottoms_comp_mass"].items()})
print("Q_cond: %.2f MW  Q_reb: %.2f MW" % (res["condenser_duty"]/1e6, res["reboiler_duty"]/1e6))

feed2 = feed.copy_with(temperature=525.0, mass_flow=102.0)
t0 = time.perf_counter()
res2 = solver.solve(feed2, reflux_ratio=2.0, boilup_ratio=1.5, n_iter=15, tol=1e-3,
                    T_guess=np.asarray(res["T_profile"]))
dt2 = time.perf_counter() - t0
print("\nwarm start: converged:", res2["converged"], "iters:", res2["temperature_iterations"],
      f"time: {dt2*1000:.1f} ms")
