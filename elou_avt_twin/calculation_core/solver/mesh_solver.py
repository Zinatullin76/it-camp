"""
mesh_solver.py
==============
Rigorous staged distillation solver (Bubble-Point method with energy balances).

Solves the complete MESH set for an isobaric equilibrium-stage column:
    M - component material balances  (tridiagonal system per component)
    E - phase equilibrium  y = K x   (Wilson K from real Tc/Pc/omega)
    S - summation                   (bubble-point temperature, sum K x = 1)
    H - energy balance              (internal L/V profile updated from the
         stage enthalpy balances using Peng-Robinson enthalpies, including
         the latent heat via the residual enthalpy)

This replaces the previous Wang-Henke/CMO shortcut. No constant-molar-overflow
assumption is made: every iteration the liquid and vapour flow profiles are
recomputed so that every stage energy balance closes, and the temperature
profile is updated by bubble point until both converge. The distillate flow is
adjusted by an inner fixed-point iteration so the overall column balance
closes exactly (D + B = F).

Stage numbering is top-to-bottom: stage 1 is the (total) condenser stage,
stage N the reboiler stage; the feed enters on stage `feed_stage`.
"""

import logging

import numpy as np
from typing import Dict, List, Optional, Tuple

# Minimum internal flow before a profile is flagged as non-physical.
_MIN_FLOW = 1e-9
logger = logging.getLogger("elou_avt.mesh_solver")


