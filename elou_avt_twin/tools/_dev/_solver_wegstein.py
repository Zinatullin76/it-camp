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

def wegstein_run(T0, x0, use_accel, omega, n_iter):
    T = T0.copy()
    x = x0.copy()
    y = x0.copy()
    Tn_prev = np.zeros(n); T_prev2 = np.zeros(n); Tn_prev2 = np.zeros(n)
    Tn = np.zeros(n)
    for it in range(n_iter):
        K = thermo.k_values_wilson_vec(T, np.full(n,s.pressure), s.names)
        y = np.clip(K*x,1e-30,None); y=y/np.maximum(np.sum(y,axis=1,keepdims=True),1e-30)
        hL = thermo.stage_enthalpy_molar_vec(T, np.full(n,s.pressure), x, s.names, s._phase_liq())
        hV = thermo.stage_enthalpy_molar_vec(T, np.full(n,s.pressure), y, s.names, s._phase_vap())
        L,V,B = s._march(T,x,y,hL,hV,F,hFj,R,D,F_mol)
        x = s._solve_m(L,V,K,F,z)
        Tn = thermo.bubble_temperature_vec(np.full(n,s.pressure), s.names, x)
        if it == 0:
            T = omega*T + (1-omega)*Tn
        elif use_accel:
            denom = Tn_prev - Tn_prev2 + 1e-9*np.sign(Tn_prev - Tn_prev2 + 1e-12)
            denom = np.where(np.abs(Tn_prev - Tn_prev2) > 1e-6, Tn_prev - Tn_prev2, 1.0)
            sl = (T - T_prev2) / denom
            q = sl / (sl - 1.0)
            q = np.clip(q, -5.0, 5.0)
            T = T + q * (Tn - T)
        else:
            T = omega*T + (1-omega)*Tn
        dr = float(np.max(np.abs(Tn - T)))
        Tn_prev2 = Tn_prev; Tn_prev = Tn.copy()
        T_prev2 = T.copy()
        if dr < 0.05:
            return it+1, dr, T
    return n_iter, dr, T

for accel, omega, niter in [(False, 0.3, 40), (False, 0.4, 40), (False, 0.5, 40)]:
    iters, dr, _ = wegstein_run(T_warm, x, accel, omega, niter)
    print(f"warm accel={accel} omega={omega}: converged in {iters} iters, final dr={dr:.5f}")

# cold start (feed composition init, no warm profile): feed bubble linear guess
Tf0 = thermo.bubble_temperature_vec(np.array([s.pressure]), s.names, z_feed[None, :])[0]
cut0 = [c for c in s.names if s.components[c].get('nbp', 1e9) < Tf0]
ci0 = [i for i, c in enumerate(s.names) if c in cut0]
Dz0 = np.zeros(nc); Dz0[ci0] = z_feed[ci0]; Dz0 = Dz0 / Dz0.sum()
Bz0 = z_feed.copy(); Bz0[ci0] = 0.0; Bz0 = Bz0 / Bz0.sum()
T_cold = np.linspace(thermo.bubble_temperature_vec(np.array([s.pressure]), s.names, Dz0[None, :])[0],
                     thermo.bubble_temperature_vec(np.array([s.pressure]), s.names, Bz0[None, :])[0], n)
for omega in [0.3, 0.4, 0.5]:
    iters, dr, _ = wegstein_run(T_cold, np.tile(z_feed, (n, 1)).astype(float), False, omega, 60)
    print(f"cold omega={omega}: converged in {iters} iters, final dr={dr:.5f}")
