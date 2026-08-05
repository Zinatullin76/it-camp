import sys, time
sys.path.insert(0, ".")
import numpy as np
from calculation_core.thermodynamics.pr_eos import PengRobinsonThermodynamics
from calculation_core.thermodynamics.fractions import FRACTION_COMPONENTS

th = PengRobinsonThermodynamics(FRACTION_COMPONENTS)
crude = {
    "frac_nk62": 0.06, "frac_62_105": 0.08, "frac_105_180": 0.14,
    "frac_180_240": 0.15, "frac_240_300": 0.13, "frac_300_350": 0.10,
    "frac_mazut": 0.22, "water": 0.08, "salt": 0.04,
}
names, z = th._to_molar(crude)

print("=== Wilson vs PR K at various T ===")
for T in (340, 376, 420, 480, 560, 650):
    kw = th.k_values_wilson(T, 101325, names)
    kp = th.k_values(T, 101325, names, z)
    print(f"T={T}: sum(Wilson*x)={np.sum(kw*z):.3f}  sum(PR*x)={np.sum(kp*z):.3f}")

print("\n=== PR bubble point ===")
def pb(rigorous):
    return th.bubble_temperature(101325, names, z, rigorous=rigorous)
print("Wilson-bubble:", round(pb(False), 2), " PR-bubble:", round(pb(True), 2))

print("\n=== benchmark: PR k_values per stage ===")
n_stages = 30
t0 = time.perf_counter()
for j in range(n_stages):
    th.k_values(340 + j * 10, 101325, names, z)
dt = time.perf_counter() - t0
print(f"{n_stages} PR k_values calls: {dt*1000:.1f} ms ({dt/n_stages*1000:.2f} ms each)")

print("\n=== benchmark: flash_molar ===")
t0 = time.perf_counter()
for j in range(60):
    th.flash_molar(400 + j, 101325, names, z)
dt = time.perf_counter() - t0
print(f"60 flashes: {dt*1000:.1f} ms ({dt/60*1000:.2f} ms each)")

print("\n=== benchmark: bubble_temperature rigorous ===")
t0 = time.perf_counter()
for j in range(20):
    th.bubble_temperature(101325, names, z, rigorous=True)
dt = time.perf_counter() - t0
print(f"20 rigorous bubble points: {dt*1000:.1f} ms ({dt/20*1000:.2f} ms each)")

print("\n=== benchmark: phase_enthalpy_molar ===")
t0 = time.perf_counter()
for j in range(30):
    th.phase_enthalpy_molar(500, 101325, names, z, None)  # wrong signature? just measure liquid
dt = time.perf_counter() - t0
print(f"30 liquid enthalpies: {dt*1000:.1f} ms")
