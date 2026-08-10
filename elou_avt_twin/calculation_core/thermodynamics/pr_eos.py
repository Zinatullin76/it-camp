"""
pr_eos.py
=========
Peng-Robinson equation of state based thermodynamics for the ELOU-AVT twin.

Replaces the ideal-Raoult/Antoine MVP model with a physical EOS:
  - K-values from fugacity ratios (phi_L / phi_V), composition and pressure
    dependent — no Raoult assumption.
  - Enthalpy = ideal-gas enthalpy (polynomial Cp) + PR residual enthalpy
    (includes latent heat of vaporisation, so phase change is energetically
    correct).
  - Densities from the PR molar volume.
  - PT-flash: stability checks for single-phase branches + Rachford-Rice with
    successive-substitution K update.

The public interface mirrors calculation_core.thermodynamics.base
(ThermodynamicModel) so existing equipment / engine code keeps working, plus
extra molar-based methods used by the rigorous column solver.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple

from models.stream import Phase
from calculation_core.thermodynamics.base import ThermodynamicModel

R_GAS = 8.314462618

# PR constants
_OMEGA_A = 0.4572355289
_OMEGA_B = 0.0777960739


# ---------------------------------------------------------------------------
# Cubic root helpers (Cardano / trigonometric)
# ---------------------------------------------------------------------------

def _z_roots(A: float, B: float) -> Tuple[Optional[float], Optional[float]]:
    """Return (Z_liq, Z_vap) real roots of the PR cubic in Z.

    Z^3 - (1-B) Z^2 + (A - 3B^2 - 2B) Z - (AB - B^2 - B^3) = 0
    Z_liq is the smallest real root, Z_vap the largest.
    """
    p = -1.0 + B
    q = A - 3.0 * B * B - 2.0 * B
    r = -(A * B - B * B - B ** 3)

    # Depressed cubic: t^3 + P t + Q = 0 with t = Z - p/3
    P = q - p * p / 3.0
    Q = 2.0 * p ** 3 / 27.0 - p * q / 3.0 + r
    disc = (P / 3.0) ** 3 + (Q / 2.0) ** 2

    if disc > 0.0:
        s1 = np.cbrt(-Q / 2.0 + np.sqrt(disc))
        s2 = np.cbrt(-Q / 2.0 - np.sqrt(disc))
        z = s1 + s2 - p / 3.0
        return (z, z) if z > 0 else (None, z)
    # Three real roots -> trigonometric method
    if P >= 0.0:
        return (None, None)
    phi = np.arccos(np.clip(-Q / 2.0 / np.sqrt((-P / 3.0) ** 3), -1.0, 1.0))
    fac = 2.0 * np.sqrt(-P / 3.0)
    z1 = fac * np.cos(phi / 3.0) - p / 3.0
    z2 = fac * np.cos((phi + 2.0 * np.pi) / 3.0) - p / 3.0
    z3 = fac * np.cos((phi + 4.0 * np.pi) / 3.0) - p / 3.0
    roots = np.array([z1, z2, z3])
    roots = roots[np.isfinite(roots)]
    if roots.size == 0:
        return (None, None)
    z_vap = float(np.max(roots))
    z_liq = float(np.min(roots[roots > 0])) if np.any(roots > 0) else z_vap
    return (z_liq, z_vap)


# ---------------------------------------------------------------------------
# Component property access
# ---------------------------------------------------------------------------

def _a_i(pc: float, tc: float) -> float:
    return _OMEGA_A * R_GAS ** 2 * tc ** 2 / pc


def _b_i(pc: float, tc: float) -> float:
    return _OMEGA_B * R_GAS * tc / pc


def _alpha(t: float, tc: float, omega: float) -> float:
    kappa = 0.37464 + 1.54226 * omega - 0.26992 * omega ** 2
    sqrt_alpha = 1.0 + kappa * (1.0 - np.sqrt(max(t / tc, 1e-6)))
    return sqrt_alpha * sqrt_alpha


def _dalpha_dt(t: float, tc: float, omega: float) -> float:
    kappa = 0.37464 + 1.54226 * omega - 0.26992 * omega ** 2
    tr = max(t / tc, 1e-6)
    sqrt_alpha = 1.0 + kappa * (1.0 - np.sqrt(tr))
    return -kappa * sqrt_alpha / np.sqrt(t * tc)


class PengRobinsonThermodynamics(ThermodynamicModel):
    """Peng-Robinson EOS thermodynamics over fractional pseudo-components."""

    def __init__(self, components_data: Dict[str, Dict]):
        self.data = components_data
        self.R = R_GAS
        self.T_REF = 298.15
        self._param_cache: Dict[Tuple[str, ...], Dict[str, np.ndarray]] = {}
        # Small per-instance cache for repeated enthalpy evaluations. A plain
        # dict avoids the global lifetime/self-retention behaviour of
        # functools.lru_cache on bound methods, which matters in long-running
        # training sessions that create many thermodynamic model instances.
        self._enthalpy_cache: Dict[Tuple[float, float, Tuple[Tuple[str, float], ...], str], float] = {}
        self._enthalpy_cache_limit = 1024

    # -- component / composition helpers ------------------------------------

    def _names(self, composition: Dict[str, float]) -> List[str]:
        names = [c for c in composition if composition.get(c, 0.0) > 0]
        unknown = [c for c in names if c not in self.data]
        if unknown:
            raise ValueError(
                f"Unknown component(s) in composition: {unknown}. "
                f"Known components: {sorted(self.data.keys())}. "
                f"Unknown components are not given fake default properties."
            )
        return names

    def _to_molar(self, composition: Dict[str, float]) -> Tuple[List[str], np.ndarray]:
        names = self._names(composition)
        if not names:
            return [], np.zeros(0)
        w = np.array([composition[c] for c in names], dtype=float)
        m = np.array([self.data[c]["molar_mass"] for c in names], dtype=float)
        z = w / m
        s = np.sum(z)
        return names, (z / s if s > 0 else z)

    def _to_mass(self, names: List[str], z_molar: np.ndarray) -> Dict[str, float]:
        m = np.array([self.data[c]["molar_mass"] for c in names], dtype=float)
        w = z_molar * m
        s = np.sum(w)
        return {c: float(v) for c, v in zip(names, w / s)} if s > 0 else {c: 0.0 for c in names}

    def _mean_mw(self, names: List[str], z_molar: np.ndarray) -> float:
        m = np.array([self.data[c]["molar_mass"] for c in names], dtype=float)
        return float(np.sum(z_molar * m))

    def _param_block(self, names: List[str]) -> Dict[str, np.ndarray]:
        """Cached per-component EOS parameter arrays for a fixed name list.

        The component dictionary is immutable in practice, so the derived
        arrays (a_i, b_i, kappa, cp coefficients, ...) are computed once per
        name-list and reused by the hot kernels instead of being rebuilt from
        dict lookups on every stage call.
        """
        key = tuple(names)
        block = self._param_cache.get(key)
        if block is None:
            tc = np.array([self.data[c]["tc"] for c in names], dtype=float)
            pc = np.array([self.data[c]["pc"] for c in names], dtype=float)
            omega = np.array([self.data[c]["omega"] for c in names], dtype=float)
            kappa = 0.37464 + 1.54226 * omega - 0.26992 * omega ** 2
            a_i = _OMEGA_A * R_GAS ** 2 * tc ** 2 / pc
            b_i = _OMEGA_B * R_GAS * tc / pc
            mm = np.array([self.data[c]["molar_mass"] for c in names], dtype=float)
            cp_a = np.array([self.data[c]["cp_a"] for c in names], dtype=float)
            cp_b = np.array([self.data[c]["cp_b"] for c in names], dtype=float)
            volatile = np.array(
                [self.data[c].get("volatile", True) for c in names], dtype=bool
            )
            block = {
                "tc": tc, "pc": pc, "omega": omega, "kappa": kappa,
                "a_i": a_i, "b_i": b_i, "mm": mm, "cp_a": cp_a,
                "cp_b": cp_b, "volatile": volatile,
            }
            self._param_cache[key] = block
        return block

    # -- EOS kernels ---------------------------------------------------------

    def _mixing(self, names: List[str], z: np.ndarray, t: float):
        nc = len(names)
        if nc == 0:
            return 0.0, 0.0, 0.0, 0.0
        pb = self._param_block(names)
        tr = np.maximum(t / pb["tc"], 1e-6)
        sqrt_alpha = 1.0 + pb["kappa"] * (1.0 - np.sqrt(tr))
        alpha = sqrt_alpha ** 2
        a = pb["a_i"] * alpha
        da = pb["a_i"] * (-pb["kappa"] * sqrt_alpha / np.sqrt(t * pb["tc"]))
        sqrt_a = np.sqrt(a)
        b = float(np.sum(z * pb["b_i"]))
        # am and dam are algebraically reduced from the O(nc^2) double sum:
        #   am  = (sum_i z_i sqrt(a_i))^2
        #   dam = (sum_i z_i sqrt(a_i)) * (sum_i z_i da_i / sqrt(a_i))
        S_sa = float(np.sum(z * sqrt_a))
        S_da = float(np.sum(z * da / np.maximum(np.sqrt(a), 1e-30)))
        am = S_sa * S_sa
        dam = S_sa * S_da
        return am, b, dam, a

    def _z_for_phase(self, t: float, p: float, names: List[str], z: np.ndarray, phase: Phase):
        am, b, _, _ = self._mixing(names, z, t)
        A = am * p / (R_GAS ** 2 * t ** 2)
        B = b * p / (R_GAS * t)
        z_liq, z_vap = _z_roots(A, B)
        if phase == Phase.VAPOR or phase == Phase.TWO_PHASE:
            if z_vap is not None and z_vap > 0:
                return z_vap, A, B
        if z_liq is not None and z_liq > 0:
            return z_liq, A, B
        if z_vap is not None and z_vap > 0:
            return z_vap, A, B
        return 1.0, A, B

    def _fugacity_coeff(self, t: float, p: float, names: List[str], z: np.ndarray, phase: Phase) -> np.ndarray:
        nc = len(names)
        Z, A, B = self._z_for_phase(t, p, names, z, phase)
        if nc == 0:
            return np.zeros(0)
        pb = self._param_block(names)
        tr = np.maximum(t / pb["tc"], 1e-6)
        alpha = (1.0 + pb["kappa"] * (1.0 - np.sqrt(tr))) ** 2
        a = pb["a_i"] * alpha
        b_i = pb["b_i"]
        b = float(np.sum(z * b_i))
        sqrt_a = np.sqrt(a)
        am = float(np.sum(z * sqrt_a) ** 2) if nc > 1 else a[0]
        num = Z + (1.0 + np.sqrt(2.0)) * B
        denom = Z + (1.0 - np.sqrt(2.0)) * B
        pref = A / (2.0 * np.sqrt(2.0) * B) * np.log(max(abs(num / denom), 1e-30))
        lnphi = np.empty(nc)
        for i in range(nc):
            bij = 0.5 * (b_i[i] + b)
            ai_sum = 2.0 * np.sqrt(a[i]) * float(np.sum(z * sqrt_a)) if nc > 1 else 2.0 * a[i] * z[i]
            lnphi[i] = b_i[i] / b * (Z - 1.0) - np.log(max(abs(Z - B), 1e-30)) \
                - pref * (ai_sum / max(am, 1e-30) - b_i[i] / max(b, 1e-30))
        return np.exp(lnphi)

    # -- enthalpies ----------------------------------------------------------

    def _ideal_gas_h(self, names: List[str], z: np.ndarray, t: float) -> float:
        """Ideal-gas enthalpy above T_REF [J/mol]."""
        pb = self._param_block(names)
        return float(np.sum(
            z * (pb["cp_a"] * (t - self.T_REF) + 0.5 * pb["cp_b"] * (t ** 2 - self.T_REF ** 2))
        ))

    def _residual_h(self, t: float, p: float, names: List[str], z: np.ndarray, phase: Phase) -> float:
        """PR residual enthalpy [J/mol]."""
        am, b, dam, _ = self._mixing(names, z, t)
        A = am * p / (R_GAS ** 2 * t ** 2)
        B = b * p / (R_GAS * t)
        Z, _, _ = self._z_for_phase(t, p, names, z, phase)
        if B < 1e-15:
            return 0.0
        num = Z + (1.0 + np.sqrt(2.0)) * B
        denom = Z + (1.0 - np.sqrt(2.0)) * B
        log_term = np.log(max(abs(num / denom), 1e-30))
        h_res = R_GAS * t * (Z - 1.0) + (t * dam - am) / (2.0 * np.sqrt(2.0) * b) * log_term
        return float(h_res)

    def phase_enthalpy_molar(self, t: float, p: float, names: List[str], z: np.ndarray, phase: Phase) -> float:
        """Total molar enthalpy [J/mol] of one phase (ideal gas + residual)."""
        return self._ideal_gas_h(names, z, t) + self._residual_h(t, p, names, z, phase)

    # -- Public interface (matches ThermodynamicModel) ------------------------

    def calculate_enthalpy(self, T: float, P: float, composition: Dict[str, float], phase: Optional[Phase] = None) -> float:
        """Specific enthalpy [J/kg] of a stream at T,P (auto phase if None).

        Thermodynamic calls are a hot path: the same T/P/composition tuple is
        evaluated repeatedly by heat exchangers and hydraulic iterations.  The
        immutable cache key below avoids re-running the PR flash for identical
        states while keeping the public API dict-based.
        """
        names, z = self._to_molar(composition)
        if not names:
            return 0.0
        phase_value = phase.value if isinstance(phase, Phase) else (phase or "AUTO")
        key = (float(T), float(P), tuple(sorted((str(k), float(v)) for k, v in composition.items())), phase_value)
        cached = self._enthalpy_cache.get(key)
        if cached is not None:
            return cached
        value = self._calculate_enthalpy_uncached(key[0], key[1], key[2], key[3])
        if len(self._enthalpy_cache) >= self._enthalpy_cache_limit:
            # FIFO eviction is deterministic and cheap; thermodynamic states
            # in a simulation are strongly localized, so a tiny cache is enough.
            self._enthalpy_cache.pop(next(iter(self._enthalpy_cache)))
        self._enthalpy_cache[key] = value
        return value

    def _calculate_enthalpy_uncached(
        self, T: float, P: float, composition_key: Tuple[Tuple[str, float], ...], phase_value: str
    ) -> float:
        """Non-cached implementation of :meth:`calculate_enthalpy`."""
        composition = dict(composition_key)
        names, z = self._to_molar(composition)
        phase = None if phase_value == "AUTO" else Phase(phase_value)
        if phase is None or phase == Phase.TWO_PHASE:
            beta, x, y = self.flash_molar(T, P, names, z)
            if beta <= 0.0:
                h = self.phase_enthalpy_molar(T, P, names, x, Phase.LIQUID)
            elif beta >= 1.0:
                h = self.phase_enthalpy_molar(T, P, names, y, Phase.VAPOR)
            else:
                h_liq = self.phase_enthalpy_molar(T, P, names, x, Phase.LIQUID)
                h_vap = self.phase_enthalpy_molar(T, P, names, y, Phase.VAPOR)
                h = beta * h_vap + (1.0 - beta) * h_liq
        elif phase == Phase.VAPOR:
            h = self.phase_enthalpy_molar(T, P, names, z, Phase.VAPOR)
        else:
            h = self.phase_enthalpy_molar(T, P, names, z, Phase.LIQUID)
        mw = self._mean_mw(names, z)
        return h / max(mw, 1e-6)

    def temperature_from_enthalpy(self, H: float, P: float, composition: Dict[str, float],
                                  phase: Phase = Phase.LIQUID) -> float:
        """Invert calculate_enthalpy to find T for a target enthalpy [J/kg]."""
        lo, hi = 200.0, 1200.0
        f_lo = self.calculate_enthalpy(lo, P, composition, phase) - H
        f_hi = self.calculate_enthalpy(hi, P, composition, phase) - H
        if f_lo >= 0.0:
            return lo
        if f_hi <= 0.0:
            return hi
        # Newton with the ideal-gas molar Cp as the slope.  The residual part
        # of the enthalpy varies slowly with T, so within a single phase the
        # ideal-gas slope is a good estimate of dH/dT and Newton converges in
        # a handful of evaluate calls instead of up to 80 bisection samples.
        # Non-convergence (e.g. a kink at a flash boundary) falls back to the
        # original bisection so results never change.
        names, z = self._to_molar(composition)
        pb = self._param_block(names)
        mw = float(np.sum(z * pb["mm"]))
        T = 0.5 * (lo + hi)
        for _ in range(12):
            f = self.calculate_enthalpy(T, P, composition, phase) - H
            if abs(f) < 1e-6:
                return T
            slope = float(np.sum(z * (pb["cp_a"] + pb["cp_b"] * T))) / max(mw, 1e-6)
            if abs(slope) < 1e-9:
                break
            T_new = T - f / slope
            if not (lo <= T_new <= hi):
                break
            if abs(T_new - T) < 1e-6:
                return T_new
            T = T_new
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            f_mid = self.calculate_enthalpy(mid, P, composition, phase) - H
            if abs(f_mid) < 1e-6:
                return mid
            if f_lo * f_mid < 0.0:
                hi = mid
            else:
                lo, f_lo = mid, f_mid
        return 0.5 * (lo + hi)

    def calculate_cp(self, T: float, P: float, composition: Dict[str, float], phase: Optional[Phase] = None) -> float:
        """Specific heat capacity [J/(kg*K)] via finite difference of enthalpy."""
        if phase is None:
            names, z = self._to_molar(composition)
            if not names:
                return 0.0
            beta, x, y = self.flash_molar(T, P, names, z)
            phase = Phase.VAPOR if beta >= 1.0 else Phase.LIQUID
        d = 0.5
        h_lo = self.calculate_enthalpy(T - d, P, composition, phase)
        h_hi = self.calculate_enthalpy(T + d, P, composition, phase)
        return (h_hi - h_lo) / (2.0 * d)

    def calculate_density(self, T: float, P: float, composition: Dict[str, float], phase: Phase = Phase.LIQUID) -> float:
        """Density [kg/m^3].

        Liquid: SG-based with thermal expansion (realistic, PR volumes are not
        volume-translated and under-predict liquids by 10-20%).
        Vapor: PR molar volume.
        """
        names, z = self._to_molar(composition)
        if not names:
            return 850.0
        if phase is None or phase == Phase.TWO_PHASE:
            beta, x, y = self.flash_molar(T, P, names, z)
            phase = Phase.VAPOR if beta >= 1.0 else Phase.LIQUID
        if phase == Phase.VAPOR:
            Z, _, _ = self._z_for_phase(T, P, names, z, phase)
            mw = self._mean_mw(names, z)
            v_mol = Z * R_GAS * T / P
            return mw / max(v_mol, 1e-12)
        # Liquid density from composition-averaged SG + thermal expansion
        sg = sum(z[i] * self.data[c].get("sg", 0.85) for i, c in enumerate(names))
        rho_ref = sg * 1000.0
        alpha = 0.0008
        return max(100.0, rho_ref * (1.0 - alpha * (T - 288.15)))

    def calculate_vle(self, T: float, P: float, composition: Dict[str, float]) -> Tuple[float, Dict[str, float], Dict[str, float]]:
        """PT-flash -> (vapor_fraction, x_mass, y_mass)."""
        names, z = self._to_molar(composition)
        if not names:
            return 0.0, {}, {}
        beta, x, y = self.flash_molar(T, P, names, z)
        return float(beta), self._to_mass(names, x), self._to_mass(names, y)

    # -- K-values ------------------------------------------------------------

    def k_values_wilson(self, T: float, P: float, names: List[str]) -> np.ndarray:
        """Composition-independent Wilson K for robust column initialisation."""
        self._require_names(names)
        k = np.empty(len(names))
        for i, c in enumerate(names):
            d = self.data[c]
            if not d.get("volatile", True):
                k[i] = 1e-10
            else:
                k[i] = (d["pc"] / P) * np.exp(5.42 * (1.0 + d["omega"]) * (1.0 - d["tc"] / T))
        return np.clip(k, 1e-10, 1e10)

    def _require_names(self, names: List[str]) -> None:
        """Raise a clear ValueError for component ids with no property data."""
        unknown = [c for c in names if c not in self.data]
        if unknown:
            raise ValueError(
                f"Unknown component(s): {unknown}. Known components: "
                f"{sorted(self.data.keys())}. Unknown components are not given "
                f"fake default properties."
            )

    def k_values(self, T: float, P: float, names: List[str], z_molar: np.ndarray) -> np.ndarray:
        """PR fugacity-ratio K values: K_i = phi_i(L) / phi_i(V).

        Components flagged ``volatile=False`` (e.g. salt) are forced to stay in
        the liquid: their K is pinned to 1e-10 regardless of the PR fugacity
        ratio, because their pseudo-critical properties (Tc/Pc) are not
        meaningful in the vapour phase.
        """
        phi_l = self._fugacity_coeff(T, P, names, z_molar, Phase.LIQUID)
        phi_v = self._fugacity_coeff(T, P, names, z_molar, Phase.VAPOR)
        k = np.where(np.abs(phi_v) > 1e-30, phi_l / np.maximum(phi_v, 1e-30), 1e-10)
        k = np.clip(k, 1e-10, 1e10)
        k[self._nonvolatile_mask(names)] = 1e-10
        return k

    def _nonvolatile_mask(self, names: List[str]) -> np.ndarray:
        """Boolean mask of components that must never enter the vapour phase."""
        return np.array(
            [not self.data[c].get("volatile", True) for c in names], dtype=bool
        )

    # -- Flash ---------------------------------------------------------------

    def _rr(self, beta: float, z: np.ndarray, k: np.ndarray) -> float:
        denom = 1.0 + beta * (k - 1.0)
        return float(np.sum(z * (k - 1.0) / np.maximum(denom, 1e-30)))

    def _bracket_rr(self, z: np.ndarray, k: np.ndarray):
        f0 = self._rr(0.0, z, k)
        f1 = self._rr(1.0, z, k)
        if f0 <= 0.0:
            return 0.0
        if f1 >= 0.0:
            return 1.0
        lo, hi = 0.0, 1.0
        flo = f0
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            fmid = self._rr(mid, z, k)
            if abs(fmid) < 1e-9:
                return mid
            if flo * fmid < 0.0:
                hi = mid
            else:
                lo, flo = mid, fmid
        return 0.5 * (lo + hi)

    def flash_molar(self, T: float, P: float, names: List[str], z: np.ndarray,
                    n_ss: int = 3) -> Tuple[float, np.ndarray, np.ndarray]:
        """Rachford-Rice PT-flash returning (beta, x_molar, y_molar).

        Successive substitution on fugacity-ratio K with Wilson initialisation
        makes the result consistent with the PR EOS.
        """
        z = np.asarray(z, dtype=float)
        if z.size == 0:
            return 0.0, z, z
        self._require_names(names)
        k = self.k_values_wilson(T, P, names)
        # Single-phase stability checks on the Wilson K
        if float(np.sum(z * k)) <= 1.0:
            return 0.0, z, z.copy()
        if float(np.sum(z / np.maximum(k, 1e-30))) <= 1.0:
            return 1.0, z.copy(), z
        for _ in range(n_ss + 1):
            beta = self._bracket_rr(z, k)
            x = z / np.maximum(1.0 + beta * (k - 1.0), 1e-30)
            x = x / np.sum(x)
            y = k * x
            y = y / np.sum(y)
            k_new = self.k_values(T, P, names, x)
            # clamp so it stays a valid two-phase direction
            if float(np.sum(z * k_new)) <= 1.0:
                break
            k = np.clip(k_new, 1e-10, 1e10)
        beta = self._bracket_rr(z, k)
        x = z / np.maximum(1.0 + beta * (k - 1.0), 1e-30)
        x = x / np.sum(x)
        y = k * x
        y = y / np.sum(y)
        return float(beta), x, y

    # -- Column solver helpers ------------------------------------------------

    def bubble_temperature(self, P: float, names: List[str], x_molar: np.ndarray,
                           rigorous: bool = False) -> float:
        """Stage bubble point: T with sum(K_i x_i) = 1.

        The bisection is anchored on a grid scan: the PR fugacity K flattens
        to exactly 1.0 above the critical point (single real root of the
        cubic), so a naive monotonic-search guard would jump to the range top.
        Instead the first negative->positive sign crossing is bracketed.
        """
        x = np.asarray(x_molar, dtype=float)
        if x.size == 0:
            return 300.0

        def f(T: float) -> float:
            if rigorous:
                k = self.k_values(T, P, names, x)
            else:
                k = self.k_values_wilson(T, P, names)
            return float(np.sum(k * x)) - 1.0

        lo, hi = 200.0, 1200.0
        grid = np.linspace(lo, hi, 61)
        fvals = [f(float(t)) for t in grid]
        idx = next((i for i, fv in enumerate(fvals) if fv > 1e-12), None)
        if idx is None:
            # No point with f > 0 in range: all-liquid everywhere.
            return lo if fvals[0] >= 0.0 else hi
        if idx == 0:
            return lo
        a, b = float(grid[idx - 1]), float(grid[idx])
        fa, fb = fvals[idx - 1], fvals[idx]
        for _ in range(80):
            mid = 0.5 * (a + b)
            f_mid = f(mid)
            if abs(f_mid) < 1e-9:
                return mid
            if f_mid > 0.0:
                b, fb = mid, f_mid
            else:
                a, fa = mid, f_mid
        return 0.5 * (a + b)

    def dew_temperature(self, P: float, names: List[str], y_molar: np.ndarray,
                        rigorous: bool = False) -> float:
        y = np.asarray(y_molar, dtype=float)
        if y.size == 0:
            return 300.0

        def f(T: float) -> float:
            if rigorous:
                k = self.k_values(T, P, names, y)
            else:
                k = self.k_values_wilson(T, P, names)
            return float(np.sum(y / np.maximum(k, 1e-30))) - 1.0

        # f decreases with T; the dew point is the first >0 -> <0 crossing.
        lo, hi = 200.0, 1200.0
        grid = np.linspace(lo, hi, 61)
        fvals = [f(float(t)) for t in grid]
        idx = next((i for i, fv in enumerate(fvals) if fv < -1e-12), None)
        if idx is None:
            return lo if fvals[0] <= 0.0 else hi
        if idx == 0:
            return lo
        a, b = float(grid[idx - 1]), float(grid[idx])
        fa, fb = fvals[idx - 1], fvals[idx]
        for _ in range(80):
            mid = 0.5 * (a + b)
            f_mid = f(mid)
            if abs(f_mid) < 1e-9:
                return mid
            if f_mid < 0.0:
                b, fb = mid, f_mid
            else:
                a, fa = mid, f_mid
        return 0.5 * (a + b)

    # -- Vectorized kernels (used by the staged column solver) ----------------

    def k_values_wilson_vec(self, T_arr: np.ndarray, P_arr: np.ndarray,
                            names: List[str]) -> np.ndarray:
        """Wilson K for an array of stages -> (n_stages, nc)."""
        n = len(T_arr)
        nc = len(names)
        if n == 0 or nc == 0:
            return np.zeros((n, nc))
        T = np.asarray(T_arr, dtype=float)
        P = np.broadcast_to(np.atleast_1d(np.asarray(P_arr, dtype=float)), (n,))
        pb = self._param_block(names)
        vol = pb["volatile"]
        K = np.empty((n, nc))
        if np.any(vol):
            K[:, vol] = (pb["pc"][vol][None, :] / P[:, None]) * np.exp(
                5.42 * (1.0 + pb["omega"][vol]) * (1.0 - pb["tc"][vol] / T[:, None]))
        if np.any(~vol):
            K[:, ~vol] = 1e-10
        return np.clip(K, 1e-10, 1e10)

    def _bubble_newton(self, P: np.ndarray, names: List[str], X: np.ndarray,
                       T_guess: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Newton on f(T) = sum(K_i(T) x_i) - 1 with a warm start.

        f is strictly increasing (Wilson K grow with T), so for any interior
        root Newton converges quadratically from a nearby guess.  Returns
        (T, converged): converged marks stages that reached an interior root
        to full precision.  Stages that fail -- e.g. feeds whose bubble point
        lies at the [200, 1200] K ceiling, where the old bisection returns the
        midpoint -- are NOT marked converged and go to the bisection fallback,
        preserving the original degenerate semantics exactly.
        """
        n, nc = X.shape
        pb = self._param_block(names)
        lo, hi = 200.0, 1200.0
        T = np.clip(np.asarray(T_guess, dtype=float), lo, hi).copy()
        done = np.zeros(n, dtype=bool)
        active = np.flatnonzero(~done)
        lnk = 5.42 * (1.0 + pb["omega"]) * pb["tc"]
        for _ in range(12):
            if active.size == 0:
                break
            Ka = self.k_values_wilson_vec(T[active], P[active], names)
            sa = np.sum(Ka * X[active], axis=1) - 1.0
            ds = np.sum(Ka * X[active] * (lnk / T[active, None] ** 2), axis=1)
            step = np.clip(sa / np.maximum(ds, 1e-12), -60.0, 60.0)
            Tn = T[active] - step
            ok = (Tn > lo) & (Tn < hi)
            T[active] = np.where(ok, Tn, T[active])
            conv_here = ok & (np.abs(step) < 1e-7)
            done[active] |= conv_here
            active = active[~conv_here]
        if np.any(done):
            K = self.k_values_wilson_vec(T[done], P[done], names)
            s = np.sum(K * X[done], axis=1) - 1.0
            good = (np.abs(s) < 1e-7) & (T[done] > lo) & (T[done] < hi)
            d2 = done.copy()
            d2[done] = good
            done = d2
        return T, done

    def _bubble_bisect(self, P: np.ndarray, names: List[str], X: np.ndarray,
                       idx: np.ndarray) -> np.ndarray:
        """Original 45-iteration vectorized bisection, restricted to stages idx."""
        idx = np.asarray(idx, dtype=int)
        if idx.size == 0:
            return np.empty(0)
        lo = np.full(idx.size, 200.0)
        hi = np.full(idx.size, 1200.0)
        Xsub = X[idx]
        Psub = P[idx]
        for _ in range(45):
            mid = 0.5 * (lo + hi)
            K = self.k_values_wilson_vec(mid, Psub, names)
            s = np.sum(K * Xsub, axis=1) - 1.0
            hi[s > 0.0] = mid[s > 0.0]
            lo[s <= 0.0] = mid[s <= 0.0]
            if np.all(np.abs(s) < 1e-7):
                break
        return 0.5 * (lo + hi)

    def bubble_temperature_vec(self, P_arr: np.ndarray, names: List[str],
                               Xmat: np.ndarray,
                               T_guess: Optional[np.ndarray] = None) -> np.ndarray:
        """Isobaric bubble points for every stage row of Xmat (Wilson K).

        f(T) = sum(K_i(T) x_i) - 1 is strictly increasing in T for Wilson K.
        With a warm-start guess the root is found by a few Newton steps; any
        stage that does not converge (or the no-guess call) uses the safe
        bisection path, so results are unchanged while the hot column loop
        drops from ~45 K-evaluations per stage-row to ~4.
        """
        n, nc = Xmat.shape
        if n == 0 or nc == 0:
            return np.full(n, 300.0)
        P = np.broadcast_to(np.atleast_1d(np.asarray(P_arr, dtype=float)), (n,))
        X = np.asarray(Xmat, dtype=float)
        T = np.full(n, 700.0)
        conv = np.zeros(n, dtype=bool)
        if T_guess is not None:
            Tg = np.asarray(T_guess, dtype=float)
            if Tg.shape == (n,) and np.all(np.isfinite(Tg)):
                T, conv = self._bubble_newton(P, names, X, Tg)
        if not np.all(conv):
            rest = np.flatnonzero(~conv)
            T[rest] = self._bubble_bisect(P, names, X, rest)
        return T

    def _mixing_vec(self, names: List[str], Zmat: np.ndarray, T_arr: np.ndarray):
        """Vectorized PR mixing over stages -> (am, b, dam, a, da)."""
        n, nc = Zmat.shape
        pb = self._param_block(names)
        T = np.asarray(T_arr, dtype=float)
        Tr = T[:, None] / pb["tc"][None, :]
        sqrt_alpha = 1.0 + pb["kappa"][None, :] * (1.0 - np.sqrt(Tr))
        alpha = sqrt_alpha ** 2
        a = pb["a_i"][None, :] * alpha
        dalpha = -pb["kappa"][None, :] * sqrt_alpha / np.sqrt(T[:, None] * pb["tc"][None, :])
        da = pb["a_i"][None, :] * dalpha
        sqrt_a = np.sqrt(a)
        b = Zmat @ pb["b_i"]
        # O(nc) reduction of the double sum (verified equivalent to 7e-13):
        S_sa = np.sum(Zmat * sqrt_a, axis=1)
        S_da = np.sum(Zmat * da / np.sqrt(np.maximum(a, 1e-30)), axis=1)
        am = S_sa ** 2
        dam = S_sa * S_da
        return am, b, dam, a, da

    def _z_phase_vec(self, A_arr: np.ndarray, B_arr: np.ndarray,
                     phase: Phase) -> np.ndarray:
        """Vectorized PR compressibility root selection -> (n,)."""
        A = np.asarray(A_arr, dtype=float)
        B = np.asarray(B_arr, dtype=float)
        p = -1.0 + B
        q = A - 3.0 * B * B - 2.0 * B
        r = -(A * B - B * B - B ** 3)
        P = q - p * p / 3.0
        Q = 2.0 * p ** 3 / 27.0 - p * q / 3.0 + r
        disc = (P / 3.0) ** 3 + (Q / 2.0) ** 2

        single = disc > 0.0
        s1 = np.cbrt(-Q / 2.0 + np.sqrt(np.maximum(disc, 0.0)))
        s2 = np.cbrt(-Q / 2.0 - np.sqrt(np.maximum(disc, 0.0)))
        z_single = s1 + s2 - p / 3.0

        Pc = np.where(P < 0.0, P, 1.0)
        arg = np.clip(-Q / 2.0 / np.sqrt(np.maximum((-Pc / 3.0) ** 3, 1e-30)), -1.0, 1.0)
        phi = np.arccos(arg)
        fac = 2.0 * np.sqrt(np.maximum(-Pc / 3.0, 0.0))
        z1 = fac * np.cos(phi / 3.0) - p / 3.0
        z2 = fac * np.cos((phi + 2.0 * np.pi) / 3.0) - p / 3.0
        z3 = fac * np.cos((phi + 4.0 * np.pi) / 3.0) - p / 3.0
        roots = np.stack([z1, z2, z3], axis=1)  # (n, 3)

        want_vap = phase == Phase.VAPOR or phase == Phase.TWO_PHASE
        if want_vap:
            z = np.max(roots, axis=1)
        else:
            pos = np.where(roots > 0.0, roots, np.inf)
            z = np.min(pos, axis=1)
        z = np.where(single, z_single, z)
        z = np.where(np.isfinite(z) & (z > 0.0), z, 1.0)
        return z

    def stage_enthalpy_molar_vec(self, T_arr: np.ndarray, P_arr: np.ndarray,
                                 Zmat: np.ndarray, names: List[str],
                                 phase: Phase) -> np.ndarray:
        """Total molar enthalpy [J/mol] for each stage row, vectorized."""
        n, nc = Zmat.shape
        if n == 0 or nc == 0:
            return np.zeros(n)
        am, b, dam, _, _ = self._mixing_vec(names, Zmat, T_arr)
        T = np.asarray(T_arr, dtype=float)
        P = np.asarray(P_arr, dtype=float)
        A = am * P / (R_GAS ** 2 * T ** 2)
        B = b * P / (R_GAS * T)
        Z = self._z_phase_vec(A, B, phase)
        num = Z + (1.0 + np.sqrt(2.0)) * B
        denom = Z + (1.0 - np.sqrt(2.0)) * B
        log_term = np.log(np.maximum(np.abs(num / np.maximum(denom, 1e-30)), 1e-30))
        h_res = R_GAS * T * (Z - 1.0) + (T * dam - am) / (
            2.0 * np.sqrt(2.0) * np.maximum(b, 1e-30)) * log_term
        # ideal gas contribution
        pb = self._param_block(names)
        h_ig = np.sum(
            Zmat * (pb["cp_a"][None, :] * (T - self.T_REF)[:, None]
                    + 0.5 * pb["cp_b"][None, :] * (T ** 2 - self.T_REF ** 2)[:, None]),
            axis=1,
        )
        return h_ig + h_res
