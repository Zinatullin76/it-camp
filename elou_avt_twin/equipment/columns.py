"""
columns.py
==========
Dedicated distillation column classes for the ELOU-AVT P&ID (K-1..K-4).

Each class specialises :class:`DistillationColumn` with the process defaults
of its scheme node (number of stages, feed stage, operating pressure, top
cut, alarm limits) so that a bare ``K1Column("column_K1")`` already matches
the process sheet without an explicit configuration dict.
"""

from typing import Any, Dict, Optional

from .distillation_column import DistillationColumn

KGFCM2 = 98066.5


def _c(temp_c: float) -> float:
    """Celsius -> Kelvin."""
    return temp_c + 273.15


def _kgf(n: float) -> float:
    """kgf/cm2 -> Pa."""
    return n * KGFCM2


class AtmosphericColumnK1(DistillationColumn):
    """K-1 atmospheric distillation column (crude oil)."""

    DEFAULT_PARAMS: Dict[str, Any] = {
        "num_stages": 28,
        "feed_stage": 16,
        "nominal_pressure": _kgf(2.0),
        "sump_area": 15.9,
        "initial_level": 2.5,
        "top_cut": ["frac_nk62", "frac_62_105", "water"],
        "solver_n_iter": 80,
        "limits": {
            "pressure_low": _kgf(1.0),
            "pressure_low_low": _kgf(0.8),
            "pressure_high": _kgf(4.5),
            "pressure_high_high": _kgf(4.8),
            "temperature_top_high": _c(250.0),
            "temperature_top_high_high": _c(270.0),
            "temperature_bottom_high": _c(300.0),
            "temperature_bottom_high_high": _c(320.0),
            "level_low": 1.0,
            "level_low_low": 0.6,
        },
    }

    def __init__(self, equipment_id: str, params: Optional[Dict[str, Any]] = None):
        merged = dict(self.DEFAULT_PARAMS)
        merged.update(params or {})
        super().__init__(equipment_id, merged)


class ColumnK2(DistillationColumn):
    """K-2 rectifying column (fuel-oil separation)."""

    DEFAULT_PARAMS: Dict[str, Any] = {
        "num_stages": 30,
        "feed_stage": 6,
        "nominal_pressure": _kgf(0.6),
        "sump_area": 19.63,
        "initial_level": 2.5,
        "top_cut": ["frac_105_180"],
        "solver_n_iter": 80,
        "solver_tol": 3e-3,
        "limits": {
            "pressure_low": _kgf(0.2),
            "pressure_low_low": _kgf(0.15),
            "pressure_high": _kgf(1.0),
            "pressure_high_high": _kgf(1.5),
            "temperature_top_high": _c(180.0),
            "temperature_top_high_high": _c(200.0),
            "temperature_bottom_high": _c(280.0),
            "temperature_bottom_high_high": _c(300.0),
            "level_low": 1.0,
            "level_low_low": 0.6,
        },
    }

    def __init__(self, equipment_id: str, params: Optional[Dict[str, Any]] = None):
        merged = dict(self.DEFAULT_PARAMS)
        merged.update(params or {})
        super().__init__(equipment_id, merged)


