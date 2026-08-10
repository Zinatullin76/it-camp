"""
validator.py
============
Scheme validation (ТЗ section 5).

``validate_scheme()`` checks the P&ID graph for structural and equipment-level
consistency and returns a ``SchemeValidationResult`` with a list of issues.
Validation is pure configuration checking — it never inspects runtime state.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple, Literal

from pydantic import BaseModel, Field

from scheme.model import ProcessScheme, SchemeEdge, SchemeNode

# Allowed node types (ТЗ section 4.1).
NODE_TYPES = {
    "pump",
    "valve",
    "angle_valve",
    "heater",
    "heat_exchanger",
    "furnace",
    "tank",
    "column",
    "elou",
    "junction",
    "source",
    "sink",
    "stream",
    "gate_valve",
    "separator",
    "separator_s1k",
    "mixer",
    "splitter",
}

# Boundary node types.
SOURCE_TYPES = {"source"}
SINK_TYPES = {"sink"}

# Process node types that must not be isolated (must have in/out edges).
PROCESS_TYPES = NODE_TYPES - SOURCE_TYPES - SINK_TYPES - {"junction", "stream"}

# Valid port names per node type.  Anything else is a schema error (the engine
# keys streams by '<node>:<port>', so a typo in a port silently disconnects the
# graph).  Unknown/extension types default to the generic "in"/"out" ports.
DEFAULT_PORTS = {"in", "out"}
PORT_SPECS: Dict[str, Set[str]] = {
    "heat_exchanger": {"in", "out", "hot_in", "hot_out", "cold_in", "cold_out"},
    "column": {
        "in", "out", "distillate", "bottoms", "feed", "overhead", "side_draw",
        "reflux", "circ", "steam", "feed1", "feed2", "feed3", "feed4",
    },
    "elou": {"in", "out", "brine", "water_in", "oil_out"},
    "tank": {"in", "out", "gas"},
    "separator": {"in", "out", "gas"},
    "separator_s1k": {"in_l", "in_r", "out_t", "out_b"},
    "mixer": {"out"},
    "splitter": {"in"},
}

# Required equipment parameters per node type (ТЗ section 5 "Equipment").
REQUIRED_PARAMS: Dict[str, List[str]] = {
    "pump": ["nominal_volumetric_flow_m3_s"],
    "valve": ["flow_coefficient_si"],
    "angle_valve": ["flow_coefficient_si"],
    "heat_exchanger": ["u", "area"],
    "heater": ["max_heat_duty"],
    "furnace": ["max_heat_duty"],
    "column": ["num_stages", "feed_stage", "nominal_pressure"],
    "elou": ["vessel_area"],
    "tank": ["vessel_area"],
    "separator": ["vessel_area"],
    "separator_s1k": ["vessel_area"],
}

# Legacy parameter aliases accepted in addition to the canonical names (so
# existing schemes still validate while new schemes must use canonical names).
LEGACY_ALIASES = {
    "pump": {"nominal_flow", "delta_p"},
    "valve": {"cv", "design_delta_p"},
    "angle_valve": {"cv", "design_delta_p"},
}


class ValidationIssue(BaseModel):
    """A single validation finding."""

    severity: Literal["error", "warning"]
    code: str
    node_id: Optional[str] = None
    edge_id: Optional[str] = None
    message: str


class SchemeValidationResult(BaseModel):
    """Result of scheme validation."""

    is_valid: bool
    issues: List[ValidationIssue] = Field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def as_dict(self) -> Dict:
        return {
            "is_valid": self.is_valid,
            "issues": [i.model_dump() for i in self.issues],
            "node_count": self.node_count,
            "edge_count": self.edge_count,
        }


def _ports_for(node: SchemeNode) -> Set[str]:
    return PORT_SPECS.get(node.type, DEFAULT_PORTS)


def _valid_port(node: SchemeNode, port: str, direction: str) -> bool:
    if port in _ports_for(node):
        return True
    # Многоотростковые колонны принимают произвольные входные порты
    # (in, in_2, ...), согласованные с хэндлами детальной мнемосхемы.
    if node.type == "column" and direction == "target" and port.startswith("in"):
        return True
    # Смеситель объединяет n потоков: входы in0, in1, ...
    if node.type == "mixer" and direction == "target" and port.startswith("in"):
        return True
    # Разъединитель делит поток на n ветвей: выходы out0, out1, ...
    if node.type == "splitter" and direction == "source" and port.startswith("out"):
        return True
    return False


def _missing_required_params(node: SchemeNode) -> List[str]:
    required = REQUIRED_PARAMS.get(node.type, [])
    aliases = LEGACY_ALIASES.get(node.type, set())
    if not required:
        return []
    missing = []
    for req in required:
        # A canonical param is satisfied by itself or by a legacy alias.
        if req in node.params:
            continue
        if aliases and any(a in node.params for a in aliases):
            continue
        missing.append(req)
    return missing


def validate_scheme(scheme: ProcessScheme) -> SchemeValidationResult:
    """Validate the topology and equipment configuration of a scheme.

    Checks (ТЗ section 5):
      - unique node / edge IDs;
      - edge source / target exist and their ports exist;
      - no dangling edges;
      - source/sink correctness;
      - process network connectivity (no isolated process nodes);
      - required equipment parameters.
    """
    issues: List[ValidationIssue] = []
    nodes = scheme.nodes
    edges = scheme.edges
    node_map: Dict[str, SchemeNode] = {n.id: n for n in nodes}

    # ---- unique IDs --------------------------------------------------------
    seen_ids: Set[str] = set()
    for n in nodes:
        if n.id in seen_ids:
            issues.append(ValidationIssue(
                severity="error", code="DUPLICATE_NODE_ID", node_id=n.id,
                message=f"Duplicate node id '{n.id}'.",
            ))
        seen_ids.add(n.id)
        if n.type not in NODE_TYPES:
            issues.append(ValidationIssue(
                severity="warning", code="UNKNOWN_NODE_TYPE", node_id=n.id,
                message=f"Node '{n.id}' has unknown type '{n.type}'; "
                        f"known types: {sorted(NODE_TYPES)}.",
            ))

    edge_ids: Set[str] = set()
    for e in edges:
        if e.id in edge_ids:
            issues.append(ValidationIssue(
                severity="error", code="DUPLICATE_EDGE_ID", edge_id=e.id,
                message=f"Duplicate edge id '{e.id}'.",
            ))
        edge_ids.add(e.id)

    # ---- edges reference existing nodes/ports ------------------------------
    for e in edges:
        src = node_map.get(e.source)
        if src is None:
            issues.append(ValidationIssue(
                severity="error", code="DANGLING_EDGE_SOURCE", edge_id=e.id,
                message=f"Edge '{e.id}' references missing source node '{e.source}'.",
            ))
        else:
            if not _valid_port(src, e.source_port, "source"):
                issues.append(ValidationIssue(
                    severity="error", code="INVALID_SOURCE_PORT", edge_id=e.id,
                    node_id=e.source,
                    message=f"Edge '{e.id}' uses source port '{e.source_port}' "
                            f"not valid for node type '{src.type}'.",
                ))
        tgt = node_map.get(e.target)
        if tgt is None:
            issues.append(ValidationIssue(
                severity="error", code="DANGLING_EDGE_TARGET", edge_id=e.id,
                message=f"Edge '{e.id}' references missing target node '{e.target}'.",
            ))
        else:
            if not _valid_port(tgt, e.target_port, "target"):
                issues.append(ValidationIssue(
                    severity="error", code="INVALID_TARGET_PORT", edge_id=e.id,
                    node_id=e.target,
                    message=f"Edge '{e.id}' uses target port '{e.target_port}' "
                            f"not valid for node type '{tgt.type}'.",
                ))

    # ---- boundary node correctness -----------------------------------------
    for n in nodes:
        if n.type in SOURCE_TYPES:
            if not any(e.source == n.id for e in edges):
                issues.append(ValidationIssue(
                    severity="warning", code="SOURCE_NO_OUTPUT", node_id=n.id,
                    message=f"Source node '{n.id}' has no outgoing edge.",
                ))
        if n.type in SINK_TYPES:
            if not any(e.target == n.id for e in edges):
                issues.append(ValidationIssue(
                    severity="warning", code="SINK_NO_INPUT", node_id=n.id,
                    message=f"Sink node '{n.id}' has no incoming edge.",
                ))

    # ---- connectivity: no isolated process nodes ---------------------------
    out_degree: Dict[str, int] = {}
    in_degree: Dict[str, int] = {}
    for e in edges:
        out_degree[e.source] = out_degree.get(e.source, 0) + 1
        in_degree[e.target] = in_degree.get(e.target, 0) + 1
    for n in nodes:
        if n.type not in PROCESS_TYPES:
            continue
        if in_degree.get(n.id, 0) == 0 and out_degree.get(n.id, 0) == 0:
            issues.append(ValidationIssue(
                severity="error", code="ISOLATED_PROCESS_NODE", node_id=n.id,
                message=f"Process node '{n.id}' is isolated (no in/out edges).",
            ))

    # ---- required equipment parameters -------------------------------------
    for n in nodes:
        missing = _missing_required_params(n)
        for req in missing:
            issues.append(ValidationIssue(
                severity="warning", code="MISSING_EQUIPMENT_PARAM", node_id=n.id,
                message=f"Node '{n.id}' (type '{n.type}') is missing required "
                        f"parameter '{req}'.",
            ))

    errors = [i for i in issues if i.severity == "error"]
    return SchemeValidationResult(
        is_valid=len(errors) == 0,
        issues=issues,
        node_count=len(nodes),
        edge_count=len(edges),
    )
