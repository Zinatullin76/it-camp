import sys
sys.path.insert(0, ".")
import numpy as np
from calculation_core.thermodynamics.pr_eos import PengRobinsonThermodynamics
from calculation_core.thermodynamics.fractions import FRACTION_COMPONENTS, HYDROCARBON_FRACTIONS
from models.stream import Phase

th = PengRobinsonThermodynamics(FRACTION_COMPONENTS)

crude = {
    "frac_nk62": 0.06, "frac_62_105": 0.08, "frac_105_180": 0.14,
    "frac_180_240": 0.15, "frac_240_300": 0.13, "frac_300_350": 0.10,
    "frac_mazut": 0.22, "water": 0.08, "salt": 0.04,
}
print("=== fractions properties ===")
for c, d in FRACTION_COMPONENTS.items():
    print(f"{c:16s} MW={d['molar_mass']:6.4f} Tc={d['tc']:7.1f} Pc={d['pc']/1e5:6.2f}bar om={d['omega']:5.3f}")

print("\n=== density ===")
print("liquid crude @300K:", round(th.calculate_density(300, 101325, crude, Phase.LIQUID), 1))
print("vapor crude @550K :", round(th.calculate_density(550, 101325, crude, Phase.VAPOR), 4))

print("\n=== flash ===")
for T in (300, 380, 450, 550, 650, 750):
    beta, x, y = th.calculate_vle(T, 101325, crude)
    print(f"T={T} beta={beta:6.3f} y_nk62={y.get('frac_nk62',0):.4f} x_mazut={x.get('frac_mazut',0):.4f}")

print("\n=== enthalpy ===")
for T in (300, 400, 500, 600, 700):
    h = th.calculate_enthalpy(T, 101325, crude)
    print(f"T={T} H={h/1000:9.2f} kJ/kg  T_from_H={th.temperature_from_enthalpy(h, 101325, crude):.1f}")

print("\n=== latent heat across boiling ===")
h_liq_550 = th.calculate_enthalpy(550, 101325, crude, Phase.LIQUID)
h_vap_550 = th.calculate_enthalpy(550, 101325, crude, Phase.VAPOR)
print(f"at 550K: H_liq={h_liq_550/1000:.1f} kJ/kg  H_vap={h_vap_550/1000:.1f} kJ/kg  latent={ (h_vap_550-h_liq_550)/1000:.1f} kJ/kg")

print("\n=== K values ===")
names, z = th._to_molar(crude)
k = th.k_values(560, 101325, names, z)
for n, kv in zip(names, k):
    print(f"  K({n:14s}) = {kv:.4f}")

print("\n=== bubble/dew ===")
x = z.copy()
Tb = th.bubble_temperature(101325, names, x)
Td = th.dew_temperature(101325, names, x)
print("bubble T:", round(Tb, 2), " dew T:", round(Td, 2))

print("\n=== single component sanity: water ===")
w = {"water": 1.0}
for T in (298, 373, 400, 500):
    beta, x, y = th.calculate_vle(T, 101325, w)
    print(f"water T={T} beta={beta:.3f}")

print("\n=== salt nonvolatile ===")
comp = {"frac_mazut": 0.5, "water": 0.4, "salt": 0.1}
beta, x, y = th.calculate_vle(420, 101325, comp)
print(f"beta={beta:.3f} y_salt={y.get('salt',0):.2e}")
print("OK")
