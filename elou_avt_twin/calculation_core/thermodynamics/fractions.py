"""
fractions.py
============
Fractional pseudo-components for the ELOU-AVT scheme.

Real petroleum fractions replace the 4 lumped MVP components (oil/naphtha/
water/salt). Each hydrocarbon cut is described by its nominal normal boiling
point (NBP) and specific gravity (SG); critical properties (Tc, Pc, omega)
are taken from an n-alkane backbone table by matching NBP, which keeps the
Peng-Robinson EOS parameters physically consistent with real petroleum cuts.

Keys used by streams / scheme compositions:
    frac_nk62       НК-62  °C      (lightest naphtha overhead)
    frac_62_105     62-105 °C      (K-10 overhead)
    frac_105_180    105-180 °C     (K-3/1 kerosene cut)
    frac_180_240    180-240 °C
    frac_240_300    240-300 °C     (diesel)
    frac_300_350    300-350 °C     (VGO / gasoil)
    frac_mazut      >350   °C      (atmospheric residue)
    water           real H2O
    salt            non-volatile electrolyte (stays in the liquid)
"""

import numpy as np

# n-alkane backbone: (carbon number, Tb [K], Tc [K], Pc [bar], omega, MW [g/mol])
ALKANE_TABLE = [
    (1, 111.7, 190.6, 46.0, 0.011, 16.04),
    (2, 184.6, 305.4, 48.8, 0.099, 30.07),
    (3, 231.1, 369.8, 42.5, 0.153, 44.10),
    (4, 272.7, 425.1, 38.0, 0.201, 58.12),
    (5, 309.2, 469.7, 33.7, 0.251, 72.15),
    (6, 341.9, 507.4, 30.1, 0.301, 86.18),
    (7, 371.6, 540.2, 27.4, 0.349, 100.20),
    (8, 398.8, 568.7, 24.9, 0.398, 114.23),
    (9, 423.9, 594.6, 22.9, 0.443, 128.26),
    (10, 447.3, 617.7, 21.1, 0.492, 142.29),
    (11, 469.1, 639.0, 19.6, 0.533, 156.31),
    (12, 489.4, 658.0, 18.2, 0.576, 170.34),
    (13, 508.6, 676.0, 17.0, 0.618, 184.36),
    (14, 526.7, 693.0, 14.1, 0.659, 198.39),
    (15, 543.8, 708.0, 13.8, 0.707, 212.42),
    (16, 559.9, 723.0, 14.0, 0.717, 226.44),
    (17, 575.2, 736.0, 13.5, 0.770, 240.47),
    (18, 589.8, 747.0, 11.9, 0.789, 254.50),
    (19, 603.4, 758.0, 11.4, 0.827, 268.52),
    (20, 617.0, 768.0, 11.1, 0.907, 282.55),
    (22, 641.0, 789.0, 10.0, 1.000, 310.60),
    (24, 667.0, 804.0, 9.0, 1.100, 338.66),
    (28, 703.0, 830.0, 8.1, 1.300, 394.76),
    (32, 739.0, 850.0, 7.5, 1.500, 450.87),
    (36, 773.0, 870.0, 6.9, 1.700, 506.97),
]

_TB_ARRAY = np.array([r[1] for r in ALKANE_TABLE], dtype=float)
_N_ARRAY = np.array([r[0] for r in ALKANE_TABLE], dtype=float)
_TC_ARRAY = np.array([r[2] for r in ALKANE_TABLE], dtype=float)
_PC_ARRAY = np.array([r[3] for r in ALKANE_TABLE], dtype=float)
_OM_ARRAY = np.array([r[4] for r in ALKANE_TABLE], dtype=float)
_MW_ARRAY = np.array([r[5] for r in ALKANE_TABLE], dtype=float)


def equivalent_carbon_number(tb: float) -> float:
    """Interpolated carbon number of the n-alkane with the same NBP [K]."""
    if tb <= _TB_ARRAY[0]:
        return 1.0
    if tb >= _TB_ARRAY[-1]:
        return _N_ARRAY[-1]
    return float(np.interp(tb, _TB_ARRAY, _N_ARRAY))