class StrippingColumnK3(DistillationColumn):
    """K-3 stripping column (K-3/1, K-3/2, K-3/3 side cuts).

    The ``variant`` parameter (1..3) selects the per-cut top composition and
    alarm limits; explicitly provided params always win over the defaults.
    """

    DEFAULT_PARAMS: Dict[str, Any] = {
        "num_stages": 10,
        "feed_stage": 5,
        "nominal_pressure": _kgf(3.0),
        "sump_area": 3.14,
        "initial_level": 2.0,
        "solver_n_iter": 80,
        "solver_tol": 3e-3,
        "limits": {
            "pressure_low": _kgf(1.5),
            "pressure_high": _kgf(4.5),
            "pressure_high_high": _kgf(5.0),
            "level_low": 0.8,
            "level_low_low": 0.5,
        },
    }

    VARIANTS: Dict[int, Dict[str, Any]] = {
        1: {
            "top_cut": ["frac_180_240"],
            "limits": {
                "temperature_top_high": _c(310.0),
                "temperature_top_high_high": _c(330.0),
                "temperature_bottom_high": _c(340.0),
                "temperature_bottom_high_high": _c(360.0),
            },
        },
        2: {
            "top_cut": ["frac_240_300"],
            "limits": {
                "temperature_top_high": _c(320.0),
                "temperature_top_high_high": _c(340.0),
                "temperature_bottom_high": _c(360.0),
                "temperature_bottom_high_high": _c(380.0),
            },
        },
        3: {
            "top_cut": ["frac_300_350"],
            "limits": {
                "temperature_top_high": _c(380.0),
                "temperature_top_high_high": _c(400.0),
                "temperature_bottom_high": _c(400.0),
                "temperature_bottom_high_high": _c(420.0),
            },
        },
    }

    def __init__(self, equipment_id: str, params: Optional[Dict[str, Any]] = None):
        params = params or {}
        variant = int(params.get("variant", 1))
        merged = dict(self.DEFAULT_PARAMS)
        variant_defaults = self.VARIANTS.get(variant, self.VARIANTS[1])
        merged["top_cut"] = list(variant_defaults["top_cut"])
        merged["limits"] = dict(merged["limits"])
        merged["limits"].update(variant_defaults["limits"])
        merged.update(params)
        super().__init__(equipment_id, merged)


class StabilizerColumnK4(DistillationColumn):
    """K-4 gasoline stabilizer."""

    DEFAULT_PARAMS: Dict[str, Any] = {
        "num_stages": 25,
        "feed_stage": 12,
        "nominal_pressure": _kgf(8.0),
        "sump_area": 4.52,
        "initial_level": 2.0,
        "top_cut": ["frac_nk62"],
        "solver_n_iter": 80,
        "solver_tol": 3e-3,
        "limits": {
            "pressure_low": _kgf(6.0),
            "pressure_low_low": _kgf(5.5),
            "pressure_high": _kgf(11.0),
            "pressure_high_high": _kgf(12.0),
            "temperature_top_high": _c(260.0),
            "temperature_top_high_high": _c(280.0),
            "temperature_bottom_high": _c(330.0),
            "temperature_bottom_high_high": _c(350.0),
            "level_low": 0.8,
            "level_low_low": 0.5,
        },
    }

    def __init__(self, equipment_id: str, params: Optional[Dict[str, Any]] = None):
        merged = dict(self.DEFAULT_PARAMS)
        merged.update(params or {})
        super().__init__(equipment_id, merged)


COLUMN_CLASSES: Dict[str, type] = {
    "column_K1": AtmosphericColumnK1,
    "column_K2": ColumnK2,
    "column_K3": StrippingColumnK3,
    "column_K4": StabilizerColumnK4,
}


def column_class_for(node_id: str, params: Optional[Dict[str, Any]] = None) -> type:
    """Pick the dedicated column class for a scheme node.

    A ``preset`` parameter (``k1``..``k4``, as written by the scheme editor for
    detailed columns) takes precedence, so a node carrying the K-1 preset gets
    the full :class:`AtmosphericColumnK1` even when its id is a generic
    ``col_N``.  Otherwise the ELOU-AVT node ids are matched (``column_K1``,
    ``column_K2``, ``column_K31``..``column_K33``, ``column_K4``); the K-3
    stripping variants share :class:`StrippingColumnK3`.  Falls back to the
    generic :class:`DistillationColumn` for unknown nodes.
    """
    preset = (params or {}).get("preset")
    if preset:
        p = str(preset).lower()
        if p.startswith("k1"):
            return AtmosphericColumnK1
        if p.startswith("k2"):
            return ColumnK2
        if p.startswith("k3"):
            return StrippingColumnK3
        if p.startswith("k4"):
            return StabilizerColumnK4
    nid = (node_id or "").lower()
    if nid.startswith("column_k1"):
        return AtmosphericColumnK1
    if nid.startswith("column_k2"):
        return ColumnK2
    if nid.startswith("column_k3"):
        return StrippingColumnK3
    if nid.startswith("column_k4"):
        return StabilizerColumnK4
    return DistillationColumn
