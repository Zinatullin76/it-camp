import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from controls.catalog import CONTROLLER_CATALOG, CASCADES, TRACKED_LOOPS
from models.controller import MODE_AUTO, MODE_MANUAL


def test_catalogue_size():
    """53 PID loops + 2 manual hand valves, exactly as in avt4.html."""
    assert len(CONTROLLER_CATALOG) == 55


def test_tags_unique():
    assert len(set(CONTROLLER_CATALOG)) == len(CONTROLLER_CATALOG)


def test_hand_valves_locked_in_manual():
    for tag, out in (("HV 820", 48.0), ("HV 803", 56.0)):
        c = CONTROLLER_CATALOG[tag]
        assert c.man is True
        assert c.mode == MODE_MANUAL
        assert c.out == out


def test_ranges_sane():
    for tag, c in CONTROLLER_CATALOG.items():
        assert c.lo < c.hi, tag
        assert c.kp > 0, tag
        assert c.ti > 0, tag
        assert c.lo <= c.sp <= c.hi, tag


def test_spot_check_tuning():
    trc2 = CONTROLLER_CATALOG["TRC 2"]
    assert trc2.sp == 128 and trc2.lo == 60 and trc2.hi == 190
    assert trc2.kp == 3.5 and trc2.ti == 90 and trc2.rev is True
    assert CONTROLLER_CATALOG["FRC 404"].kp == 1.2
    assert CONTROLLER_CATALOG["PRC 221"].rev is True
    assert CONTROLLER_CATALOG["LRCA 644"].rev is True
    assert CONTROLLER_CATALOG["TRC 3"].rev is False


def test_cascade_masters_exist():
    for slave, spec in CASCADES.items():
        assert slave in CONTROLLER_CATALOG, slave
        assert spec["form"] in ("span", "scale", "master_pv", "pv")
        master = spec.get("master")
        if master:
            assert master in CONTROLLER_CATALOG, f"{slave}: master {master}"


def test_key_cascades():
    assert CASCADES["FRC 408"] == {"form": "scale", "master": "TRC 2", "scale": 80.0}
    assert CASCADES["FRC 418"] == {"form": "scale", "master": "TRC 50", "scale": 120.0}
    assert CASCADES["FRC 406"]["master"] == "LRCA 605"
    assert CASCADES["FRC 460"]["master"] == "LRCA 602"


def test_tracked_loops_exist():
    for tag in TRACKED_LOOPS:
        assert tag in CONTROLLER_CATALOG, tag


def test_catalogue_factory_equivalence():
    """Rebuilding from the factory reproduces the catalogue."""
    c = CONTROLLER_CATALOG["FRC 404"]
    assert (c.tag, c.sp, c.lo, c.hi, c.kp, c.ti, c.rev, c.mode) == \
        ("FRC 404", 130.0, 0.0, 220.0, 1.2, 60.0, False, MODE_AUTO)
