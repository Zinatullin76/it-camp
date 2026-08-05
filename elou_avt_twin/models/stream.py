from pydantic import BaseModel, Field, field_validator
from typing import Dict, Optional, Literal
from enum import Enum

class Phase(str, Enum):
    LIQUID = "LIQUID"
    VAPOR = "VAPOR"
    TWO_PHASE = "TWO_PHASE"

# Maximum |sum(composition) - 1| tolerated before a Stream is rejected.
# Compositions are mass fractions and MUST sum to 1; no silent renormalisation.
COMPOSITION_TOLERANCE = 1e-6

class Stream(BaseModel):
    """
    Unified process stream model.

    Physics contract (PHASE 2):
      composition is ALWAYS mass fractions {component_id: fraction}, sum = 1.
      A composition that does not sum to 1 within COMPOSITION_TOLERANCE is
      rejected (no silent normalisation).

    Units:
        temperature     : Kelvin [K]
        pressure        : Pascal [Pa]
        mass_flow       : kg/s
        molar_flow      : mol/s
        volumetric_flow : m^3/s
        enthalpy        : J/kg
        density         : kg/m^3
        viscosity       : Pa*s
        composition     : mass fractions [-]
    """
    name: str = "Stream"
    temperature: float = Field(..., gt=0, description="Temperature in Kelvin")
    pressure: float = Field(..., gt=0, description="Pressure in Pascal")
    mass_flow: float = Field(..., ge=0, description="Mass flow in kg/s")
    molar_flow: Optional[float] = Field(None, ge=0, description="Molar flow in mol/s")
    volumetric_flow: Optional[float] = Field(None, ge=0, description="Volumetric flow in m^3/s")
    composition: Dict[str, float] = Field(default_factory=dict, description="Mass fractions")
    phase: Phase = Phase.LIQUID
    enthalpy: float = Field(0.0, description="Specific enthalpy in J/kg")
    density: float = Field(850.0, gt=0, description="Density in kg/m^3")
    viscosity: float = Field(0.001, gt=0, description="Dynamic viscosity in Pa*s")

    @field_validator('composition')
    @classmethod
    def validate_composition(cls, v: Dict[str, float]) -> Dict[str, float]:
        if not v:
            return v
        if any(val < 0.0 for val in v.values()):
            raise ValueError(
                f"Composition fractions must be non-negative, got {v}"
            )
        total = sum(v.values())
        if abs(total - 1.0) > COMPOSITION_TOLERANCE:
            raise ValueError(
                f"Composition (mass fractions) must sum to 1.0, got sum={total}. "
                f"Silent normalisation is not allowed; fix the input instead."
            )
        return v

    def validate_physics(self):
        """Perform additional physical sanity checks."""
        if self.temperature < 200 or self.temperature > 2000:
            raise ValueError(f"Temperature {self.temperature}K out of physical bounds [200, 2000]")
        if self.pressure < 100 or self.pressure > 1e8:
            raise ValueError(f"Pressure {self.pressure}Pa out of physical bounds [100, 1e8]")
        for comp, frac in self.composition.items():
            if frac < 0 or frac > 1:
                raise ValueError(f"Composition fraction for {comp} must be in [0, 1], got {frac}")

    def mole_fractions(self, mw: Dict[str, float]) -> Dict[str, float]:
        """Mole fractions of the stream's composition.

        ``mw`` maps component id -> molecular weight [kg/mol].  Raises a clear
        ValueError for any component missing from ``mw`` (no fake defaults).
        """
        from calculation_core.units import mass_to_mole_fractions
        return mass_to_mole_fractions(self.composition, mw)

    def mean_molar_mass(self, mw: Dict[str, float]) -> float:
        """Mass-fraction-averaged molecular weight [kg/mol] of the stream.

        Formula: Mw = 1 / sum_i (w_i / M_i).  Consistent with the identity
        mass_flow = molar_flow * Mw.
        """
        from calculation_core.units import mean_molecular_weight
        return mean_molecular_weight(self.composition, mw)

    def validate_consistency(self, mw: Optional[Dict[str, float]] = None,
                             tol: float = 1e-3) -> None:
        """Cross-check flow fields that are simultaneously specified.

        mass_flow [kg/s] <-> molar_flow [mol/s] (via Mw)
        mass_flow [kg/s] <-> volumetric_flow [m^3/s] (via density [kg/m^3])

        Raises ValueError when two specified quantities disagree by more than
        ``tol`` (relative to the larger reference).  Consistency checks are
        skipped for fields that are None.
        """
        if mw is not None and self.mass_flow is not None and self.molar_flow is not None:
            m_calc = self.molar_flow * self.mean_molar_mass(mw)
            ref = max(abs(self.mass_flow), abs(m_calc), 1e-9)
            if abs(m_calc - self.mass_flow) / ref > tol:
                raise ValueError(
                    f"Inconsistent flows: mass_flow={self.mass_flow} kg/s, "
                    f"molar_flow={self.molar_flow} mol/s with Mw gives "
                    f"{m_calc} kg/s."
                )
        if self.mass_flow is not None and self.volumetric_flow is not None:
            q_calc = self.mass_flow / max(self.density, 1e-12)
            ref = max(abs(self.volumetric_flow), abs(q_calc), 1e-9)
            if abs(q_calc - self.volumetric_flow) / ref > tol:
                raise ValueError(
                    f"Inconsistent flows: mass_flow={self.mass_flow} kg/s with "
                    f"density={self.density} kg/m^3 gives {q_calc} m^3/s, but "
                    f"volumetric_flow={self.volumetric_flow} m^3/s."
                )

    def copy_with(self, **kwargs) -> 'Stream':
        """Return a new stream with updated parameters."""
        data = self.model_dump()
        data.update(kwargs)
        return Stream(**data)
