from typing import List, Dict
from models.stream import Stream

def check_mass_balance(inflows: List[Stream], outflows: List[Stream], accumulation: float = 0.0) -> Dict[str, float]:
    """
    Check total mass balance: ΣIn - ΣOut = Accumulation
    Returns error metrics.
    """
    total_in = sum(s.mass_flow for s in inflows)
    total_out = sum(s.mass_flow for s in outflows)
    
    error = total_in - total_out - accumulation
    rel_error = abs(error) / max(total_in, 1e-9)
    
    return {
        "mass_balance_error": error,
        "relative_mass_error": rel_error,
        "is_converged": rel_error < 1e-4
    }

def check_component_balance(inflows: List[Stream], outflows: List[Stream], accumulation: Dict[str, float] = None) -> Dict[str, float]:
    """
    Check component-wise mass balance.
    """
    accumulation = accumulation or {}
    components = set()
    for s in inflows + outflows:
        components.update(s.composition.keys())
    
    errors = {}
    for comp in components:
        comp_in = sum(s.mass_flow * s.composition.get(comp, 0.0) for s in inflows)
        comp_out = sum(s.mass_flow * s.composition.get(comp, 0.0) for s in outflows)
        comp_acc = accumulation.get(comp, 0.0)
        
        error = comp_in - comp_out - comp_acc
        errors[f"{comp}_balance_error"] = error
        
    return errors

def check_energy_balance(inflows: List[Stream], outflows: List[Stream], heat_duty: float = 0.0, work: float = 0.0, accumulation: float = 0.0) -> Dict[str, float]:
    """
    Check energy balance: Σ(H_in * m_in) - Σ(H_out * m_out) + Q + W = dU/dt
    Units: H [J/kg], m [kg/s], Q [W], W [W], dU/dt [W]
    """
    energy_in = sum(s.mass_flow * s.enthalpy for s in inflows)
    energy_out = sum(s.mass_flow * s.enthalpy for s in outflows)
    
    error = energy_in - energy_out + heat_duty + work - accumulation
    rel_error = abs(error) / max(abs(energy_in) + abs(heat_duty) + abs(work), 1e-9)
    
    return {
        "energy_balance_error": error,
        "relative_energy_error": rel_error,
        "is_converged": rel_error < 1e-4
    }
