"""
controller.py
=============
Unified domain model for PID control loops (controllers) of the KTK.

Migrated from the HMI controller catalogue (avt4.html) into the backend so the
loop setpoints/modes live in the Digital Twin, while the HMI only renders the
faceplate and sends commands.

Semantics mirror the HMI implementation exactly:
  e      = (sp - pv) * (rev ? -1 : 1)      -- reverse-acting negates error
  i     += e/span*100 * dt/ti              -- clamped to [-60, +60] (%)
  out    = 50 + kp*(e/span*100)*0.6 + i    -- clamped to [0, 100] (%)
  span   = hi - lo

Modes:
  АВТ — automatic (output driven by the PID algorithm)
  РУЧ — manual (output set by the operator)
  man — manual-only hand valve (HV 820, HV 803): locked in РУЧ
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

MODE_AUTO = "АВТ"
MODE_MANUAL = "РУЧ"

INTEGRAL_CLAMP = 60.0
OUTPUT_MIN = 0.0
OUTPUT_MAX = 100.0
OUTPUT_DEFAULT = 50.0


class Controller(BaseModel):
    """A single PID control loop (instrument tag)."""

    tag: str
    desc: str = ""
    unit: str = ""
    sp: float = 0.0
    pv: float = 0.0
    lo: float = 0.0
    hi: float = 100.0
    kp: float = 1.0
    ti: float = 60.0          # integration time [s]
    rev: bool = False         # reverse-acting controller
    mode: str = MODE_AUTO     # АВТ / РУЧ
    out: float = OUTPUT_DEFAULT
    i: float = 0.0            # integral accumulator
    man: bool = False         # manual-only hand valve
    cascade_sp: Optional[str] = None  # tag of the master controller feeding sp

    def step(self, pv: float, dt: float) -> float:
        """Advance the loop by dt seconds and return the output [0..100] %."""
        self.pv = float(pv)
        if self.mode == MODE_MANUAL or self.man:
            return self.out
        span = (self.hi - self.lo) or 1.0
        e = (self.sp - self.pv) * (-1.0 if self.rev else 1.0)
        self.i += e / span * 100.0 * (dt / max(self.ti, 1.0))
        self.i = max(-INTEGRAL_CLAMP, min(INTEGRAL_CLAMP, self.i))
        self.out = max(OUTPUT_MIN, min(OUTPUT_MAX,
                       OUTPUT_DEFAULT + self.kp * (e / span * 100.0) * 0.6 + self.i))
        return self.out

    def set_sp(self, value: float) -> float:
        """Set the setpoint, clamped to the instrument range."""
        self.sp = max(self.lo, min(self.hi, float(value)))
        return self.sp

    def set_manual_output(self, value: float) -> float:
        """Set the manual output [0..100] %."""
        self.out = max(OUTPUT_MIN, min(OUTPUT_MAX, float(value)))
        return self.out

    def set_mode(self, mode: str) -> str:
        """Switch mode; manual-only valves stay locked in РУЧ."""
        if self.man:
            self.mode = MODE_MANUAL
        elif mode == MODE_AUTO or mode == MODE_MANUAL:
            self.mode = mode
        return self.mode

    def reset(self) -> None:
        """Reset dynamic state back to the default operating point."""
        self.pv = self.sp
        self.mode = MODE_MANUAL if self.man else MODE_AUTO
        self.out = OUTPUT_DEFAULT
        self.i = 0.0


def controller(tag: str, desc: str, unit: str, sp: float,
               lo: float, hi: float, kp: float = 1.0,
               ti: float = 60.0, rev: bool = False) -> Controller:
    """Factory mirroring the HMI constructor C(tag, desc, unit, sp, lo, hi, kp, ti, rev)."""
    return Controller(
        tag=tag, desc=desc, unit=unit,
        sp=sp, pv=sp, lo=lo, hi=hi, kp=kp, ti=ti, rev=rev,
        mode=MODE_AUTO, out=OUTPUT_DEFAULT, i=0.0,
    )


def manual_valve(tag: str, desc: str, unit: str, out: float = 50.0) -> Controller:
    """Factory for manual-only hand valves (HV 820, HV 803)."""
    return Controller(
        tag=tag, desc=desc, unit=unit, sp=0.0, pv=0.0,
        lo=0.0, hi=100.0, kp=0.0, ti=60.0, rev=False,
        mode=MODE_MANUAL, out=out, i=0.0, man=True,
    )
