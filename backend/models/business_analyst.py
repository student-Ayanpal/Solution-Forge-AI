from pydantic import BaseModel
from typing import List

class BusinessAnalysis(BaseModel):
    """Structured output produced by the Business Analyst (BA) agent."""
    problem_statement: str
    users: List[str]
    stakeholders: List[str]
    functional_requirements: List[str]
    non_functional_requirements: List[str]
    mvp_scope: List[str]
    future_scope: List[str]
    constraints: List[str]
    assumptions: List[str]
    risks: List[str]
    open_questions: List[str]