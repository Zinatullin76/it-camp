import numpy as np

# Physical constants
R = 8.314 # J/(mol*K)
G = 9.81 # m/s^2

def calculate_flow_valve(cv: float, position: float, delta_p: float, density: float) -> float:
    """
    Calculate flow through a valve.
    Q = Cv * position * sqrt(delta_p / density)
    Units: Q [m^3/s], Cv [m^3/s / sqrt(Pa/(kg/m^3))], position [0-1], delta_p [Pa], density [kg/m^3]
    """
    if delta_p <= 0 or position <= 0:
        return 0.0
    return cv * position * np.sqrt(delta_p / density)

def calculate_pump_head(nominal_head: float, flow: float, nominal_flow: float) -> float:
    """
    Simplified pump curve: H = H_nom * (1 - (Q/Q_max)^2)
    """
    q_max = nominal_flow * 1.5
    if flow >= q_max:
        return 0.0
    return nominal_head * (1 - (flow / q_max)**2)

def calculate_heat_transfer(u: float, a: float, delta_t_lm: float) -> float:
    """
    Q = U * A * LMTD
    Units: Q [W], U [W/(m^2*K)], A [m^2], LMTD [K]
    """
    return u * a * delta_t_lm

def calculate_lmtd(t_hot_in: float, t_hot_out: float, t_cold_in: float, t_cold_out: float) -> float:
    """
    Logarithmic Mean Temperature Difference
    """
    dt1 = t_hot_in - t_cold_out
    dt2 = t_hot_out - t_cold_in
    if dt1 == dt2:
        return dt1
    if dt1 <= 0 or dt2 <= 0:
        return 0.0
    return (dt1 - dt2) / np.log(dt1 / dt2)

def calculate_temperature_change(heat_input: float, mass: float, cp: float, dt: float) -> float:
    """
    dT = (Q * dt) / (m * Cp)
    Units: dT [K], Q [W], m [kg], Cp [J/(kg*K)], dt [s]
    """
    if mass <= 0:
        return 0.0
    return (heat_input * dt) / (mass * cp)

def calculate_level_change(flow_in: float, flow_out: float, area: float, dt: float) -> float:
    """
    dh = (Q_in - Q_out) * dt / A
    Units: dh [m], Q [m^3/s], A [m^2], dt [s]
    """
    if area <= 0:
        return 0.0
    return (flow_in - flow_out) * dt / area

def calculate_pressure_change_gas(flow_in: float, flow_out: float, volume: float, temperature: float, dt: float) -> float:
    """
    Simplified gas pressure change based on ideal gas law: dP = (dm/dt) * R * T / (V * M)
    Assuming molar mass M ~ 0.029 kg/mol (air) for demo purposes, or similar.
    Let's use a generic compressibility factor for MVP.
    dP = (mass_flow_in - mass_flow_out) * dt * K / V
    """
    K = 1e5 # MVP generic factor
    if volume <= 0:
        return 0.0
    return (flow_in - flow_out) * dt * K / volume
