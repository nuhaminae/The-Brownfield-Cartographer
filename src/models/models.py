# src/models/models.py
# The Brownfield Cartographer Models

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel


# --- Edge Model ---
class EdgeType(str, Enum):
    IMPORT = "import"
    SQL = "sql"
    DAG = "dag"


class Edge(BaseModel):
    source: str
    target: str
    type: EdgeType = EdgeType.IMPORT

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the Edge object into a dictionary for JSON export."""
        return self.model_dump()


# --- ClassNode Model ---
class ClassNode(BaseModel):
    name: str
    bases: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the ClassNode object into a dictionary for JSON export."""
        return self.model_dump()


# --- ModuleNode Model ---
class ModuleNode(BaseModel):
    path: str
    imports: List[str]
    functions: List[str]
    classes: List[ClassNode]

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the ModuleNode object into a dictionary for JSON export."""
        return self.model_dump()


# --- GraphSchema Model ---
class GraphSchema(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    pagerank: Dict[str, float] = {}
    circular_dependencies: List[List[str]] = []
    velocity: Dict[str, Any] = {}
    sources: List[str] = []
    sinks: List[str] = []
    blast_radius: Dict[str, int] = {}

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the GraphSchema object into a dictionary for JSON export."""
        return self.model_dump()
