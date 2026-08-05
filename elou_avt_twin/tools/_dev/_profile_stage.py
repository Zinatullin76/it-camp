import sys, time
sys.path.insert(0, ".")
import numpy as np
from models.stream import Stream
from calculation_core.thermodynamics.pr_eos import PengRobinsonThermodynamics
from calculation_core.thermodynamics.fractions import FRACTION_COMPONENTS

thermo = PengRobinsonThermodynamics(FRACTION_COMPONENTS)
n = 28
names = list(thermo.data.keys())
rng = np.random.default_rng(1)
T = rng.uniform(380, 580, n)
P = np.full(n, 196133.0)
X = rng.dirichlet(np.ones(len(names)), size=n)
Y = rng.dirichlet(np.ones(len(names)), size=n)
from models.stream import Phase

for label, fn in [
    ("wilson_k", lambda: thermo.k_values_wilson_vec(T, P, names)),
    ("bubble60", lambda: thermo.bubble_temperature_vec(P, names, X)),
    ("hL", lambda: thermo.stage_enthalpy_molar_vec(T, P, X, names, Phase.LIQUID)),
    ("hV", lambda: thermo.stage_enthalpy_molar_vec(T, P, Y, names, Phase.VAPOR)),
]:
    fn()
    t0 = time.perf_counter()
    for _ in range(200):
        fn()
    print(f"{label}: {(time.perf_counter()-t0)*1e3/200:.3f} ms")
