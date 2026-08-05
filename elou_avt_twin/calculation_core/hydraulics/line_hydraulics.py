"""
line_hydraulics.py
==================
Steady-state hydraulic solver for serial process lines.

A serial line is a chain  source -> pump? -> {valve | pass-through}* -> sink
that carries a single mass flow.  For a given flow Q the net driving pressure
equals the sum of the quadratic valve resistances:

    P_src + H(Q) - P_sink - sum(dP_i(Q)) = 0

with valve resistance   dP_i(Q) = k_i * Q^2,   k_i = 1 / (rho * Cv^2 * x^2)
and pump head          H(Q)    = H_max * max(0, 1 - (Q / Q_ref)^2).

Because H(Q) is monotone decreasing and dP_i(Q) monotone increasing in Q, the
residual is strictly monotone decreasing, so bisection always converges.
"""

from typing import Callable, Dict, List, Optional, Tuple

MIN_OPENING = 1e-4
_MIN_FLOW = 1e-9


def valve_resistance(density: float, cv: float, opening: float, min_opening: float = MIN_OPENING) -> float:
    """Quadratic resistance coefficient k in dP = k * Q^2, Q in kg/s, dP in Pa."""
    x = max(min_opening, opening)
    return 1.0 / (density * cv * cv * x * x)


def bisection_root(
    f: Callable[[float], float],
    lo: float,
    hi: float,
    iters: int = 200,
    tol: float = 1e-9,
) -> float:
    """Root of a monotone-decreasing function on [lo, hi]; f(lo) > 0, f(hi) <= 0."""
    flo = f(lo)
    if flo <= 0.0:
        return lo
    fhi = f(hi)
    while fhi > 0.0:
        hi *= 2.0
        fhi = f(hi)
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if fm > 0.0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol * (abs(lo) + abs(hi) + 1e-30):
            break
    return 0.5 * (lo + hi)


def solve_serial_line(
    p_src: float,
    p_sink: float,
    density: float,
    valves: List[Tuple[str, float]],
    pump_head: Optional[Callable[[float], float]] = None,
    q_ref: float = 1.0,
    q_src_limit: Optional[float] = None,
) -> Tuple[float, Dict[str, float]]:
    """Solve the steady-state flow of one serial line.

    Parameters
    ----------
    p_src, p_sink : boundary pressures in Pa.
    density        : fluid density [kg/m3].
    valves         : list of (node_id, resistance k).
    pump_head      : Q -> discharge head [Pa]; None for no pump.
    q_ref          : reference flow for the pump curve (where head drops to 0).
    q_src_limit    : optional hard cap on the source flow (e.g. feed setpoint).

    Returns
    -------
    (Q, dP_by_node) : the line mass flow and the pressure drop per valve node.
    """
    total_k = sum(k for _, k in valves)
    if pump_head is None:
        def head(q: float) -> float:
            return 0.0
    else:
        head = pump_head

    def residual(q: float) -> float:
        return (p_src + head(q) - p_sink) - total_k * q * q

    q_hi = max(float(q_ref), 1.0)
    q = bisection_root(residual, 0.0, q_hi)
    if q < 0.0:
        q = 0.0
    if q_src_limit is not None:
        q = min(q, max(0.0, float(q_src_limit)))
    dP: Dict[str, float] = {}
    for nid, k in valves:
        dP[nid] = k * q * q
    return q, dP
