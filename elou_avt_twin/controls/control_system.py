"""
control_system.py
=================
ControlSystem — runtime container for the KTK controller catalogue.

Owns the PID loops (unified Controller models), applies operator commands,
advances every loop against measured process values and reproduces the HMI
cascade / setpoint-correction logic captured in controls.catalog.CASCADES.

API layer contract (Этап 3): the system is populated from the catalogue and
exposed via /controllers + /command. Live PV binding to the physics engine is
wired in a later stage; step_all() already implements the control algorithm
so nothing is lost when the HMI's JS model is removed.
"""

from typing import Dict, Optional, Any

from models.controller import Controller, MODE_AUTO
from models.command import Command, CommandAction, validate_controller_command
from .catalog import CONTROLLER_CATALOG, CASCADES, TRACKED_LOOPS


class ControlSystem:
    """PID loop registry with command handling and cascade stepping."""

    def __init__(self,
                 catalog: Optional[Dict[str, Controller]] = None,
                 cascades: Optional[Dict[str, dict]] = None,
                 tracked: Optional[Dict[str, Any]] = None):
        self._catalog_defaults: Dict[str, Controller] = {
            tag: c.model_copy(deep=True)
            for tag, c in (catalog if catalog is not None else CONTROLLER_CATALOG).items()
        }
        self.controllers: Dict[str, Controller] = {
            tag: c.model_copy(deep=True) for tag, c in self._catalog_defaults.items()
        }
        self.cascades: Dict[str, dict] = dict(cascades if cascades is not None else CASCADES)
        self.tracked: Dict[str, Any] = dict(tracked if tracked is not None else TRACKED_LOOPS)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def apply_command(self, cmd: Command) -> Controller:
        """Validate and apply one operator command; returns the loop."""
        ctrl = self.controllers.get(cmd.tag)
        if ctrl is None:
            raise ValueError(f"Регулятор '{cmd.tag}' не найден")
        validate_controller_command(cmd, ctrl)
        if cmd.action == CommandAction.SET_SP:
            ctrl.set_sp(float(cmd.value))
        elif cmd.action == CommandAction.SET_MODE:
            ctrl.set_mode(str(cmd.value))
        elif cmd.action == CommandAction.SET_VALUE:
            ctrl.set_manual_output(float(cmd.value))
        return ctrl

    # ------------------------------------------------------------------
    # Stepping
    # ------------------------------------------------------------------

    def step_all(self,
                 pv_map: Optional[Dict[str, float]] = None,
                 dt: float = 1.0,
                 extra: Optional[Dict[str, float]] = None) -> None:
        """Advance every loop by dt seconds.

        Parameters:
            pv_map : tag -> measured process value (falls back to c.pv)
            dt     : time step [s]
            extra  : cascade process variables (T_K1bot, L4K28, T_K9bot, L632)
        """
        pv_map = pv_map or {}
        extra = extra or {}
        stepped: set = set()

        def do_step(tag: str) -> None:
            if tag in stepped or tag not in self.controllers:
                return
            stepped.add(tag)
            c = self.controllers[tag]
            if tag in self.tracked:
                r = self.tracked[tag]
                pv = c.sp if r == "sp" else c.pv + (c.sp - c.pv) * float(r)
            else:
                pv = pv_map.get(tag, c.pv)
            c.step(pv, dt)

        # Cascades: step the master first so the slave reads a fresh output,
        # then apply the corrected setpoint and step the slave (HMI ordering).
        for tag, spec in self.cascades.items():
            master = spec.get("master")
            if master:
                do_step(master)
            sp = self._cascade_sp(spec, extra)
            if sp is not None:
                c = self.controllers[tag]
                if c.mode == MODE_AUTO and not c.man:
                    lo = spec.get("lo", c.lo)
                    hi = spec.get("hi", c.hi)
                    c.sp = max(lo, min(hi, sp))
            do_step(tag)

        for tag in self.controllers:
            do_step(tag)

    def _cascade_sp(self, spec: dict, extra: Dict[str, float]) -> Optional[float]:
        """Compute the cascade setpoint for a spec, or None if data is missing."""
        form = spec["form"]
        if form == "span":
            return spec["base"] + self.controllers[spec["master"]].out / 100.0 * spec["span"]
        if form == "scale":
            return self.controllers[spec["master"]].out / 100.0 * spec["scale"]
        if form == "master_pv":
            pv = extra.get(spec["pv"])
            if pv is None:
                return None
            return spec["base"] + (self.controllers[spec["master"]].sp - pv) * spec["k"]
        if form == "pv":
            pv = extra.get(spec["pv"])
            if pv is None:
                return None
            if spec.get("dir") == "minus":
                return spec["base"] + (spec["pvbase"] - pv) * spec["k"]
            return spec["base"] + (pv - spec["pvbase"]) * spec["k"]
        return None

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    def snapshot(self) -> Dict[str, dict]:
        """Faceplate snapshot of every loop for the HMI / API."""
        return {tag: self.faceplate(tag) for tag in self.controllers}

    def faceplate(self, tag: str) -> dict:
        """Faceplate snapshot of one loop."""
        c = self.controllers[tag]
        return {
            **c.model_dump(),
            "cascade": self.cascades.get(tag),
            "tracked": tag in self.tracked,
        }

    def reset(self) -> None:
        """Restore every loop to its pristine catalogue default (sp, mode, out)."""
        self.controllers = {
            tag: c.model_copy(deep=True) for tag, c in self._catalog_defaults.items()
        }
