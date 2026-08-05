"""
units.py
========
Physics Contract — canonical units and unit-conversion helpers.

PHASE 2 (physics contract).  Every physical quantity inside the calculation
core uses a single canonical unit:

    temperature      -> K         (Kelvin)
    pressure         -> Pa        (Pascal)
    mass flow        -> kg/s
    molar flow       -> mol/s
    volumetric flow  -> m^3/s
    specific enthalpy-> J/kg
    heat duty        -> W         (J/s)
    density          -> kg/m^3
    heat capacity    -> J/(kg*K)
    molecular weight -> kg/mol
    dynamic viscosity-> Pa*s
    time             -> s

Conversions below are the only place where unit transformations happen, so
units are never mixed ad hoc inside the calculation core.

Each helper documents: formula, physical meaning, units, applicability.
"""

from typing import Dict

# ---------------------------------------------------------------------------
# Canonical unit constants
# ---------------------------------------------------------------------------
KELVIN_ZERO_C = 273.15        # 0 degC = 273.15 K
BAR_TO_PA = 1.0e5             # 1 bar = 1e5 Pa
ATMOSPHERE_PA = 101325.0      # 1 atm = 101325 Pa


# ---------------------------------------------------------------------------
# Temperature / pressure
# ---------------------------------------------------------------------------

def celsius_to_kelvin(t_c: float) -> float:
    """T [K] = T [C] + 273.15.  Units: degC -> K."""
    return float(t_c) + KELVIN_ZERO_C


def kelvin_to_celsius(t_k: float) -> float:
    """T [C] = T [K] - 273.15.  Units: K -> degC."""
    return float(t_k) - KELVIN_ZERO_C


def bar_to_pa(p_bar: float) -> float:
    """P [Pa] = P [bar] * 1e5.  Units: bar -> Pa."""
    return float(p_bar) * BAR_TO_PA


def pa_to_bar(p_pa: float) -> float:
    """P [bar] = P [Pa] / 1e5.  Units: Pa -> bar."""
    return float(p_pa) / BAR_TO_PA


# ---------------------------------------------------------------------------
# Composition: mass fraction <-> mole fraction
# ---------------------------------------------------------------------------

def mass_to_mole_fractions(w: Dict[str, float], mw: Dict[str, float]) -> Dict[str, float]:
    """Convert mass fractions to mole fractions.

    Formula:
        x_i = (w_i / M_i) / sum_j (w_j / M_j)

    where w_i is the mass fraction of component i and M_i its molecular
    weight [kg/mol].  Mole fractions sum to 1 by construction.

    Units: w [-], mw [kg/mol] -> x [-].
    Applicability: w_i >= 0, sum(w) = 1, M_i > 0.
    Raises ValueError for a component missing from ``mw`` (no silent defaults).
    """
    _require_mw(w, mw)
    z = 0.0
    x = {}
    for c, wc in w.items():
        if wc > 0.0:
            x[c] = wc / mw[c]
            z += x[c]
    if z <= 0.0:
        raise ValueError("Cannot convert an empty or zero-mass composition to mole fractions")
    return {c: v / z for c, v in x.items()}


def mole_to_mass_fractions(x: Dict[str, float], mw: Dict[str, float]) -> Dict[str, float]:
    """Convert mole fractions to mass fractions.

    Formula:
        w_i = (x_i * M_i) / sum_j (x_j * M_j)

    Units: x [-], mw [kg/mol] -> w [-].
    Applicability: x_i >= 0, sum(x) = 1, M_i > 0.
    Raises ValueError for a component missing from ``mw``.
    """
    _require_mw(x, mw)
    z = 0.0
    w = {}
    for c, xc in x.items():
        if xc > 0.0:
            w[c] = xc * mw[c]
            z += w[c]
    if z <= 0.0:
        raise ValueError("Cannot convert an empty or zero-mole composition to mass fractions")
    return {c: v / z for c, v in w.items()}


def _require_mw(fracs: Dict[str, float], mw: Dict[str, float]) -> None:
    """Raise a clear error if a fraction references an unknown component."""
    for c in fracs:
        if c not in mw:
            raise ValueError(
                f"Component '{c}' has no molecular-weight data. "
                f"Known components: {sorted(mw.keys())}"
            )


# ---------------------------------------------------------------------------
# Flow conversions
# ---------------------------------------------------------------------------

def mass_to_molar_flow(mass_flow: float, mean_mw: float) -> float:
    """n [mol/s] = m [kg/s] / Mw [kg/mol].  Units: kg/s -> mol/s."""
    if mean_mw <= 0.0:
        raise ValueError("mean_mw must be > 0 to convert mass to molar flow")
    return mass_flow / mean_mw


def molar_to_mass_flow(molar_flow: float, mean_mw: float) -> float:
    """m [kg/s] = n [mol/s] * Mw [kg/mol].  Units: mol/s -> kg/s."""
    return molar_flow * mean_mw


def mass_to_volumetric_flow(mass_flow: float, density: float) -> float:
    """Q [m^3/s] = m [kg/s] / rho [kg/m^3].  Units: kg/s -> m^3/s."""
    if density <= 0.0:
        raise ValueError("density must be > 0 to convert mass to volumetric flow")
    return mass_flow / density


def volumetric_to_mass_flow(vol_flow: float, density: float) -> float:
    """m [kg/s] = Q [m^3/s] * rho [kg/m^3].  Units: m^3/s -> kg/s."""
    return vol_flow * density


def mean_molecular_weight(w: Dict[str, float], mw: Dict[str, float]) -> float:
    """Mean molecular weight of a mixture given mass fractions.

    Formula:
        Mw = 1 / sum_i (w_i / M_i)

    This is the mixture-averaged molecular weight consistent with the
    conversion mass_flow = molar_flow * Mw.
    Units: kg/mol.  Applicability: sum(w) = 1, M_i > 0.
    """
    _require_mw(w, mw)
    s = 0.0
    for c, wc in w.items():
        if wc > 0.0:
            s += wc / mw[c]
    if s <= 0.0:
        raise ValueError("Cannot compute mean molecular weight of an empty composition")
    return 1.0 / s
