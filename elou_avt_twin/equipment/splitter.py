"""
splitter.py
===========
Stream splitter (разъединитель потока): divides a single inlet stream into N
outlet streams with mass and energy conservation.

Physical model (a header / manifold junction, no inventory):

  Σ m_out,i = m_in                       (mass conservation at the junction)
  w_out,i,c = w_in,c                     (component balance: composition is
                                         identical in every branch)
  h_out,i   = h_in                       (isenthalpic split: the junction does
                                         no work and no heat exchange, so every
                                         branch carries the inlet enthalpy)
  T_out,i = T_in,  P_out,i = P_junction  (one thermodynamic state, one common
                                         junction pressure)

The distribution of mass between the branches is NOT arbitrary: it follows the
downstream hydraulics -- each branch's resistance at the common junction
pressure (Q_i = f(dP_i, R_i)).  The engine's line solver computes those branch
flows and passes them as ``branch_flows`` (keyed by port ``out<i>``); the model
then normalises the split so the junction mass balance closes exactly:

  m_out,i = branch_i * (m_in / Σ branch)

When no hydraulic solution is available (isolated node, not solved line), the
fallback is an even split of the inlet flow -- mass- and energy-conserving, and
equivalent to N identical parallel branches.
"""

from typing import Any, Dict, List, Optional

from .base_equipment import BaseEquipment, EquipmentState
from models.stream import Stream


class Splitter(BaseEquipment):
    """
    Splitter of one feed stream into several product streams.
    """

    def __init__(self, equipment_id: str, params: Optional[Dict[str, Any]] = None):
        super().__init__(equipment_id, params or {})
        self._apply_params()

    def _apply_params(self) -> None:
        self.num_outputs = max(1, int(self.params.get("num_outputs", 2)))

    def step(self, dt: float, **inputs) -> Dict[str, Any]:
        """
        Inputs:
            inlet_stream: Stream — the single feed stream
            branch_flows: Dict[str, float] (optional) — per-port mass flows
                    {'out0': q0, 'out1': q1, ...} from the line solver (the
                    branch resistances at the common junction pressure).
            junction_pressure: float (optional) — common pressure of all
                    outlets, set by the hydraulic solver at the splitter node.

        Outputs:
            outlet_streams: List[Stream] — N branches, each a copy of the inlet
                    (same composition / temperature / enthalpy / density) with
                    its own mass flow; Σ flows == inlet flow by construction.
            flow_in / flow_out: total inlet / outlet mass flow.
        """
        inlet = inputs.get("inlet_stream")
        if inlet is None:
            return {"outlet_streams": [], "flow_in": 0.0, "flow_out": 0.0}
        if self.state.failed:
            return self._split(
                inlet,
                None,
                inputs.get("junction_pressure"),
            )
        return self._split(
            inlet,
            inputs.get("branch_flows"),
            inputs.get("junction_pressure"),
        )

    def _split(
        self,
        inlet: Stream,
        branch_flows: Optional[Dict[str, float]],
        junction_pressure: Optional[float],
    ) -> Dict[str, Any]:
        n = self.num_outputs
        total = max(0.0, inlet.mass_flow)
        flows: List[float] = [0.0] * n
        if branch_flows:
            assigned = 0.0
            for i in range(n):
                f = branch_flows.get(f"out{i}")
                if f is not None:
                    flows[i] = max(0.0, float(f))
                    assigned += flows[i]
            if assigned > 0.0:
                # Junction mass balance: scale the hydraulic shares so the sum
                # of the branch flows equals the inlet flow exactly.
                scale = total / assigned
                flows = [f * scale for f in flows]
            elif total > 0.0:
                # Hydraulic solution exists but carries no flow while the inlet
                # does -- inconsistent; keep mass conserved with an even split.
                flows = [total / n] * n
        else:
            # No hydraulic solution: neutral even split (N identical branches).
            flows = [total / n] * n
        outlets: List[Stream] = []
        for i in range(n):
            s = inlet.copy_with(name=f"{inlet.name}:out{i}", mass_flow=flows[i])
            if junction_pressure is not None:
                s = s.copy_with(pressure=float(junction_pressure))
            outlets.append(s)
        return {
            "outlet_streams": outlets,
            "flow_in": total,
            "flow_out": total,
        }

    def get_state(self) -> EquipmentState:
        self.state.extra["num_outputs"] = self.num_outputs
        return self.state

    def apply_action(self, action_type: str, value: Optional[float] = None) -> None:
        if action_type == "SET_VALUE" and value is not None:
            self.num_outputs = max(1, int(value))

    def reset(self) -> None:
        super().reset()
        self._apply_params()
