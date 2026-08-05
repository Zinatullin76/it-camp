import numpy as np
from calculation_core.thermodynamics.pr_eos import PengRobinsonThermodynamics
from calculation_core.thermodynamics.fractions import FRACTION_COMPONENTS
from calculation_core.thermodynamics.base import Phase

names = list(FRACTION_COMPONENTS.keys())
thermo = PengRobinsonThermodynamics(FRACTION_COMPONENTS)

rng = np.random.default_rng(7)
n = 37
T = rng.uniform(300, 650, n)
P = rng.uniform(5e4, 2e6, n)
Z = rng.dirichlet(np.ones(len(names)), size=n)

Hl_vec = thermo.stage_enthalpy_molar_vec(T, P, Z, names, Phase.LIQUID)
Hv_vec = thermo.stage_enthalpy_molar_vec(T, P, Z, names, Phase.VAPOR)

Hl_scl = np.array([thermo.phase_enthalpy_molar(T[j], P[j], names, Z[j], Phase.LIQUID) for j in range(n)])
Hv_scl = np.array([thermo.phase_enthalpy_molar(T[j], P[j], names, Z[j], Phase.VAPOR) for j in range(n)])

print("liquid max abs diff:", np.max(np.abs(Hl_vec - Hl_scl)))
print("vapor  max abs diff:", np.max(np.abs(Hv_vec - Hv_scl)))

Tb = thermo.bubble_temperature_vec(P, names, Z)
print("bubble temps sample:", np.round(Tb[:5], 2), "... range", round(Tb.min(), 2), round(Tb.max(), 2))

Kw = thermo.k_values_wilson_vec(T, P, names)
print("K shape:", Kw.shape, "salt col:", Kw[:, -1][:3])

import time
t0 = time.perf_counter()
for _ in range(100):
    Hl_vec = thermo.stage_enthalpy_molar_vec(T, P, Z, names, Phase.LIQUID)
    Hv_vec = thermo.stage_enthalpy_molar_vec(T, P, Z, names, Phase.VAPOR)
    Tb = thermo.bubble_temperature_vec(P, names, Z)
t1 = time.perf_counter()
print(f"100 x (2 enthalpies+1 bubble for {n} stages): {(t1-t0)*1e3:.1f} ms total, {(t1-t0)*1e3/100:.2f} ms per call set")
