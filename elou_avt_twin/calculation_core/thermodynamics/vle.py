import numpy as np
from typing import Dict, Tuple
from scipy.optimize import newton

def calculate_k_values(T: float, P: float, components_data: Dict[str, Dict]) -> Dict[str, float]:
    """
    Calculate K-values using Antoine equation: log10(Psat) = A - B/(T + C)
    K_i = Psat_i / P
    T in Kelvin, P in Pascal.
    """
    k_values = {}
    for comp, data in components_data.items():
        a = data.get("antoine_a", 0)
        b = data.get("antoine_b", 0)
        c = data.get("antoine_c", 0)
        # Antoine often uses mmHg and Celsius, so we need to be careful.
        # Here we assume A, B, C are for log10(P[Pa]) and T[K].
        if a == 0: # Fallback for non-volatile
            k_values[comp] = 1e-10
            continue
        
        log10_psat = a - b / (T + c)
        psat = 10**log10_psat
        k_values[comp] = psat / P
    return k_values

def rachford_rice(beta: float, z: np.ndarray, k: np.ndarray) -> float:
    """
    Rachford-Rice equation: Σ [zi * (ki - 1) / (1 + beta * (ki - 1))] = 0
    """
    return np.sum(z * (k - 1) / (1 + beta * (k - 1)))

def solve_flash(T: float, P: float, z_mass: Dict[str, float], components_data: Dict[str, Dict]) -> Tuple[float, Dict[str, float], Dict[str, float]]:
    """
    Perform isothermal flash calculation.
    Returns: (vapor_fraction, x_mass, y_mass)
    """
    # 1. Convert mass fractions to molar fractions
    molar_masses = np.array([components_data[c].get("molar_mass", 0.1) for c in z_mass])
    z_mass_vals = np.array(list(z_mass.values()))
    z_molar = (z_mass_vals / molar_masses) / np.sum(z_mass_vals / molar_masses)
    
    # 2. Get K-values
    k_dict = calculate_k_values(T, P, components_data)
    k_vals = np.array([k_dict[c] for c in z_mass])
    # Guard against degenerate (all-involatile) systems producing inf/nan.
    k_vals = np.nan_to_num(k_vals, nan=1e-10, posinf=1e10, neginf=1e-10)
    k_vals = np.clip(k_vals, 1e-10, 1e10)

    # 3. Check if single phase
    f_0 = rachford_rice(0.0, z_molar, k_vals)
    f_1 = rachford_rice(1.0, z_molar, k_vals)

    if f_0 <= 0: # Subcooled liquid
        return 0.0, z_mass, z_mass
    if f_1 >= 0: # Superheated vapor
        return 1.0, z_mass, z_mass

    # 4. Solve for beta (vapor fraction)
    beta = 0.5
    try:
        beta = float(newton(rachford_rice, 0.5, args=(z_molar, k_vals), tol=1e-8))
    except Exception:
        # Fallback to bisection if Newton fails to converge.
        lo, hi = 0.0, 1.0
        flo = rachford_rice(lo, z_molar, k_vals)
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            fmid = rachford_rice(mid, z_molar, k_vals)
            if abs(fmid) < 1e-9:
                beta = mid
                break
            if flo * fmid < 0:
                hi = mid
            else:
                lo, flo = mid, fmid
            beta = mid

    beta = max(0.0, min(1.0, beta))
    
    # 5. Calculate phase compositions (molar)
    x_molar = z_molar / (1 + beta * (k_vals - 1))
    y_molar = k_vals * x_molar
    
    # 6. Convert back to mass fractions
    x_mass_vals = (x_molar * molar_masses) / np.sum(x_molar * molar_masses)
    y_mass_vals = (y_molar * molar_masses) / np.sum(y_molar * molar_masses)
    
    x_mass = dict(zip(z_mass.keys(), x_mass_vals))
    y_mass = dict(zip(z_mass.keys(), y_mass_vals))
    
    return float(beta), x_mass, y_mass
