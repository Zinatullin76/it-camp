"""test_scheme_validation.py — ТЗ §45, §5: validate_scheme checks."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from scheme.model import ProcessScheme, SchemeNode, SchemeEdge
from scheme.validator import validate_scheme


def _valid():
    return ProcessScheme(nodes=[
        SchemeNode(id="src", type="source"),
        SchemeNode(id="p", type="pump",
                   params={"nominal_volumetric_flow_m3_s": 0.1}),
        SchemeNode(id="snk", type="sink"),
    ], edges=[
        SchemeEdge(id="e1", source="src", target="p"),
        SchemeEdge(id="e2", source="p", target="snk"),
    ])


def test_valid_scheme():
    res = validate_scheme(_valid())
    assert res.is_valid
    assert len(res.errors) == 0


def test_result_counts():
    res = validate_scheme(_valid())
    assert res.node_count == 3
    assert res.edge_count == 2


def test_duplicate_node_id():
    sc = _valid()
    sc.nodes.append(SchemeNode(id="p", type="valve"))
    res = validate_scheme(sc)
    assert not res.is_valid
    assert any(i.code == "DUPLICATE_NODE_ID" for i in res.issues)


def test_duplicate_edge_id():
    sc = _valid()
    sc.edges.append(SchemeEdge(id="e1", source="src", target="p"))
    res = validate_scheme(sc)
    assert any(i.code == "DUPLICATE_EDGE_ID" for i in res.issues)


def test_dangling_edge_source_and_target():
    sc = _valid()
    sc.edges.append(SchemeEdge(id="e3", source="ghost", target="snk"))
    sc.edges.append(SchemeEdge(id="e4", source="src", target="ghost"))
    res = validate_scheme(sc)
    assert any(i.code == "DANGLING_EDGE_SOURCE" for i in res.issues)
    assert any(i.code == "DANGLING_EDGE_TARGET" for i in res.issues)
    assert not res.is_valid


def test_invalid_source_port():
    sc = _valid()
    sc.edges[0].source_port = "bogus"
    res = validate_scheme(sc)
    assert any(i.code == "INVALID_SOURCE_PORT" for i in res.issues)


def test_invalid_target_port_for_elou():
    sc = _valid()
    sc.nodes[1] = SchemeNode(id="p", type="elou", params={"vessel_area": 30.0})
    sc.edges[1].target_port = "bogus"
    res = validate_scheme(sc)
    assert any(i.code == "INVALID_TARGET_PORT" for i in res.issues)


def test_isolated_process_node():
    sc = _valid()
    sc.nodes.append(SchemeNode(id="iso", type="valve",
                               params={"flow_coefficient_si": 0.01}))
    res = validate_scheme(sc)
    assert any(i.code == "ISOLATED_PROCESS_NODE" for i in res.issues)
    assert not res.is_valid


def test_missing_equipment_param_warning():
    sc = _valid()
    sc.nodes.append(SchemeNode(id="v", type="valve"))
    sc.edges.append(SchemeEdge(id="e3", source="p", target="v"))
    sc.edges.append(SchemeEdge(id="e4", source="v", target="snk"))
    res = validate_scheme(sc)
    assert any(i.code == "MISSING_EQUIPMENT_PARAM" for i in res.issues)
    assert res.is_valid  # missing params are warnings, not hard errors


def test_unknown_node_type_warning():
    sc = _valid()
    sc.nodes.append(SchemeNode(id="x", type="bogus"))
    res = validate_scheme(sc)
    assert any(i.code == "UNKNOWN_NODE_TYPE" for i in res.issues)


def test_source_without_output_warning():
    sc = _valid()
    sc.nodes.append(SchemeNode(id="src2", type="source"))
    res = validate_scheme(sc)
    assert any(i.code == "SOURCE_NO_OUTPUT" for i in res.issues)
