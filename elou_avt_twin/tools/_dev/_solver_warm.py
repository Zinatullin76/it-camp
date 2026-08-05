import sys
sys.path.insert(0, ".")
import numpy as np
from models.stream import Stream
from calculation_core.thermodynamics.pr_eos import PengRobinsonThermodynamics
from calculation_core.thermodynamics.fractions import FRACTION_COMPONENTS
from calculation_core.solver.mesh_solver import DistillationSolver

thermo = PengRobinsonThermodynamics(FRACTION_COMPONENTS)
feed = Stream(name='f', temperature=523.0, pressure=196133.0, mass_flow=100.0,
              composition={'frac_nk62': 0.02, 'frac_62_105': 0.04, 'frac_105_180': 0.10,
                           'frac_180_240': 0.13, 'frac_240_300': 0.12, 'frac_300_350': 0.10,
                           'frac_mazut': 0.45, 'water': 0.03, 'salt': 0.01})
s = DistillationSolver(28, 16, thermo, pressure=196133.0)
res = s.solve(feed, reflux_ratio=2.0, n_iter=50, tol=1e-3)
T_warm = np.asarray(res["T_profile"])

feed2 = feed.copy_with(temperature=525.0, mass_flow=102.0)
n, nc, f = s.n, s.nc, s.f
from calculation_core.solver.mesh_solver import _MIN_FLOW
F_mol, z_feed, mean_m, hF = s._feed_molar(feed2)
F = np.zeros(n); F[f-1] = F_mol
z = np.zeros((n, nc)); z[f-1] = z_feed
hFj = np.zeros(n); hFj[f-1] = hF
Tf = thermo.bubble_temperature_vec(np.array([s.pressure]), s.names, z_feed[None,:])[0]
cut = [c for c in s.names if s.components[c].get('nbp',1e9) < Tf]
ci = [i for i,c in enumerate(s.names) if c in cut]
D = float(np.clip(F_mol*np.sum(z_feed[ci]),1e-6,F_mol-1e-6))
R=2.0
Vtop=(R+1)*D; Ltop=R*D
L=np.full(n,Ltop); V=np.full(n,Vtop)
T = T_warm.copy()
x = np.tile(z_feed,(n,1)).astype(float); y=x.copy()
omega=0.6
for it in range(15):
    K = thermo.k_values_wilson_vec(T, np.full(n,s.pressure), s.names)
    y = np.clip(K*x,1e-30,None); y=y/np.maximum(np.sum(y,axis=1,keepdims=True),1e-30)
    hL = thermo.stage_enthalpy_molar_vec(T, np.full(n,s.pressure), x, s.names, s._phase_liq())
    hV = thermo.stage_enthalpy_molar_vec(T, np.full(n,s.pressure), y, s.names, s._phase_vap())
    L,V,B = s._march(T,x,y,hL,hV,F,hFj,R,D,F_mol)
    x = s._solve_m(L,V,K,F,z)
    Tn = thermo.bubble_temperature_vec(np.full(n,s.pressure), s.names, x)
    dr = float(np.max(np.abs(Tn-T)))
    T = omega*T + (1-omega)*Tn
    print(f"it {it}: raw={dr:.5f} T0={T[0]:.3f} Tn0={Tn[0]:.3f} Tbot={T[-1]:.3f}")
    if dr < 0.05:
        print("CONVERGED", it); break
