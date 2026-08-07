"""
scheme
======
Data model and persistence for the P&ID process scheme.

A scheme is a directed graph of typed nodes (equipment / sources / sinks)
connected by edges with explicit input/output ports.

The simulation engine walks this graph instead of using a hardcoded
equipment sequence, so the operator can build and connect new objects
on the frontend and the digital twin simulates the resulting topology.
"""

from .model import (
    SchemeNode,
    SchemeEdge,
    ProcessScheme,
    load_scheme,
    save_scheme,
    migrate_scheme_data,
    DEFAULT_SCHEME_PATH,
    SCHEMA_VERSION,
)
from .validator import validate_scheme, SchemeValidationResult, ValidationIssue

__all__ = [
    "SchemeNode",
    "SchemeEdge",
    "ProcessScheme",
    "load_scheme",
    "save_scheme",
    "migrate_scheme_data",
    "DEFAULT_SCHEME_PATH",
    "SCHEMA_VERSION",
    "validate_scheme",
    "SchemeValidationResult",
    "ValidationIssue",
]
