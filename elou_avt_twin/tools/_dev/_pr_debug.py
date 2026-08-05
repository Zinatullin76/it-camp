import sys
sys.path.insert(0, ".")
import numpy as np
from calculation_core.thermodynamics.pr_eos import (
    PengRobinsonThermodynamics, _a_i, _b_i, _alpha, _z_roots)
from calculation_core.thermodynamics.fractions import FRACTION_COMPONENTS
from models.stream import Phase

th = PengRobinsonThermodynamics(FRACTION_COMPONENTS)
T, P = 560.0, 101325.0

names = ["frac_mazut", "frac_240_300", "frac_nk62", "water", "salt"]
z = np.array([0.4, 0.25, 0.15, 0.15, 0.05])

print("=== pure mazut ===")
phi_l = th._fugacity_coeff(T, P, ["frac_mazut"], np.array([1.0]), Phase.LIQUID)
phi_v = th._fugacity_coeff(T, P, ["frac_mazut"], np.array([1.0]), Phase.VAPOR)
print("phi_L", phi_l, "phi_V", phi_v, "K", phi_l[0]/phi_v[0])

print("=== pure nk62 ===")
phi_l = th._fugacity_coeff(T, P, ["frac_nk62"], np.array([1.0]), Phase.LIQUID)
phi_v = th._fugacity_coeff(T, P, ["frac_nk62"], np.array([1.0]), Phase.VAPOR)
print("phi_L", phi_l, "phi_V", phi_v, "K", phi_l[0]/phi_v[0])

print("=== mixture (z=%s) ===" % z)
phi_l = th._fugacity_coeff(T, P, names, z, Phase.LIQUID)
phi_v = th._fugacity_coeff(T, P, names, z, Phase.VAPOR)
print("phi_L", phi_l)
print("phi_V", phi_v)
print("K    ", phi_l / phi_v)

am, b, dam, a = th._mixing(names, z, T)
print("am", am, "b", b)
sqrt_a = np.sqrt(a)
print("a_i", a)
print("am2 (dot)", float(np.sum(z*np.sqrt(a))**2))
