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

from typing import Callable, Dict, List, Optional, Tuple, Any
import math

MIN_OPENING = 1e-4
_MIN_FLOW = 1e-9
INF = float("inf")

# Fallback resistance for a valve whose computed k is non-positive (e.g. a
# degenerate Cv).  Real valve resistances come from Cv at any opening, so this
# is only a guard against division errors, not a physics switch.
_K_EPS = 1e-8

# Flow below this is treated as "dead-headed" (zero), and the downstream of a
# dead-headed node is isolated at its own sink pressure.
ZERO_FLOW = 1e-6

# Absolute-pressure floor: the model works in absolute pressure, and a stream
# pressure of zero (or below) is physically a vacuum and rejected by the Stream
# model.  Solutions are clamped to stay above this.
P_FLOOR = 1000.0


def valve_resistance(density: float, cv: float, opening: float, min_opening: float = MIN_OPENING) -> float:
    """Quadratic resistance coefficient k in dP = k * Q^2, Q in kg/s, dP in Pa.

    A control valve is a flow restriction at ANY opening, including fully open:
    its discharge coefficient Cv fixes a minimum resistance k = 1/(rho * Cv^2)
    at x = 1, and closing the valve grows the resistance as 1/x^2.  This keeps
    the pressure-driven network bounded and well-conditioned (a real valve at
    100% still needs a finite pressure drop to push a given flow).  The
    min_opening floor keeps k finite near full closure.
    """
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
    for _ in range(200):
        if fhi <= 0.0:
            break
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
    valves: List[Tuple[str, float, bool]],
    pump_head: Optional[Callable[[float], float]] = None,
    q_ref: float = 1.0,
    q_src_limit: Optional[float] = None,
) -> Tuple[float, Dict[str, float]]:
    """Solve the steady-state flow of one serial line.

    Parameters
    ----------
    p_src, p_sink : boundary pressures in Pa.
    density        : fluid density [kg/m3].
    valves         : list of (node_id, resistance k, closed). A closed valve
                     isolates the line, so the flow is exactly zero and the
                     whole pump head stands in front of it.
    pump_head      : Q -> discharge head [Pa]; None for no pump.
    q_ref          : reference flow for the pump curve (where head drops to 0).
    q_src_limit    : optional hard cap on the source flow (e.g. feed setpoint).

    Returns
    -------
    (Q, dP_by_node) : the line mass flow and the pressure drop per valve node.
    """
    if any(closed for _, _, closed in valves):
        return 0.0, {nid: 0.0 for nid, _, _ in valves}
    total_k = sum(k for _, k, _ in valves)
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
    for nid, k, _ in valves:
        dP[nid] = k * q * q
    return q, dP


