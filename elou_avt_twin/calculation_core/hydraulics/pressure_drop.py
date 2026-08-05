import numpy as np
from typing import Optional

def calculate_pipe_pressure_drop(flow_rate: float, density: float, viscosity: float, length: float, diameter: float, roughness: float = 0.000045) -> float:
    """
    Darcy-Weisbach equation: ΔP = f * (L/D) * (ρ * v^2 / 2)
    """
    if flow_rate <= 0 or diameter <= 0:
        return 0.0
    
    area = np.pi * (diameter**2) / 4
    velocity = flow_rate / (density * area)
    
    # Reynolds number
    re = (density * velocity * diameter) / viscosity
    
    # Friction factor (Colebrook-White approximation or simple Haaland)
    if re < 2300:
        f = 64 / re
    else:
        # Haaland equation
        f = (1 / (-1.8 * np.log10((roughness/diameter/3.7)**1.11 + 6.9/re)))**2
        
    delta_p = f * (length / diameter) * (density * velocity**2 / 2)
    return delta_p

def calculate_valve_flow(cv: float, opening: float, delta_p: float, density: float) -> float:
    """
    Rigorous valve flow calculation.
    Q = Cv * f(opening) * sqrt(delta_p / SG)
    """
    if delta_p <= 0 or opening <= 0:
        return 0.0
    # Standard Cv is often in gpm/psi^0.5, we assume SI units: m^3/s / Pa^0.5
    # For MVP, we use linear characteristic f(x) = x
    vol_flow = cv * opening * np.sqrt(delta_p / density)
    return vol_flow
