import sys
sys.path.insert(0, ".")
import numpy as np
from calculation_core.thermodynamics.pr_eos import (
    PengRobinsonThermodynamics, _a_i, _b_i, _alpha, _z_roots, R_GAS, _OMEGA_A, _OMEGA_B)
from calculation_core.thermodynamics.fractions import FRACTION_COMPONENTS
from models.stream import Phase

th = PengRobinsonThermodynamics(FRACTION_COMPONENTS)
T, P = 560.0, 101325.0
names = ["frac_mazut"]
z = np.array([1.0])

tc = FRACTION_COMPONENTS["frac_mazut"]["tc"]
pc = FRACTION_COMPONENTS["frac_mazut"]["pc"]
omega = FRACTION_COMPONENTS["frac_mazut"]["omega"]
print("Tc", tc, "Pc", pc, "omega", omega)
a_i = _a_i(pc, tc)
b_i = _b_i(pc, tc)
alpha = _alpha(T, tc, omega)
a = a_i * alpha
b = b_i
print("a_i", a_i, "b_i", b_i, "alpha", alpha, "a", a, "b", b)
A = a * P / (R_GAS ** 2 * T ** 2)
B = b * P / (R_GAS * T)
print("A", A, "B", B)
z_liq, z_vap = _z_roots(A, B)
print("z_liq", z_liq, "z_vap", z_vap)

Z, A2, B2 = th._z_for_phase(T, P, names, z, Phase.LIQUID)
print("from _z_for_phase LIQUID: Z", Z, "A", A2, "B", B2)
Z, A2, B2 = th._z_for_phase(T, P, names, z, Phase.VAPOR)
print("from _z_for_phase VAPOR:  Z", Z, "A", A2, "B", B2)
