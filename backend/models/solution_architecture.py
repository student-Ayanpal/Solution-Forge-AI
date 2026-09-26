from pydantic import BaseModel
from typing import List


class Component(BaseModel):
    """A single architectural component."""

    id: str
    name: str
    responsibility: str


class ArchitectureConnection(BaseModel):
    """Connection between two architectural components."""

    source: str
    target: str
    label: str | None = None


class DatabaseDesign(BaseModel):
    """Database layer specification."""

    type: str
    purpose: str


class CacheDesign(BaseModel):
    """Cache layer specification."""

    required: bool
    purpose: str


class SolutionArchitecture(BaseModel):
    """Structured output produced by the Solution Architect (SA) agent."""

    architecture_style: str

    components: List[Component]
    connections: List[ArchitectureConnection]

    database: DatabaseDesign
    cache: CacheDesign

    data_flow: List[str]

    security: List[str]

    scalability: List[str]

    mvp_architecture: List[str]

    future_evolution: List[str]

    architecture_rationale: str

    architecture_risks: List[str]