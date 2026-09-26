"""
backend/schemas/evaluation.py
=============================
Pydantic contracts for the Judge.

These are the types that `backend/judge/` was written against but which did
not exist in this repository. They are intentionally strict about *shape*
and lenient about *content*, because the criteria scores come from an LLM:

    CriterionEvaluation  -> one per rubric criterion, as scored by the LLM
    JudgeEvaluation      -> the Judge LLM's whole qualitative output
    HardConstraintCheck  -> one per deterministic Python check
    ScoredCriterion      -> CriterionEvaluation + its applied weight

`CriterionEvaluation.score` is clamped rather than validated, so a model that
returns 120 or -5 loses a retry round-trip instead of failing the task.
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field, field_validator


class CriterionEvaluation(BaseModel):
    """The Judge LLM's verdict on a single rubric criterion."""

    name: str = Field(
        description="Criterion name, exactly as given in the rubric.",
    )
    score: int = Field(
        default=0,
        description="0-100 for this criterion alone, before weighting.",
    )
    assessment: str = Field(
        default="",
        description="One short paragraph on how well the criterion is met.",
    )
    evidence: List[str] = Field(
        default_factory=list,
        description="Quotes/facts from the agent outputs that justify the score.",
    )
    issues: List[str] = Field(
        default_factory=list,
        description="Concrete problems found under this criterion.",
    )
    improvements: List[str] = Field(
        default_factory=list,
        description="Actionable changes that would raise this criterion.",
    )

    @field_validator("score", mode="before")
    @classmethod
    def _clamp_score(cls, v):
        """Clamp an out-of-range LLM score instead of failing validation."""
        try:
            numeric = int(round(float(v)))
        except (TypeError, ValueError):
            return 0
        return max(0, min(100, numeric))


class JudgeEvaluation(BaseModel):
    """Everything the Judge LLM is asked to return.

    Note the deliberate absence of an overall score: `backend/judge/scoring.py`
    computes the headline number in Python so it stays reproducible and
    auditable (see the "JUDGING PRINCIPLES" in the Judge prompt).
    """

    criteria: List[CriterionEvaluation] = Field(
        default_factory=list,
        description="One entry per rubric criterion, all nine of them.",
    )
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    critical_issues: List[str] = Field(default_factory=list)
    recommended_improvements: List[str] = Field(default_factory=list)
    cross_agent_consistency: str = Field(
        default="",
        description="How well BA / SA / TA / DP agree with each other.",
    )
    judge_summary: str = Field(
        default="",
        description="A concise overall verdict for a non-technical reader.",
    )


class HardConstraintCheck(BaseModel):
    """A deterministic, rule-based pass/fail check.

    `status` is PASS | WARN | FAIL. `severity` is CRITICAL | MAJOR | MINOR |
    INFO and only matters when the status is not PASS, because INFO carries a
    zero penalty in `backend/judge/rubric.py`.
    """

    constraint: str
    status: str
    severity: str = "INFO"
    evidence: str = ""
    recommendation: str = ""


class ScoredCriterion(BaseModel):
    """A CriterionEvaluation after its rubric weight has been applied."""

    name: str
    weight: float
    score: int
    weighted_score: float
    assessment: str = ""
    evidence: List[str] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)
    improvements: List[str] = Field(default_factory=list)
