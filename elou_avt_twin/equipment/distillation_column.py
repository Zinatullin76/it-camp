"""
distillation_column.py
======================
Rigorous distillation column model using MESH equations (staged model).
"""

from typing import Dict, Any, Optional, List
import numpy as np
from .base_equipment import BaseEquipment, EquipmentState
from models.stream import Stream, Phase
from calculation_core.solver.mesh_solver import DistillationSolver

class DistillationColumn(BaseEquipment):
    """
    Atmospheric distillation column with staged MESH calculations.
    """

    def __init__(self, equipment_id: str, params: Optional[Dict[str, Any]] = None):
        super().__init__(equipment_id, params or {})
        self._apply_params()

        # Profiles
        self.t_profile = np.zeros(self.num_stages)
        self.l_profile = np.zeros(self.num_stages)
        self.v_profile = np.zeros(self.num_stages)
        
        self.reflux_ratio = float(self.params.get("initial_reflux_ratio", 2.0))
        self.boilup_ratio = 1.5
        self.side_draw_fraction = float(self.params.get("side_draw_fraction", 0.10))
        self._side_cut = self.params.get("side_draw_cut") or []
        self._warm_L = None
        self._warm_V = None
        self._warm_x = None
        self._last_sig = None
        self._solve_count = 0
        self._cached = None

    def _apply_params(self) -> None:
        self.num_stages = self.params.get("num_stages", 20)
        self.feed_stage = self.params.get("feed_stage", 10)
        self.pressure = self.params.get("nominal_pressure", 101325.0)

    def _side_split(self, feed, distillate_mass):
        """Mass of the side draw and its composition (a share of the feed).

        Uses the ``side_draw_cut`` fraction list when given (side draw takes
        exactly those fractions present in the feed); otherwise the constant
        ``side_draw_fraction`` (default 0.10).  The side draw never exceeds
        what is left of the feed after the distillate, so the overall balance
        D + S + B = F always holds.
        """
        cut = self._side_cut
        if cut:
            d = {c: feed.composition.get(c, 0.0) for c in cut}
            ds = sum(d.values())
            if ds > 1e-12:
                frac = ds
                comp = {c: v / ds for c, v in d.items()}
            else:
                frac = 0.0
                comp = dict(feed.composition)
        else:
            frac = self.side_draw_fraction
            comp = dict(feed.composition)
        side_mass = max(0.0, feed.mass_flow * frac)
        side_mass = min(side_mass, max(0.0, feed.mass_flow - max(0.0, distillate_mass)))
        return side_mass, comp

    def step(self, dt: float, **inputs) -> Dict[str, Any]:
        """
        Inputs:
            feed_stream: Stream
            thermo: ThermodynamicModel
            reflux_ratio: float
        """
        feed: Stream = inputs.get("feed_stream")
        thermo = inputs.get("thermo")
        self.reflux_ratio = inputs.get("reflux_ratio", self.reflux_ratio)
        
        if not feed or not thermo:
            return {"distillate": None, "bottoms": None}

        # The MESH solve is the most expensive step in the train.  When the
        # driving inputs are unchanged, re-solving every 1 s tick only
        # re-converges to the same profile, so reuse the last result for up
        # to `solve_interval` consecutive identical ticks (default 3).
        interval = max(int(self.params.get("solve_interval", 3)), 1)
        sig = (
            round(float(feed.mass_flow), 3),
            round(float(feed.temperature), 2),
            round(float(feed.pressure), 0),
            tuple(sorted((c, round(float(v), 4)) for c, v in feed.composition.items())),
            round(float(self.reflux_ratio), 3),
            round(float(self.boilup_ratio), 3),
            round(float(self.pressure), 0),
        )
        if (interval > 1 and self._cached is not None
                and self._last_sig == sig and self._solve_count < interval):
            self._solve_count += 1
            return self._rebuild_cached(feed)
        self._last_sig = sig
        self._solve_count = 1

        solver = DistillationSolver(
            self.num_stages,
            self.feed_stage,
            thermo,
            pressure=self.pressure,
            top_cut=self.params.get("top_cut"),
        )
        # Warm start from the previous step's temperature profile (1 Hz loop).
        warm = self.t_profile if len(self.t_profile) == self.num_stages else None
        try:
            result = solver.solve(
                feed,
                reflux_ratio=self.reflux_ratio,
                boilup_ratio=self.boilup_ratio,
                n_iter=self.params.get("solver_n_iter", 40),
                tol=self.params.get("solver_tol", 1e-4),
                T_guess=warm,
                L_guess=self._warm_L,
                V_guess=self._warm_V,
                x_guess=self._warm_x,
            )
        except Exception:
            # Fall back to a mass-conservative split if the solver misbehaves.
            result = {
                "converged": False,
                "distillate_molar": 0.0,
                "bottoms_molar": 0.0,
            }

        # Reject physically impossible results (bisection ceiling / degenerate
        # solutions) so the mass-conserving fallback keeps the column bounded.
        if result.get("converged"):
            prof = np.asarray(result.get("T_profile") or [], dtype=float)
            if (len(prof) != self.num_stages
                    or not np.all(np.isfinite(prof))
                    or prof.min() < 250.0 or prof.max() > 1100.0):
                result = {
                    "converged": False,
                    "distillate_molar": 0.0,
                    "bottoms_molar": 0.0,
                }

        # Reconstruct the temperature profile from the solver output.
        if result.get("converged") and result.get("T_profile"):
            t_profile = np.asarray(result["T_profile"], dtype=float)
            self.t_profile = t_profile
            self.l_profile = np.asarray(result["L_profile"], dtype=float)
            self.v_profile = np.asarray(result["V_profile"], dtype=float)
            self._warm_L = result.get("L_molar")
            self._warm_V = result.get("V_molar")
            self._warm_x = result.get("x_profile")
        elif len(self.t_profile) != self.num_stages:
            self.t_profile = np.linspace(feed.temperature - 50.0, feed.temperature + 30.0, self.num_stages)

        if not result.get("converged") or feed.mass_flow <= 0:
            if feed.mass_flow <= 0:
                distillate_mass = 0.0
                bottoms_mass = 0.0
                # Zero-flow products must still carry a valid (non-zero-total)
                # composition, otherwise Stream validation rejects them.
                comp_d = dict(feed.composition)
                comp_b = dict(feed.composition)
            else:
                # Mass-conserving MVP fallback: split the feed by the overhead
                # cut so the products never vanish (D + B = F exactly).
                cut = self.params.get("top_cut") or []
                d = {c: feed.composition.get(c, 0.0) for c in cut}
                ds = sum(d.values())
                b = {c: v for c, v in feed.composition.items() if c not in cut}
                bs = sum(b.values())
                if ds <= 1e-12 or bs <= 1e-12:
                    comp_d = dict(feed.composition)
                    comp_b = feed.composition.copy()
                    distillate_mass = 0.0
                    bottoms_mass = feed.mass_flow
                else:
                    comp_d = {c: v / ds for c, v in d.items()}
                    comp_b = {c: v / bs for c, v in b.items()}
                    distillate_mass = feed.mass_flow * ds
                    bottoms_mass = feed.mass_flow - distillate_mass
            def _fb_temp(idx):
                if len(self.t_profile) == self.num_stages:
                    t = float(self.t_profile[idx])
                    if t > 200.0:
                        return t
                return feed.temperature
            t_fb = _fb_temp(0)
            t_fb_bot = _fb_temp(-1)
            side_mass, comp_sd = self._side_split(feed, distillate_mass)
            bottoms_mass = max(0.0, feed.mass_flow - distillate_mass - side_mass)
            t_mid = 0.5 * (t_fb + t_fb_bot)
            distillate = self._make_product(
                thermo, feed, t_fb, self.pressure, distillate_mass, comp_d, Phase.VAPOR,
            )
            bottoms = self._make_product(
                thermo, feed, t_fb_bot, self.pressure, bottoms_mass, comp_b, Phase.LIQUID,
            )
            side = self._make_product(
                thermo, feed, t_mid, self.pressure, side_mass, comp_sd, Phase.LIQUID,
            )
            self._cached = {
                "t_top": t_fb, "t_bottom": t_fb_bot, "t_side": t_mid,
                "d_mass": distillate_mass, "b_mass": bottoms_mass, "s_mass": side_mass,
                "comp_dist": comp_d, "comp_bott": comp_b, "comp_side": comp_sd,
                "h_dist": distillate.enthalpy, "h_bott": bottoms.enthalpy,
                "h_side": side.enthalpy,
                "converged": result.get("converged", False),
            }
            return {
                "distillate": distillate,
                "side_draw": side,
                "bottoms": bottoms,
                "t_profile": self.t_profile.tolist(),
                "converged": result.get("converged", False),
            }

        comp_dist = result.get("distillate_comp_mass") or {k: 0.0 for k in feed.composition}
        comp_bott = result.get("bottoms_comp_mass") or {k: 0.0 for k in feed.composition}

        # Overall mass conservation: scale molar-derived flows to the feed mass.
        d_mass_raw = float(result["distillate_molar"] * result.get("distillate_mean_molar_mass", 0.05))
        b_mass_raw = float(result["bottoms_molar"] * result.get("bottoms_mean_molar_mass", 0.3))
        total_raw = d_mass_raw + b_mass_raw
        if total_raw > 1e-12:
            f_d = d_mass_raw / total_raw
            distillate_mass = f_d * feed.mass_flow
            bottoms_mass = (1.0 - f_d) * feed.mass_flow
        else:
            distillate_mass = 0.0
            bottoms_mass = feed.mass_flow

        t_top = float(self.t_profile[0])
        t_bottom = float(self.t_profile[-1])

        side_mass, comp_sd = self._side_split(feed, distillate_mass)
        bottoms_mass = max(0.0, feed.mass_flow - distillate_mass - side_mass)
        if bottoms_mass <= 0.0 and feed.mass_flow > 0.0:
            distillate_mass = max(0.0, feed.mass_flow - side_mass)
        t_mid = 0.5 * (t_top + t_bottom)

        distillate = self._make_product(
            thermo, feed, t_top, self.pressure, distillate_mass, comp_dist, Phase.VAPOR,
        )
        bottoms = self._make_product(
            thermo, feed, t_bottom, self.pressure, bottoms_mass, comp_bott, Phase.LIQUID,
        )
        side = self._make_product(
            thermo, feed, t_mid, self.pressure, side_mass, comp_sd, Phase.LIQUID,
        )
        self._cached = {
            "t_top": t_top, "t_bottom": t_bottom, "t_side": t_mid,
            "d_mass": distillate_mass, "b_mass": bottoms_mass, "s_mass": side_mass,
            "comp_dist": comp_dist, "comp_bott": comp_bott, "comp_side": comp_sd,
            "h_dist": distillate.enthalpy, "h_bott": bottoms.enthalpy,
            "h_side": side.enthalpy,
            "converged": True,
        }
        return {
            "distillate": distillate,
            "side_draw": side,
            "bottoms": bottoms,
            "t_profile": self.t_profile.tolist(),
            "converged": result.get("converged", False),
        }

    def _rebuild_cached(self, feed: Stream) -> Dict[str, Any]:
        """Re-emit the last solved products from fresh stream copies."""
        c = self._cached
        distillate = feed.copy_with(
            name="Distillate", temperature=c["t_top"], pressure=self.pressure,
            mass_flow=c["d_mass"], composition=c["comp_dist"], phase=Phase.VAPOR,
            enthalpy=c.get("h_dist", feed.enthalpy),
        )
        bottoms = feed.copy_with(
            name="Bottoms", temperature=c["t_bottom"], pressure=self.pressure,
            mass_flow=c["b_mass"], composition=c["comp_bott"], phase=Phase.LIQUID,
            enthalpy=c.get("h_bott", feed.enthalpy),
        )
        side = feed.copy_with(
            name="SideDraw", temperature=c["t_side"], pressure=self.pressure,
            mass_flow=c["s_mass"], composition=c["comp_side"], phase=Phase.LIQUID,
            enthalpy=c.get("h_side", feed.enthalpy),
        )
        return {
            "distillate": distillate,
            "side_draw": side,
            "bottoms": bottoms,
            "t_profile": self.t_profile.tolist(),
            "converged": c["converged"],
        }

    @staticmethod
    def _make_product(thermo, feed: Stream, temperature: float, pressure: float,
                      mass_flow: float, composition: dict, phase: Phase) -> Stream:
        """Build a product stream with an enthalpy consistent with T/P/comp.

        copy_with() keeps the feed's enthalpy, which is wrong for a distillate
        or bottoms stream (different temperature and composition).  Recompute
        it from the PR EOS so downstream energy balances (condensers, heat
        exchangers) see a consistent stream.
        """
        enthalpy = feed.enthalpy
        try:
            enthalpy = float(thermo.calculate_enthalpy(temperature, pressure, composition, phase))
        except Exception:
            pass
        return feed.copy_with(
            name="Distillate" if phase == Phase.VAPOR else "Bottoms",
            temperature=temperature, pressure=pressure,
            mass_flow=mass_flow, composition=composition, phase=phase,
            enthalpy=enthalpy,
        )

    def get_state(self) -> EquipmentState:
        self.state.extra["top_temperature"] = self.t_profile[0] if len(self.t_profile) > 0 else 0
        self.state.extra["bottom_temperature"] = self.t_profile[-1] if len(self.t_profile) > 0 else 0
        return self.state

    def apply_action(self, action_type: str, value: Optional[float] = None) -> None:
        if action_type == "SET_VALUE" and value is not None:
            self.reflux_ratio = max(0.1, value)

    def reset(self) -> None:
        super().reset()
        self.t_profile = np.zeros(self.num_stages)
        self.l_profile = np.zeros(self.num_stages)
        self.v_profile = np.zeros(self.num_stages)
        self._warm_L = None
        self._warm_V = None
        self._warm_x = None
        self._last_sig = None
        self._solve_count = 0
        self._cached = None
