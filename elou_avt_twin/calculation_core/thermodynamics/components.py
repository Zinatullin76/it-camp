"""
Standard component data for ELOU-AVT simulation.
A, B, C for Antoine: log10(P[Pa]) = A - B/(T + C)
cp_coeffs: [a, b, c] for Cp = a + b*T + c*T^2 [J/(kg*K)]
"""

COMPONENTS = {
    "oil": {
        "molar_mass": 0.250, # kg/mol (heavy crude average)
        "antoine_a": 9.5,
        "antoine_b": 2000.0,
        "antoine_c": -50.0,
        "cp_coeffs": [1800.0, 2.5, 0.001],
        "rho_ref": 870.0,
    },
    "water": {
        "molar_mass": 0.018,
        "antoine_a": 10.1,
        "antoine_b": 1687.0,
        "antoine_c": -43.0,
        "cp_coeffs": [4186.0, 0.0, 0.0],
        "rho_ref": 1000.0,
    },
    "salt": {
        "molar_mass": 0.058,
        "antoine_a": 0.0, # non-volatile
        "antoine_b": 0.0,
        "antoine_c": 0.0,
        "cp_coeffs": [880.0, 0.0, 0.0],
        "rho_ref": 2160.0,
    },
    "naphtha": {
        "molar_mass": 0.100,
        "antoine_a": 9.2,
        "antoine_b": 1200.0,
        "antoine_c": -45.0,
        "cp_coeffs": [2200.0, 3.0, 0.0],
        "rho_ref": 700.0,
    }
}
