import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import numpy as np
from models.stream import Stream, Phase
from calculation_core.thermodynamics.base import IdealThermodynamics
from calculation_core.thermodynamics.components import COMPONENTS
from calculation_core.validation.balance_checker import check_mass_balance, check_energy_balance
from equipment.pump import Pump
from equipment.heater import Heater

@pytest.fixture
def thermo():
    return IdealThermodynamics(COMPONENTS)

def test_stream_validation():
    """Test Stream model validation logic."""
    s = Stream(temperature=300, pressure=101325, mass_flow=10, composition={"oil": 1.0})
    s.validate_physics()
    assert s.mass_flow == 10
    
    with pytest.raises(ValueError):
        s_bad = Stream(temperature=10, pressure=101325, mass_flow=10)
        s_bad.validate_physics()

def test_mass_balance_checker():
    """Test mass balance utility."""
    s1 = Stream(temperature=300, pressure=101325, mass_flow=10, composition={"oil": 1.0})
    s2 = Stream(temperature=300, pressure=101325, mass_flow=5, composition={"oil": 1.0})
    s3 = Stream(temperature=300, pressure=101325, mass_flow=15, composition={"oil": 1.0})
    
    res = check_mass_balance([s1, s2], [s3])
    assert res["is_converged"] is True
    assert abs(res["mass_balance_error"]) < 1e-9

def test_pump_rigorous(thermo):
    """Test pump with energy balance."""
    s_in = Stream(temperature=300, pressure=101325, mass_flow=10, composition={"oil": 1.0})
    s_in.enthalpy = thermo.calculate_enthalpy(s_in.temperature, s_in.pressure, s_in.composition)
    
    pump = Pump("P1")
    pump.apply_action("TURN_ON")
    out = pump.step(1.0, inlet_stream=s_in, delta_p=5e5)
    
    s_out = out["outlet_stream"]
    assert s_out.pressure > s_in.pressure
    assert s_out.enthalpy > s_in.enthalpy
    
    # Check energy balance
    res = check_energy_balance([s_in], [s_out], work=out["power"])
    assert res["is_converged"] is True

def test_vle_rachford_rice(thermo):
    """Test VLE calculation."""
    # Mix of naphtha and oil at intermediate temp
    comp = {"naphtha": 0.5, "oil": 0.5}
    T = 380.0 # K (at 450K it was all vapor)
    P = 101325.0 # Pa
    
    beta, x, y = thermo.calculate_vle(T, P, comp)
    assert 0 < beta < 1, f"Expected two-phase at 380K, got beta={beta}"
    assert y["naphtha"] > x["naphtha"], "Naphtha should be enriched in vapor phase"
    assert x["oil"] > y["oil"], "Oil should be enriched in liquid phase"