class DistillationSolver:
    """
    Rigorous staged distillation solver over Peng-Robinson thermodynamics.

    ``thermo`` must expose the vectorised PR kernels:
        k_values_wilson_vec(T_arr, P_arr, names)      -> (n, nc)
        bubble_temperature_vec(P_arr, names, Xmat)    -> (n,)
        stage_enthalpy_molar_vec(T_arr, P_arr, Z, names, phase) -> (n,)
        calculate_enthalpy(T, P, comp_dict)           -> J/kg
        calculate_vle(T, P, comp_dict)                -> (beta, x, y)
    """

    def __init__(
        self,
        num_stages: int,
        feed_stage: int,
        thermo_model,
        pressure: float = 101325.0,
        top_cut: Optional[List[str]] = None,
    ):
        self.n = int(num_stages)
        self.f = int(feed_stage)
        self.thermo = thermo_model
        self.components = thermo_model.data
        self.pressure = float(pressure)
        self.names = list(thermo_model.data.keys())
        self.nc = len(self.names)
        self.top_cut = list(top_cut) if top_cut else None
        if self.f < 1:
            self.f = 1
        if self.f > self.n:
            self.f = self.n
        self._M = np.array(
            [self.components[c].get("molar_mass", 0.1) for c in self.names]
        )

    # ------------------------------------------------------------------
    # Feed handling
    # ------------------------------------------------------------------

    def _feed_molar(self, feed_stream) -> Tuple[float, np.ndarray, float, float]:
        """Return (F_mol, z_molar over full set, mean_mw, hF_mol [J/mol])."""
        comp = {k: v for k, v in feed_stream.composition.items() if v and v > 0}
        if not comp or feed_stream.mass_flow <= 0:
            return 0.0, np.zeros(self.nc), 1.0, 0.0
        w = np.array([comp.get(c, 0.0) for c in self.names], dtype=float)
        w = w / max(np.sum(w), 1e-30)
        z = (w / self._M)
        z = z / max(np.sum(z), 1e-30)
        mean_m = float(np.sum(z * self._M))
        F_mol = feed_stream.mass_flow / mean_m
        try:
            # Use the feed's own enthalpy (as delivered by upstream equipment,
            # e.g. the furnace outlet) rather than re-deriving it at the
            # column pressure with the stream temperature.  The old path
            # evaluated the mixture at (T_stream, P_column) which sits far
            # above the bubble point for a hot liquid feed flashed into a
            # vacuum column, over-stating the feed energy by the latent heat
            # and forcing a spurious energy residual at the feed stage.
            if feed_stream.enthalpy:
                hF_kg = feed_stream.enthalpy
            else:
                hF_kg = self.thermo.calculate_enthalpy(
                    feed_stream.temperature, feed_stream.pressure, dict(comp)
                )
        except (ValueError, FloatingPointError) as exc:
            logger.debug("Feed enthalpy calculation failed; using zero fallback: %s", exc)
            hF_kg = 0.0
        return F_mol, z, mean_m, hF_kg * mean_m

    def _feed_q(self, feed_stream) -> float:
        """Liquid fraction of the feed at its own T/P (for the initial D guess)."""
        try:
            beta, _, _ = self.thermo.calculate_vle(
                feed_stream.temperature, self.pressure, feed_stream.composition
            )
            return float(np.clip(1.0 - beta, 0.0, 1.0))
        except (ValueError, FloatingPointError) as exc:
            logger.debug("Feed flash failed; assuming liquid feed quality: %s", exc)
            return 1.0

    # ------------------------------------------------------------------
    # Component balance (tridiagonal per component)
    # ------------------------------------------------------------------

    def _solve_m(self, L: np.ndarray, V: np.ndarray, K: np.ndarray,
                 F: np.ndarray, z: np.ndarray, normalize: bool = True) -> np.ndarray:
        """Solve the nc tridiagonal M-systems for x (n x nc).

        With ``normalize=True`` each row is normalised to mole fractions;
        otherwise the raw liquid amounts [mol/s] are returned (used by the
        BP sum-rates flow update).
        """
        n = self.n
        x = np.zeros((n, self.nc))
        D_diag = V[1]  # condenser: liquid leaving stage 0 = reflux + distillate
        a_col = np.zeros(n)
        a_col[1:] = L[:-1]
        c_col = np.zeros((n, self.nc))
        c_col[:-1, :] = V[1:, None] * K[1:, :]  # (n-1, nc)
        for i in range(self.nc):
            b = -(L + V * K[:, i])
            b[0] = -D_diag
            d = -F * z[:, i]
            d[0] = 0.0
            x[:, i] = _solve_tridiagonal(a_col, b, c_col[:, i], d)
        if not normalize:
            return x
        s = np.maximum(np.sum(x, axis=1, keepdims=True), 1e-12)
        x = x / s
        return np.clip(x, 1e-30, None)

    # ------------------------------------------------------------------
    # Energy-balance flow march (top-down)
    # ------------------------------------------------------------------

    def _march(self, T: np.ndarray, x: np.ndarray, y: np.ndarray,
               hL: np.ndarray, hV: np.ndarray, F: np.ndarray,
               hFj: np.ndarray, R: float, D: float,
               F_total: float, min_flow: float = _MIN_FLOW) -> Tuple[np.ndarray, np.ndarray, float]:
        """Compute the L/V profile from stage energy balances.

        ``D`` is the specified distillate draw; the bottoms flow follows from
        the overall material balance B = F_total - D, and the reboiler duty is
        whatever the reboiler energy balance requires (computed later).
        """
        n = self.n
        L = np.zeros(n)
        V = np.zeros(n)
        V[1] = (R + 1.0) * D
        L[0] = R * D
        for j in range(1, n - 1):
            C = V[j] - L[j - 1] - F[j]
            # Stage energy balance (top-to-bottom numbering):
            #     L_{j-1} hL_{j-1} + V_{j+1} hV_{j+1} + F_j hF_j
            #         = L_j hL_j + V_j hV_j
            # with V_{j+1} = L_j + C from the total material balance.
            # Substituting and solving for L_j:
            #     L_j (hV_{j+1} - hL_j) = V_j hV_j - L_{j-1} hL_{j-1}
            #                            - F_j hF_j - C hV_{j+1}
            denom = hV[j + 1] - hL[j]
            if abs(denom) < 1e-12:
                denom = 1e-12
            num = (V[j] * hV[j] - L[j - 1] * hL[j - 1]
                   - F[j] * hFj[j] - C * hV[j + 1])
            L[j] = num / denom
            V[j + 1] = L[j] + C
            if getattr(self, "_trace_clamp", False) and (L[j] < min_flow or V[j + 1] < min_flow):
                logger.debug(
                    "Stage %d flow clamp: L=%.3f, V=%.3f",
                    j, float(L[j]), float(V[j + 1]),
                )
            L[j] = max(L[j], min_flow)
            V[j + 1] = max(V[j + 1], min_flow)
        B = max(F_total - D, min_flow)
        V[n - 1] = L[n - 2] + F[n - 1] - B
        V[n - 1] = max(V[n - 1], min_flow)
        L[n - 1] = B
        return L, V, B

    # ------------------------------------------------------------------
    # Main solve
    # ------------------------------------------------------------------

    def solve(
        self,
        feed_stream,
        reflux_ratio: float = 2.0,
        boilup_ratio: float = 1.5,
        feed_thermal: Optional[float] = None,
        n_iter: int = 40,
        tol: float = 1e-4,
        T_guess: Optional[np.ndarray] = None,
        L_guess: Optional[np.ndarray] = None,
        V_guess: Optional[np.ndarray] = None,
        x_guess: Optional[np.ndarray] = None,
    ) -> Dict:
        thermo = self.thermo
        n, nc, f = self.n, self.nc, self.f
        fail = {"converged": False, "distillate_molar": 0.0, "bottoms_molar": 0.0}

        F_mol, z_feed, feed_mean_m, hF = self._feed_molar(feed_stream)
        if F_mol <= 0:
            return fail

        F = np.zeros(n)
        F[f - 1] = F_mol
        z = np.zeros((n, nc))
        z[f - 1] = z_feed
        hFj = np.zeros(n)
        hFj[f - 1] = hF

        R = max(float(reflux_ratio), 1e-3)
        RB = max(float(boilup_ratio), 1e-3)
        q = 1.0 if feed_thermal is None else float(np.clip(feed_thermal, 0.0, 1.0))
        if feed_thermal is None:
            q = self._feed_q(feed_stream)

        # Distillate draw: molar fraction of the feed that belongs to the
        # column's overhead cut (top_cut). Falls back to every component that
        # would partition to the VAPOUR at the feed bubble point (Wilson
        # K_i(T_feed_bubble, P) > 1 + margin) when no cut is given.
        T_feed_bubble = thermo.bubble_temperature_vec(
            np.array([self.pressure]), self.names, z_feed[None, :]
        )[0]
        # At the feed bubble point of a nearly-pure feed its own dominant
        # component has K ~ 1 by definition; a small margin keeps that
        # "self" component out of the overhead and into the bottoms.
        VAPOUR_PARTITION_MARGIN = 1.05

        def _partitions_to_vapour(c: str) -> bool:
            d = self.components[c]
            if not d.get("volatile", True):
                return False
            return (d["pc"] / self.pressure) * np.exp(
                5.42 * (1.0 + d["omega"]) * (1.0 - d["tc"] / T_feed_bubble)
            ) > VAPOUR_PARTITION_MARGIN

        def _present_cut() -> List[str]:
            # Only components that actually exist in the feed (mole fraction
            # above a floor) may be recovered as overhead.
            return [c for i, c in enumerate(self.names)
                    if z_feed[i] > 1e-9 and _partitions_to_vapour(c)]

        # NOTE: the threshold must be the vapour partition at the feed bubble
        # point, NOT nbp < T_feed_bubble.  For a heavy feed (e.g. ~pure
        # vacuum residue) the feed bubble point lies ABOVE the NBP of its own
        # dominant component, so the old "nbp < bubble" test classified the
        # whole feed as overhead -> D ~= F, the bottoms (which carry all the
        # non-volatile salt) collapsed to ~zero flow, and the bottom stage
        # became ~pure salt -> bubble point degenerated to the 1200 K ceiling.
        cut = self.top_cut
        if not cut:
            cut = _present_cut()
        cut_idx = [i for i, c in enumerate(self.names) if c in cut]
        if cut_idx:
            D_frac = float(np.sum(z_feed[cut_idx]))
        else:
            D_frac = 0.0
        # A configured cut that is absent from the feed (e.g. a stripping
        # column fed after an upstream column removed the cut) leaves nothing
        # physically recoverable overhead: D -> 0 and the whole feed goes to
        # the bottoms.  This is correct and conservative -- it also keeps the
        # non-volatile salt dilute in a large bottoms flow instead of
        # concentrating it to a degenerate ~pure-salt reboiler.
        if D_frac < 1e-4:
            cut = _present_cut()
            cut_idx = [i for i, c in enumerate(self.names) if c in cut]
            D_frac = float(np.sum(z_feed[cut_idx])) if cut_idx else 0.0
        D = float(np.clip(F_mol * D_frac, 1e-6, F_mol - 1e-6))
        B = max(F_mol - D, _MIN_FLOW)

        # Initial temperature profile: linear between the bubble point of the
        # overhead cut and the bubble point of the residue (standard BP init),
        # or a warm start from the previous solve (real-time stepping).
        if T_guess is not None and len(T_guess) == n and np.all(np.isfinite(T_guess)) \
                and np.all(np.asarray(T_guess) > 200.0):
            T = np.asarray(T_guess, dtype=float).copy()
        elif cut_idx and len(cut_idx) < nc:
            Dz = np.zeros(nc)
            Dz[cut_idx] = z_feed[cut_idx]
            Dz_sum = np.sum(Dz)
            if Dz_sum > 1e-12:
                Dz = Dz / Dz_sum
            Bz = z_feed.copy()
            Bz[cut_idx] = 0.0
            Bz_sum = np.sum(Bz)
            if Bz_sum > 1e-12:
                Bz = Bz / Bz_sum
            t_top = thermo.bubble_temperature_vec(
                np.array([self.pressure]), self.names, Dz[None, :]
            )[0]
            t_bot = thermo.bubble_temperature_vec(
                np.array([self.pressure]), self.names, Bz[None, :]
            )[0]
            T = np.linspace(t_top, t_bot, n)
        else:
            T = thermo.bubble_temperature_vec(
                np.full(n, self.pressure), self.names, np.tile(z_feed, (n, 1))
            )
        # Initial flows from a constant-overflow estimate, or a warm start
        # from the previous solve (real-time stepping).
        x = np.tile(z_feed, (n, 1)).astype(float)
        y = np.tile(z_feed, (n, 1)).astype(float)
        x_use_guess = False
        if x_guess is not None:
            xg = np.asarray(x_guess, dtype=float)
            if xg.shape == (n, nc) and np.all(np.isfinite(xg)) and np.all(xg > 0.0):
                x = np.clip(xg, 1e-12, None)
                x = x / np.maximum(np.sum(x, axis=1, keepdims=True), 1e-12)
                x_use_guess = True
        if not x_use_guess and cut_idx and len(cut_idx) < nc:
            # Blend the overhead and residue compositions along the column so
            # the first energy march sees a physical profile instead of a
            # uniform feed-composition guess on every stage.
            Dz = np.zeros(nc)
            Dz[cut_idx] = z_feed[cut_idx]
            Dz_sum = np.sum(Dz)
            if Dz_sum > 1e-12:
                Dz = Dz / Dz_sum
            Bz = z_feed.copy()
            Bz[cut_idx] = 0.0
            Bz_sum = np.sum(Bz)
            if Bz_sum > 1e-12:
                Bz = Bz / Bz_sum
            w = np.linspace(0.0, 1.0, n)[:, None]
            x = Dz[None, :] * (1.0 - w) + Bz[None, :] * w
            x = x / np.maximum(np.sum(x, axis=1, keepdims=True), 1e-12)
        V_top = (R + 1.0) * D
        L_top = R * D
        if L_guess is not None and len(L_guess) == n and np.all(np.isfinite(L_guess)) \
                and np.all(np.asarray(L_guess) > 0.0):
            L = np.clip(np.asarray(L_guess, dtype=float), _MIN_FLOW, None)
        else:
            L = np.full(n, L_top)
        if V_guess is not None and len(V_guess) == n and np.all(np.isfinite(V_guess)) \
                and np.all(np.asarray(V_guess) > 0.0):
            V = np.clip(np.asarray(V_guess, dtype=float), _MIN_FLOW, None)
        else:
            V = np.full(n, V_top)

        # Damping of temperature updates keeps the wide-boiling crude stable.
        omega = getattr(self, '_omega', 0.3)
        omega_x = getattr(self, '_omega_x', 0.0)
        prev_T = T.copy()
        energy_max = 1e30
        flow_ok = True
        satisfied_tol = False
        iters = 0
        eff_tol = max(float(tol), 0.3)
        min_flow = max(_MIN_FLOW, 1e-3 * F_mol)
        L_prev = L.copy()
        V_prev = V.copy()

        for it in range(int(n_iter)):
            iters = it + 1
            # 1) Equilibrium ratios, vapour compositions and stage enthalpies.
            K = thermo.k_values_wilson_vec(T, np.full(n, self.pressure), self.names)
            y = np.clip(K * x, 1e-30, None)
            y = y / np.maximum(np.sum(y, axis=1, keepdims=True), 1e-30)
            hL = thermo.stage_enthalpy_molar_vec(T, np.full(n, self.pressure),
                                                 x, self.names, self._phase_liq())
            hV = thermo.stage_enthalpy_molar_vec(T, np.full(n, self.pressure),
                                                 y, self.names, self._phase_vap())

            # 2) Energy-balance flow march consistent with the current T
            #    (D and B fixed by the overall material balance), damped and
            #    floored to keep every stage viable during subcooled/hot feed.
            L, V, B = self._march(T, x, y, hL, hV, F, hFj, R, D, F_mol, min_flow)
            if it > 0:
                L = 0.5 * L + 0.5 * L_prev
                V = 0.5 * V + 0.5 * V_prev
            L_prev, V_prev = L.copy(), V.copy()

            # 3) Component balances -> x.
            x_new = self._solve_m(L, V, K, F, z)
            if omega_x > 0.0:
                x_new = omega_x * x + (1.0 - omega_x) * x_new
                x_new = x_new / np.maximum(np.sum(x_new, axis=1, keepdims=True), 1e-12)
                x_new = np.clip(x_new, 1e-30, None)
            x = x_new

            # 4) Bubble-point temperatures -> T (damped update).  The current
            #    damped profile is a warm start for Newton (see
            #    PengRobinsonThermodynamics.bubble_temperature_vec).
            T_new = thermo.bubble_temperature_vec(
                np.full(n, self.pressure), self.names, x, T_guess=T
            )
            delta_raw = float(np.max(np.abs(T_new - T)))
            if getattr(self, "_trace", False):
                logger.debug(
                    "MESH iteration=%d dT=%.4g Ttop=%.1f Tbot=%.1f Tfeed=%.1f",
                    it, delta_raw, float(T_new[0]), float(T_new[-1]), float(T_new[self.f - 1]),
                )
            T = omega * T + (1.0 - omega) * T_new
            delta_T = float(np.max(np.abs(T - prev_T)))
            prev_T = T.copy()

            # 5) Energy-balance residuals (informational; recomputed on the
            #    final undamped flows in the reporting block).
            flow_ok = (np.all(L >= _MIN_FLOW) and np.all(V[1:] >= _MIN_FLOW)
                       and B >= _MIN_FLOW and D >= _MIN_FLOW)

            if delta_raw < eff_tol and flow_ok:
                satisfied_tol = True
                break

        # ------------------------------------------------------------------
        # Reporting
        # ------------------------------------------------------------------
        K = thermo.k_values_wilson_vec(T, np.full(n, self.pressure), self.names)
        y = np.clip(K * x, 1e-30, None)
        y = y / np.maximum(np.sum(y, axis=1, keepdims=True), 1e-30)
        hL = thermo.stage_enthalpy_molar_vec(T, np.full(n, self.pressure),
                                             x, self.names, self._phase_liq())
        hV = thermo.stage_enthalpy_molar_vec(T, np.full(n, self.pressure),
                                             y, self.names, self._phase_vap())
        L, V, B = self._march(T, x, y, hL, hV, F, hFj, R, D, F_mol, min_flow)

        # True stage energy residuals on the final (undamped) flows.
        H_res = np.zeros(n)
        for j in range(1, n - 1):
            H_res[j] = (L[j - 1] * hL[j - 1] + V[j + 1] * hV[j + 1]
                        + F[j] * hFj[j] - L[j] * hL[j] - V[j] * hV[j])
        energy_max = float(np.max(np.abs(H_res[1:n - 1])))

        Q_cond = V[1] * (hV[1] - hL[0])
        Q_reb = (L[n - 1] * hL[n - 1] + V[n - 1] * hV[n - 1]
                 - L[n - 2] * hL[n - 2] - F[n - 1] * hFj[n - 1])

        def to_mass(zm):
            mf = zm * self._M
            s = np.sum(mf)
            if s <= 1e-30:
                return {c: 0.0 for c in self.names}
            return dict(zip(self.names, (mf / s).tolist()))

        conv = (satisfied_tol and flow_ok and B > 0.0 and D > 0.0)

        return {
            "converged": conv,
            "T_profile": T.tolist(),
            "L_profile": (L * self._M.mean()).tolist(),
            "V_profile": (V * self._M.mean()).tolist(),
            "L_molar": L.tolist(),
            "V_molar": V.tolist(),
            "x_profile": x.tolist(),
            "y_profile": y.tolist(),
            "distillate_molar": float(D),
            "bottoms_molar": float(B),
            "distillate_comp_molar": x[0].tolist(),
            "bottoms_comp_molar": x[n - 1].tolist(),
            "distillate_comp_mass": to_mass(x[0]),
            "bottoms_comp_mass": to_mass(x[n - 1]),
            "distillate_mean_molar_mass": float(np.sum(x[0] * self._M)),
            "bottoms_mean_molar_mass": float(np.sum(x[n - 1] * self._M)),
            "feed_thermal_q": float(q),
            "condenser_duty": float(Q_cond),
            "reboiler_duty": float(Q_reb),
            "energy_residual_max": energy_max,
            "flow_ok": bool(flow_ok),
            "temperature_iterations": iters,
        }

    # Small helpers to avoid repeated Phase construction.
    def _phase_liq(self):
        from models.stream import Phase
        return Phase.LIQUID

    def _phase_vap(self):
        from models.stream import Phase
        return Phase.VAPOR


def _solve_tridiagonal(a: np.ndarray, b: np.ndarray, c: np.ndarray,
                       d: np.ndarray) -> np.ndarray:
    """Thomas algorithm for the tridiagonal system A x = d."""
    n = b.size
    cf = np.zeros(n)
    df = np.zeros(n)
    m0 = b[0] if abs(b[0]) > 1e-15 else 1e-15
    cf[0] = c[0] / m0
    df[0] = d[0] / m0
    for i in range(1, n):
        m = b[i] - a[i] * cf[i - 1]
        if abs(m) < 1e-15:
            m = 1e-15
        cf[i] = c[i] / m
        df[i] = (d[i] - a[i] * df[i - 1]) / m
    x = np.zeros(n)
    x[n - 1] = df[n - 1]
    for i in range(n - 2, -1, -1):
        x[i] = df[i] - cf[i] * x[i + 1]
    return x
