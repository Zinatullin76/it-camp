"""test_scheme.py — ТЗ §45, §4, §6: P&ID scheme model, JSON persistence, migration."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from scheme.model import (
    ProcessScheme, SchemeNode, SchemeEdge, SCHEMA_VERSION,
    load_scheme, save_scheme, migrate_scheme_data,
)


def _scheme():
    return ProcessScheme(
        id="t", schema_version=SCHEMA_VERSION,
        nodes=[
            SchemeNode(id="src", type="source"),
            SchemeNode(id="p", type="pump"),
        ],
        edges=[SchemeEdge(id="e1", source="src", target="p")],
    )


def test_schema_version():
    assert SCHEMA_VERSION == "1.1"


def test_default_scheme_loads():
    scheme = load_scheme()
    assert scheme.schema_version == SCHEMA_VERSION
    assert len(scheme.nodes) > 0
    assert len(scheme.edges) > 0


def test_add_node_duplicate_raises():
    sc = _scheme()
    with pytest.raises(ValueError):
        sc.add_node(SchemeNode(id="src", type="source"))


def test_remove_node_removes_edges():
    sc = _scheme()
    sc.remove_node("src")
    assert sc.node("src") is None
    assert len(sc.edges) == 0


def test_node_map_and_graph_queries():
    sc = _scheme()
    assert set(sc.node_map().keys()) == {"src", "p"}
    assert sc.edges_from("src")[0].target == "p"
    assert sc.edges_to("p")[0].source == "src"
    assert sc.node("nope") is None


def test_save_load_round_trip(tmp_path):
    sc = _scheme()
    path = save_scheme(sc, tmp_path / "scheme.json")
    sc2 = load_scheme(path)
    assert sc2.schema_version == SCHEMA_VERSION
    assert [n.id for n in sc2.nodes] == [n.id for n in sc.nodes]
    assert [e.id for e in sc2.edges] == [e.id for e in sc.edges]
    assert sc2.node("p").type == "pump"


def test_save_is_utf8_and_atomic(tmp_path):
    sc = _scheme()
    path = save_scheme(sc, tmp_path / "scheme.json")
    text = path.read_text(encoding="utf-8")
    assert text.startswith("{")
    assert not (tmp_path / "scheme.json.tmp").exists()


def test_migration_pump_and_valve_params():
    data = {
        "schema_version": "1.0",
        "nodes": [
            {"id": "p1", "type": "pump",
             "params": {"nominal_flow": 0.1, "delta_p": 5e5}},
            {"id": "v1", "type": "valve", "params": {"cv": 0.02}},
        ],
    }
    out = migrate_scheme_data(data)
    nodes = {n["id"]: n for n in out["nodes"]}
    assert nodes["p1"]["params"]["nominal_volumetric_flow_m3_s"] == 0.1
    assert nodes["p1"]["params"]["nominal_head_pa"] == 5e5
    assert nodes["v1"]["params"]["flow_coefficient_si"] == 0.02
    assert out["schema_version"] == SCHEMA_VERSION


def test_migration_preserves_unknown_keys():
    data = {
        "schema_version": "1.0",
        "nodes": [{"id": "x", "type": "pump",
                   "params": {"custom_flag": True, "nominal_flow": 0.2}}],
    }
    out = migrate_scheme_data(data)
    assert out["nodes"][0]["params"]["custom_flag"] is True
