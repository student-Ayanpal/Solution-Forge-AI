from pydantic import BaseModel
from typing import List


class Technology(BaseModel):
    """A single technology recommendation for a specific category."""
    category: str
    technology: str
    reason: str


class CloudServices(BaseModel):
    """Cloud provider and specific services recommended."""
    provider: str
    services: List[str]


class Alternative(BaseModel):
    """An alternative technology option with justification for the primary choice."""
    category: str
    recommended: str
    alternative: str
    reason: str


class TradeOff(BaseModel):
    """Advantages and disadvantages for a key decision."""
    decision: str
    advantages: List[str]
    disadvantages: List[str]


class TechnologyRecommendation(BaseModel):
    """
    Complete technology recommendation produced by the Technology Advisor agent.
    This is the output contract passed to the Task Advisor and Delivery Planner.
    """
    technologies: List[Technology]
    cloud: CloudServices
    technology_strategy: str
    alternatives: List[Alternative]
    trade_offs: List[TradeOff]
    security_considerations: List[str]
    scalability_considerations: List[str]
    technology_risks: List[str]
    lock_in_considerations: List[str]