def _prop(tb: float, arr: np.ndarray, log: bool = False) -> float:
    if log:
        if tb <= _TB_ARRAY[0]:
            return float(arr[0])
        if tb >= _TB_ARRAY[-1]:
            return float(arr[-1])
        return float(np.exp(np.interp(tb, _TB_ARRAY, np.log(arr))))
    if tb <= _TB_ARRAY[0]:
        return float(arr[0])
    if tb >= _TB_ARRAY[-1]:
        return float(arr[-1])
    return float(np.interp(tb, _TB_ARRAY, arr))


def estimate_mw(tb: float, sg: float) -> float:
    """Riazi-Daubert molecular weight [kg/mol] from NBP [K] and SG."""
    mw_g = 42.965 * np.exp(2.097e-4 * tb - 7.78712 * sg + 2.08476e-3 * tb * sg) \
        * tb ** 1.26007 * sg ** 4.98308
    return max(0.030, mw_g) / 1000.0


def hydrocarbon_props(tb: float, sg: float):
    """Return (MW kg/mol, Tc K, Pc Pa, omega, cp_a, cp_b) for a cut."""
    n = equivalent_carbon_number(tb)
    mw = estimate_mw(tb, sg)
    tc = _prop(tb, _TC_ARRAY)
    pc_bar = _prop(tb, _PC_ARRAY, log=True)
    omega = _prop(tb, _OM_ARRAY)
    cp_a = 3.0 + 0.9 * n
    cp_b = 0.05 + 0.012 * n
    return mw, tc, pc_bar * 1e5, omega, cp_a, cp_b


def _frac(name, tb, sg):
    mw, tc, pc, omega, cp_a, cp_b = hydrocarbon_props(tb, sg)
    return {
        "molar_mass": mw,
        "nbp": tb,
        "sg": sg,
        "tc": tc,
        "pc": pc,
        "omega": omega,
        "cp_a": cp_a,
        "cp_b": cp_b,
        "volatile": True,
        "category": "hydrocarbon",
    }


def _water():
    return {
        "molar_mass": 0.018015,
        "nbp": 373.15,
        "sg": 1.0,
        "tc": 647.1,
        "pc": 220.64e5,
        "omega": 0.3443,
        "cp_a": 32.20,
        "cp_b": 0.0019,
        "volatile": True,
        "category": "water",
    }


def _salt():
    return {
        "molar_mass": 0.05844,
        "nbp": 1750.0,
        "sg": 2.16,
        "tc": 5000.0,
        "pc": 1.0e6,
        "omega": 0.0,
        "cp_a": 880.0,
        "cp_b": 0.0,
        "volatile": False,
        "category": "salt",
    }


FRACTION_COMPONENTS = {
    "frac_nk62": _frac("frac_nk62", 322.0, 0.665),
    "frac_62_105": _frac("frac_62_105", 356.0, 0.710),
    "frac_105_180": _frac("frac_105_180", 414.0, 0.765),
    "frac_180_240": _frac("frac_180_240", 482.0, 0.815),
    "frac_240_300": _frac("frac_240_300", 542.0, 0.855),
    "frac_300_350": _frac("frac_300_350", 598.0, 0.905),
    "frac_mazut": _frac("frac_mazut", 700.0, 0.975),
    "water": _water(),
    "salt": _salt(),
}

# Ordered hydrocarbon fraction keys (light -> heavy). Used by the HC balance
# in check_quality and by the column fallback split logic.
HYDROCARBON_FRACTIONS = [
    "frac_nk62", "frac_62_105", "frac_105_180",
    "frac_180_240", "frac_240_300", "frac_300_350", "frac_mazut",
]

# Guard so the sum of all stream mass fractions never drifts (Stream model
# normalises anyway, but keeping it here documents the convention).
ALL_COMPONENTS = list(FRACTION_COMPONENTS.keys())
