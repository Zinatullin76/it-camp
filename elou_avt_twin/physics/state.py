"""
state.py
========
PhysicsState and related runtime-physics data models (ТЗ section 8, 41, 42, 43).

These models hold the CURRENT process state of a simulation — they are the
opposite of the P&ID ``ProcessScheme``, which is pure configuration/topology.

Unit contract (ТЗ section 7) — everything here is canonical SI:
    temperature    -> K
    pressure       -> Pa      (absolute)
    mass flow      -> kg/s
    molar flow     -> mol/s
    volumetric flow-> m^3/s
    enthalpy       -> J/kg
    density        -> kg/m^3
    heat duty      -> W
    power          -> W
    pressure drop  -> Pa
    pump head      -> Pa
    level          -> m
    elevation      -> m
    time           -> s

The engine never stores runtime physics values inside ``ProcessScheme``
(ТЗ section 3) — they live here in ``PhysicsState``.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from models.base import SimulationState
from models.stream import Phase


class PhysicsStatus(str, Enum):
    """Overall physical status of one simulation step (ТЗ section 40)."""

    OK = "ok"
    WARNING = "warning"
    DEGRADED = "degraded"
    FAILED = "failed"


class SolverStatus(str, Enum):
    """Status of any numerical solver (ТЗ section 41).

    A solver may return CONVERGED, DEGRADED or FAILED.  A DEGRADED/FAILED
    result must never be presented as a normal physical result (ТЗ section 37).
    """

    CONVERGED = "converged"
    DEGRADED = "degraded"
    FAILED = "failed"


class BalanceStatus(str, Enum):
    """Status of the mass/component/energy balance gates (ТЗ section 40)."""

    OK = "ok"
    WARNING = "warning"
    FAILED = "failed"


class PhysicsDiagnostic(BaseModel):
    """Single physics diagnostic in a unified format (ТЗ section 42)."""

    severity: Literal["info", "warning", "error"]
    code: str
    component: str
    message: str
    value: Optional[float] = None
    limit: Optional[float] = None


class StreamState(BaseModel):
    """Runtime state of one process stream (ТЗ section 8)."""

    temperature_k: float
    pressure_pa: float
    mass_flow_kg_s: float
    composition: Dict[str, float] = Field(default_factory=dict)
    enthalpy_j_kg: Optional[float] = None
    density_kg_m3: Optional[float] = None
    phase: Phase = Phase.LIQUID


class NodeState(BaseModel):
    """Runtime state of one scheme node (ТЗ section 8)."""

    node_id: str
    streams: Dict[str, StreamState] = Field(default_factory=dict)
    values: Dict[str, float] = Field(default_factory=dict)


class PhysicsState(BaseModel):
    """Complete runtime physics state (ТЗ section 8)."""

    time_s: float = 0.0
    nodes: Dict[str, NodeState] = Field(default_factory=dict)
    streams: Dict[str, StreamState] = Field(default_factory=dict)
    diagnostics: List[PhysicsDiagnostic] = Field(default_factory=list)
    status: PhysicsStatus = PhysicsStatus.OK


class PumpOperatingPoint(BaseModel):
    """Pump/system operating point of one pump (ТЗ sections 21, 32)."""

    node_id: str
    flow_kg_s: float = 0.0
    volumetric_flow_m3_s: float = 0.0
    pressure_rise_pa: float = 0.0
    speed_fraction: float = 1.0
    npsha_pa: Optional[float] = None
    npshr_pa: Optional[float] = None
    cavitating: bool = False
    on_curve: bool = True


class HydraulicResult(BaseModel):
    """Result of the hydraulic network solve (ТЗ sections 24, 25, 28)."""

    status: SolverStatus = SolverStatus.CONVERGED
    iterations: int = 0
    residual: float = 0.0
    tolerance: float = 1e-6
    node_pressures: Dict[str, float] = Field(default_factory=dict)
    edge_flows: Dict[str, float] = Field(default_factory=dict)
    pressure_drops: Dict[str, float] = Field(default_factory=dict)
    pump_operating_points: List[PumpOperatingPoint] = Field(default_factory=list)
    diagnostics: List[PhysicsDiagnostic] = Field(default_factory=list)


class BalanceCheck(BaseModel):
    """Mass/component/energy balance residuals of one step (ТЗ sections 38-40)."""

    mass_residual_kg_s: float = 0.0
    mass_relative: float = 0.0
    component_residuals: Dict[str, float] = Field(default_factory=dict)
    component_relative: float = 0.0
    energy_residual_w: float = 0.0
    energy_relative: float = 0.0
    status: BalanceStatus = BalanceStatus.OK


class SimulationResult(BaseModel):
    """Full result of ``engine.step()`` (ТЗ section 43).

    ``engine.step()`` must never silently mutate global state without
    returning a result + diagnostics.
    """

    time_s: float = 0.0
    state: SimulationState = Field(default_factory=SimulationState)
    solver_status: SolverStatus = SolverStatus.CONVERGED
    diagnostics: List[PhysicsDiagnostic] = Field(default_factory=list)
    balance_status: BalanceStatus = BalanceStatus.OK
    balance: Optional[BalanceCheck] = None
    hydraulic: Optional[HydraulicResult] = None
