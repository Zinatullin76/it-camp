"""
model.py
========
Pydantic models for the P&ID scheme graph plus JSON persistence.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field

logger = logging.getLogger("elou_avt.scheme")

DEFAULT_SCHEME_PATH = Path(__file__).resolve().parent.parent / "schemes" / "process_elou_avt.json"


class SchemeNode(BaseModel):
    """A single object on the scheme canvas."""

    id: str
    type: str = "pump"
    name: str = ""
    x: float = 0.0
    y: float = 0.0
    params: Dict[str, Any] = Field(default_factory=dict)


class SchemeEdge(BaseModel):
    """A connection between two nodes, routed through explicit ports."""

    id: str
    source: str
    target: str
    source_port: str = "out"
    target_port: str = "in"
    kind: str = "process"


class ProcessScheme(BaseModel):
    """The full scheme graph."""

    id: str = "default"
    name: str = "ЭЛОУ-АВТ / default"
    nodes: List[SchemeNode] = Field(default_factory=list)
    edges: List[SchemeEdge] = Field(default_factory=list)

    def node(self, node_id: str) -> Optional[SchemeNode]:
        return next((n for n in self.nodes if n.id == node_id), None)

    def node_map(self) -> Dict[str, SchemeNode]:
        return {n.id: n for n in self.nodes}

    def edges_from(self, node_id: str) -> List[SchemeEdge]:
        return [e for e in self.edges if e.source == node_id]

    def edges_to(self, node_id: str) -> List[SchemeEdge]:
        return [e for e in self.edges if e.target == node_id]

    def add_node(self, node: SchemeNode) -> None:
        if self.node(node.id) is not None:
            raise ValueError(f"Node '{node.id}' already exists")
        self.nodes.append(node)

    def remove_node(self, node_id: str) -> None:
        self.nodes = [n for n in self.nodes if n.id != node_id]
        self.edges = [e for e in self.edges if e.source != node_id and e.target != node_id]

    def add_edge(self, edge: SchemeEdge) -> None:
        self.edges.append(edge)


def load_scheme(path: Optional[Path | str] = None) -> ProcessScheme:
    """Load a scheme from a JSON file (falls back to the default scheme)."""
    path = Path(path) if path else DEFAULT_SCHEME_PATH
    if not path.exists():
        logger.warning("Scheme file %s not found; using empty scheme.", path)
        return ProcessScheme()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ProcessScheme.model_validate(data)
    except Exception:
        logger.exception("Failed to load scheme from %s; using empty scheme.", path)
        return ProcessScheme()


def save_scheme(scheme: ProcessScheme, path: Optional[Path | str] = None) -> Path:
    """Persist a scheme to a JSON file."""
    path = Path(path) if path else DEFAULT_SCHEME_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(scheme.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
    logger.info("Scheme saved to %s (%d nodes, %d edges).", path, len(scheme.nodes), len(scheme.edges))
    return path
