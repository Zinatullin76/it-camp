import sys
sys.path.insert(0, ".")
import numpy as np
from calculation_core.thermodynamics.pr_eos import PengRobinsonThermodynamics
from calculation_core.thermodynamics.fractions import FRACTION_COMPONENTS
from models.stream import Phase

th = PengRobinsonThermodynamics(FRACTION_COMPONENTS)
crude = {
    "frac_nk62": 0.06, "frac_62_105": 0.08, "frac_105_180": 0.14,
    "frac_180_240": 0.15, "frac_240_300": 0.13, "frac_300_350": 0.10,
    "frac_mazut": 0.22, "water": 0.08, "salt": 0.04,
}

print("=== liquid enthalpy inversion (heater preheat path) ===")
for T in (300.0, 350.0, 400.0, 450.0, 500.0, 550.0, 600.0):
    h = th.calculate_enthalpy(T, 101325, crude, Phase.LIQUID)
    t_back = th.temperature_from_enthalpy(h, 101325, crude, Phase.LIQUID)
    print(f"T={T:6.1f} H_liq={h/1000:8.2f} kJ/kg -> invert T={t_back:6.1f}")

print("\n=== monotonic check: dH/dT over 300..700 ===")
prev = None
for T in range(300, 701, 25):
    h = th.calculate_enthalpy(T, 101325, crude, Phase.LIQUID)
    if prev is not None:
        assert h > prev, f"non-monotonic at {T}"
    prev = h
print("liquid H monotonic OK")

print("\n=== flash consistency: H(flash) vs H(L)+H(V) weighted ===")
T = 420.0
beta, x_m, y_m = th.calculate_vle(T, 101325, crude)
names_l, x = th._to_molar(x_m)
names_v, y = th._to_molar(y_m)
h_liq = th.phase_enthalpy_molar(T, 101325, names_l, x, Phase.LIQUID) / th._mean_mw(names_l, x)
h_vap = th.phase_enthalpy_molar(T, 101325, names_v, y, Phase.VAPOR) / th._mean_mw(names_v, y)
h_auto = th.calculate_enthalpy(T, 101325, crude)
h_mix = beta * h_vap + (1 - beta) * h_liq
print(f"beta={beta:.3f} H_auto={h_auto/1000:.2f} H_mix={h_mix/1000:.2f} diff={abs(h_auto-h_mix)/1000:.3f} kJ/kg")

print("\n=== bubble point: sum(K*x)=1 check ===")
names, x = th._to_molar(crude)
Tb = th.bubble_temperature(101325, names, x)
k = th.k_values(Tb, 101325, names, x)
print(f"Tb={Tb:.2f} sum(K*x)={np.sum(k*x):.5f}")

print("\n=== water liquid density ===")
print("water @ 300K, 3bar:", round(th.calculate_density(300, 3e5, {"water": 1.0}, Phase.LIQUID), 1))
print("crude @ 300K:", round(th.calculate_density(300, 101325, crude, Phase.LIQUID), 1))
print("OK")