def solve_branched_network(
    p_src: float,
    q_src_limit: Optional[float],
    nodes: Dict[str, Dict[str, Any]],
    children: Dict[str, List[str]],
    root: str,
) -> Dict[str, Dict[str, float]]:
    """Solve the steady-state flow of a branched (tree) hydraulic network.

    The tree starts at a ``source`` (fixed pressure boundary) and fans out to
    one or more ``sink`` nodes, each at its own fixed (hard) pressure.  Elements
    in between are valves (quadratic resistance k), pumps (head H(Q)) or
    pass-throughs.  At every junction the pressure is common and the outgoing
    mass flows sum to the incoming one, so a fork splits its flow between the
    branches in inverse proportion to their resistance instead of evenly.

    The source is a hard pressure boundary: it always holds ``p_src`` and the
    network draws whatever flow its resistances allow.  ``q_src_limit`` caps
    that flow: past the limit the source pressure sags until the network draws
    exactly the limit.  A closed valve isolates everything downstream: the pump
    head stands in front of it and the downstream side sits at its own sink
    pressure.

    Parameters
    ----------
    p_src         : source boundary pressure [Pa].
    q_src_limit   : accepted for interface compatibility; not enforced (see above).
    nodes         : node_id -> element info dict.  Recognised types:
                        {"type": "source"}
                        {"type": "sink",  "sink_p": pressure [Pa]}
                        {"type": "valve", "k": resistance, "closed": bool}
                        {"type": "pump",  "head": Callable[[float], float] | None}
                        {"type": "res",   "k": resistance, "head": static term [Pa]}
                        {"type": "pass"}
    children      : node_id -> list of child node ids (sinks included).
    root          : the source node id.

    Returns
    -------
    nid -> {"flow": kg/s, "p_in": Pa, "p_out": Pa} for every node of the tree
    (sources, sinks and elements).
    """
    def subtree_flow(nid: str, p_in: float) -> float:
        """Total flow through the subtree rooted at nid given its inlet pressure."""
        info = nodes[nid]
        ntype = info["type"]
        if ntype == "sink":
            return 0.0
        kids = children.get(nid, [])
        if not kids:
            return 0.0
        if ntype == "valve":
            if info.get("closed"):
                return 0.0
            k = info["k"]
            if k <= 0.0:
                # Fully-open valve with zero resistance behaves as a
                # pass-through (children do not depend on its own flow).
                return sum(subtree_flow(c, p_in) for c in kids)
            sink_kids = [c for c in kids if nodes[c]["type"] == "sink"]
            if sink_kids:
                p_pin = nodes[sink_kids[0]]["sink_p"]
                return math.sqrt(max(0.0, (p_in - p_pin) / k))

            def residual(q: float) -> float:
                p_out = p_in - k * q * q
                return sum(subtree_flow(c, p_out) for c in kids) - q

            return bisection_root(residual, 0.0, 1.0)
        if ntype == "pump":
            head = info.get("head") or (lambda q: 0.0)
            sink_kids = [c for c in kids if nodes[c]["type"] == "sink"]
            if sink_kids:
                p_pin = nodes[sink_kids[0]]["sink_p"]

                def res_pump(q: float) -> float:
                    return head(q) + p_in - p_pin

                return bisection_root(res_pump, 0.0, 1.0)

            def residual_pump(q: float) -> float:
                return sum(subtree_flow(c, p_in + head(q)) for c in kids) - q

            return bisection_root(residual_pump, 0.0, 1.0)
        if ntype == "res":
            # Pipe / equipment resistance element: quadratic drop k·q^2 plus a
            # constant static-head term (ТЗ sections 15-17).
            k = info.get("k", 0.0)
            head = info.get("head", 0.0)
            sink_kids = [c for c in kids if nodes[c]["type"] == "sink"]
            if sink_kids:
                p_pin = nodes[sink_kids[0]]["sink_p"]
                if k > 0.0:
                    return math.sqrt(max(0.0, (p_in + head - p_pin) / k))
                return 0.0

            def residual_res(q: float) -> float:
                p_out = p_in + head - k * q * q
                return sum(subtree_flow(c, p_out) for c in kids) - q

            return bisection_root(residual_res, 0.0, 1.0)
        # Pass-through: the total flow is the sum of the children flows, which
        # do not depend on this node's own flow.
        return sum(subtree_flow(c, p_in) for c in kids)

    def root_flow(P: float) -> float:
        return sum(subtree_flow(c, P) for c in children.get(root, []))

    # Operating point: the source is a hard pressure boundary, so it always
    # holds its nominal pressure and the network draws whatever flow its
    # resistances allow.
    p_eff = p_src
    q_total = root_flow(p_src)

    # Source capacity: the source holds its pressure only while demand does not
    # exceed its throughput limit.  Past the limit it physically sags -- a feed
    # of fixed capacity cannot deliver more, so the pressure drops to the value
    # at which the network draws exactly the limit (mass-conserving).
    if q_src_limit is not None:
        q_lim = max(0.0, float(q_src_limit))
        if q_total > q_lim:
            if root_flow(P_FLOOR) <= q_lim:
                lo, hi = P_FLOOR, p_src
                for _ in range(100):
                    mid = 0.5 * (lo + hi)
                    if root_flow(mid) <= q_lim:
                        lo = mid
                    else:
                        hi = mid
                    if hi - lo <= 1e-6:
                        break
                p_eff = 0.5 * (lo + hi)
            else:
                p_eff = P_FLOOR
            q_total = q_lim

    result: Dict[str, Dict[str, float]] = {
        root: {"flow": q_total, "p_in": p_eff, "p_out": p_eff},
    }

    def max_sink_p(nid: str) -> float:
        best: Optional[float] = None
        for c in children.get(nid, []):
            if nodes[c]["type"] == "sink":
                v = nodes[c]["sink_p"]
            else:
                v = max_sink_p(c)
            best = v if best is None else max(best, v)
        return p_eff if best is None else best

    def walk_isolated(nid: str) -> None:
        for c in children.get(nid, []):
            if nodes[c]["type"] == "sink":
                result[c] = {
                    "flow": 0.0,
                    "p_in": nodes[c]["sink_p"],
                    "p_out": nodes[c]["sink_p"],
                }
            else:
                p = max_sink_p(c)
                result[c] = {"flow": 0.0, "p_in": p, "p_out": p}
                walk_isolated(c)

    def distribute(nid: str, p_in: float, q_in: float) -> None:
        """Distribute the source flow down a tree (mass-conserving).

        Each node carries exactly the flow its parent assigned to it (the
        source total, already fixed by the hard pressure boundary), the pump
        adds its head at that flow, valves drop what little pressure their
        resistance costs, and a fork splits the incoming flow between its
        branches in proportion to each branch's pressure-driven demand at the
        common junction pressure.  Because every branch is a share of one
        source total, mass is conserved by construction.
        """
        info = nodes[nid]
        ntype = info["type"]
        if ntype == "sink":
            return
        kids = children.get(nid, [])
        q = max(0.0, q_in)
        if ntype == "valve":
            if info.get("closed") or q <= ZERO_FLOW:
                result[nid] = {"flow": 0.0, "p_in": p_in, "p_out": max_sink_p(nid)}
                walk_isolated(nid)
                return
            p_out = p_in - info["k"] * q * q
            result[nid] = {"flow": q, "p_in": p_in, "p_out": p_out}
        elif ntype == "pump":
            head = info.get("head") or (lambda qq: 0.0)
            p_out = p_in + head(q)
            result[nid] = {"flow": q, "p_in": p_in, "p_out": p_out}
        elif ntype == "res":
            k = info.get("k", 0.0)
            head = info.get("head", 0.0)
            if q <= ZERO_FLOW:
                result[nid] = {"flow": 0.0, "p_in": p_in, "p_out": max_sink_p(nid)}
                walk_isolated(nid)
                return
            p_out = p_in + head - k * q * q
            result[nid] = {"flow": q, "p_in": p_in, "p_out": p_out}
        else:
            p_out = p_in
            result[nid] = {"flow": q, "p_in": p_in, "p_out": p_in}

        if not kids:
            return

        def branch_demand(c: str, p: float) -> float:
            if nodes[c]["type"] == "sink":
                # A sink fed directly through this node: demand is the flow the
                # node's own resistance would deliver to that sink pressure.
                k = info.get("k", 0.0)
                head = info.get("head", 0.0)
                if ntype in ("valve", "res") and k > 0.0:
                    return math.sqrt(max(0.0, (p + head - nodes[c]["sink_p"]) / k))
                return max(1.0, (p + head - nodes[c]["sink_p"]) / 1e5)
            return subtree_flow(c, p)

        def demand(p: float) -> float:
            return sum(branch_demand(c, p) for c in kids)

        # The branches share a common junction pressure.  The pump-level solve
        # already places it at p_out (branch demands summed to q by
        # construction), but that balance is knife-edge when a branch sits
        # exactly at a sink pressure, so re-derive it robustly here: the
        # junction pressure is the p in [p_out, p_in] at which the branches
        # draw exactly q.  demand(p) is monotone increasing, so bisect the
        # decreasing q - demand(p) with an absolute tolerance (the pressure
        # margins involved are tiny for near-zero-resistance branches).
        p_fork = p_out
        if demand(p_out) < q - 1e-9 and demand(p_in) > q + 1e-9:
            lo, hi = p_out, p_in
            for _ in range(300):
                mid = 0.5 * (lo + hi)
                if q - demand(mid) > 0.0:
                    lo = mid
                else:
                    hi = mid
                if hi - lo <= 1e-8:
                    break
            p_fork = 0.5 * (lo + hi)
        result[nid]["p_out"] = p_fork
        w_total = demand(p_fork)
        if w_total > 1e-12:
            for c in kids:
                w = branch_demand(c, p_fork)
                share = q * (w / w_total)
                if nodes[c]["type"] == "sink":
                    result[c] = {
                        "flow": share,
                        "p_in": nodes[c]["sink_p"],
                        "p_out": nodes[c]["sink_p"],
                    }
                else:
                    distribute(c, p_fork, share)
        elif q > ZERO_FLOW:
            # Degenerate case: no branch has any pressure-driven demand but the
            # node must still carry its assigned flow.  Split it evenly among
            # the live (reachable) branches so mass is never silently lost.
            live = [
                c for c in kids
                if nodes[c]["type"] != "sink" or p_fork > nodes[c]["sink_p"]
            ]
            if not live:
                live = list(kids)
            share = q / len(live)
            for c in kids:
                w = share if c in live else 0.0
                if nodes[c]["type"] == "sink":
                    result[c] = {
                        "flow": w,
                        "p_in": nodes[c]["sink_p"],
                        "p_out": nodes[c]["sink_p"],
                    }
                else:
                    distribute(c, p_fork, w)
        else:
            for c in kids:
                if nodes[c]["type"] == "sink":
                    result[c] = {
                        "flow": 0.0,
                        "p_in": nodes[c]["sink_p"],
                        "p_out": nodes[c]["sink_p"],
                    }
                else:
                    distribute(c, p_fork, 0.0)

    for c in children.get(root, []):
        total = max(q_total, root_flow(p_eff))
        if total <= 1e-12:
            continue  # nothing flows (dead-headed tree)
        weight = subtree_flow(c, p_eff)
        share = q_total * (weight / total)
        distribute(c, p_eff, share)

    # Clamp absolute pressures to the physical floor so no stream ends up at or
    # below vacuum (the Stream model rejects non-positive pressure).
    for v in result.values():
        if v["p_in"] < P_FLOOR:
            v["p_in"] = P_FLOOR
        if v["p_out"] < P_FLOOR:
            v["p_out"] = P_FLOOR
    return result
