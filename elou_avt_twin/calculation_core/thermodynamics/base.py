from abc import ABC, abstractmethod
from typing import Dict, Tuple
from models.stream import Phase

class ThermodynamicModel(ABC):
    """
    Abstract interface for thermodynamic calculations.
    """
    
    @abstractmethod
    def calculate_enthalpy(self, T: float, P: float, composition: Dict[str, float]) -> float:
        """Calculate specific enthalpy [J/kg]."""
        pass

    @abstractmethod
    def calculate_density(self, T: float, P: float, composition: Dict[str, float], phase: Phase) -> float:
        """Calculate density [kg/m^3]."""
        pass

    @abstractmethod
    def calculate_cp(self, T: float, P: float, composition: Dict[str, float]) -> float:
        """Calculate specific heat capacity [J/(kg*K)]."""
        pass

    @abstractmethod
    def calculate_vle(self, T: float, P: float, composition: Dict[str, float]) -> Tuple[float, Dict[str, float], Dict[str, float]]:
        """
        Perform Flash calculation.
        Returns: (vapor_fraction, liquid_composition, vapor_composition)
        """
        pass

class IdealThermodynamics(ThermodynamicModel):
    """
    MVP Ideal Thermodynamics using Antoine and polynomial Cp.

    This is an EXPLICITLY simplified model (ideal gas / ideal liquid, Raoult
    VLE), kept separate from the rigorous Peng-Robinson model.  The rigorous
    engine model is calculation_core.thermodynamics.pr_eos.
    """
    def __init__(self, components_data: Dict[str, Dict]):
        self.data = components_data

    def _require(self, comp: str) -> None:
        """Raise a clear error for unknown components (no fake defaults)."""
        if comp not in self.data:
            raise ValueError(
                f"Component '{comp}' has no property data in "
                f"IdealThermodynamics. Known components: {sorted(self.data.keys())}"
            )

    def calculate_cp(self, T: float, P: float, composition: Dict[str, float]) -> float:
        # Cp = Σ (xi * Cp_i),  Cp_i = a + b*T + c*T^2  [J/(kg*K)]
        total_cp = 0.0
        for comp, frac in composition.items():
            if frac == 0.0:
                continue
            self._require(comp)
            c = self.data[comp]["cp_coeffs"]
            cp_i = c[0] + c[1]*T + c[2]*(T**2)
            total_cp += frac * cp_i
        return total_cp

    def calculate_enthalpy(self, T: float, P: float, composition: Dict[str, float]) -> float:
        # H(T) = H(Tref) + integral(Tref..T) Cp(T') dT'
        # With Cp = a + b*T + c*T^2 this is the exact integral, which keeps
        # enthalpy thermodynamically consistent with the temperature-dependent
        # heat capacity (NOT the approximation H = Cp(T)*(T - Tref)).
        T_ref = 298.15
        h = 0.0
        for comp, frac in composition.items():
            if frac == 0.0:
                continue
            self._require(comp)
            a, b, c = self.data[comp]["cp_coeffs"]
            h_i = a * (T - T_ref) + 0.5 * b * (T**2 - T_ref**2) + (c / 3.0) * (T**3 - T_ref**3)
            h += frac * h_i
        return h

    def calculate_density(self, T: float, P: float, composition: Dict[str, float], phase: Phase) -> float:
        if phase == Phase.VAPOR:
            # Ideal gas: rho = P * M / (R * T)
            R = 8.314
            avg_molar_mass = 0.0
            for comp, frac in composition.items():
                if frac == 0.0:
                    continue
                self._require(comp)
                avg_molar_mass += frac * self.data[comp]["molar_mass"]
            return (P * avg_molar_mass) / (R * T)
        else:
            # Simplified liquid density with thermal expansion
            rho_ref = 0.0
            for comp, frac in composition.items():
                if frac == 0.0:
                    continue
                self._require(comp)
                rho_ref += frac * self.data[comp]["rho_ref"]
            alpha = 0.0008  # expansion coeff
            return rho_ref * (1 - alpha * (T - 298.15))

    def calculate_vle(self, T: float, P: float, composition: Dict[str, float]) -> Tuple[float, Dict[str, float], Dict[str, float]]:
        from .vle import solve_flash
        return solve_flash(T, P, composition, self.data)
