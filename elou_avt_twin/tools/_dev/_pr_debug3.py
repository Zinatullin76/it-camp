import sys
sys.path.insert(0, ".")
import numpy as np
from calculation_core.thermodynamics.pr_eos import (
    PengRobinsonThermodynamics, _a_i, _b_i, _alpha, _z_roots, R_GAS)
from calculation_core.thermodynamics.fractions import FRACTION_COMPONENTS
from models.stream import Phase

th = PengRobinsonThermodynamics(FRACTION_COMPONENTS)
T, P = 560.0, 101325.0
names = ["frac_mazut"]
z = np.array([1.0])

nc = 1
Z, A, B = th._z_for_phase(T, P, names, z, Phase.LIQUID)
print("Z", Z, "A", A, "B", B)
tc = np.array([th.data[c]["tc"] for c in names], dtype=float)
pc = np.array([th.data[c]["pc"] for c in names], dtype=float)
omega = np.array([th.data[c]["omega"] for c in names], dtype=float)
a_i = _a_i(pc, tc)
b_i = _b_i(pc, tc)
alpha = np.array([_alpha(T, tci, om) for tci, om in zip(tc, omega)])
a = a_i * alpha
b = float(np.sum(z * b_i))
sqrt_a = np.sqrt(a)
print("a", a, "b", b)
am = float(np.sum(z * sqrt_a) ** 2) if nc > 1 else a[0]
denom = Z + (1.0 - np.sqrt(2.0)) * B
num = Z + (1.0 + np.sqrt(2.0)) * B
pref = A / (2.0 * np.sqrt(2.0) * B) * np.log(abs(num / denom))
i = 0
ai_sum = 2.0 * np.sqrt(a[i]) * float(np.sum(z * sqrt_a)) if nc > 1 else 2.0 * a[i] * z[i]
lnphi = b_i[i] / b * (Z - 1.0) - np.log(abs(Z - B)) - pref * (ai_sum / am - b_i[i] / b)
print("bracket (ai_sum/am - b_i/b) =", ai_sum / am - b_i[i] / b)
print("pref =", pref)
print("lnphi =", lnphi, " phi =", np.exp(lnphi))
