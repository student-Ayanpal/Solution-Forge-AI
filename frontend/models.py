"""
models.py
=========
Plain-Python mirrors of the Pydantic models the backend team already agreed
on (see the team's shared "TA.txt" contract doc). These are NOT used for
validation here (validators.py owns frontend validation) — they exist so
that:

  1. The backend engineer can see, in one place, the exact field names and
     types the frontend expects in every API response.
  2. The frontend code (views/*.py) can use dot-style access with sensible
     defaults instead of scattering `.get("x", {}).get("y", [])` everywhere.

If the backend's real Pydantic models ever rename a field, update the
`.get(...)` keys in `from_dict` below AND the docstring in config.py so the
two stay in sync.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _join_items(items: Any) -> str:
    """Helper: join a list of strings into one comma-separated string."""
    if isinstance(items, str):
        return items
    if isinstance(items, (list, tuple)):
        return ", ".join(str(item) for item in items if item)
    return ""


def _as_float(value: Any) -> float:
    """Coerce anything to a float, defaulting to 0.0.

    The judge's numbers come back as JSON floats, but MongoDB has no
    guaranteed decimal type, so an int can turn up where a float is expected.
    """
    if isinstance(value, bool) or value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_optional_float(value: Any) -> Optional[float]:
    """Like _as_float, but None stays None so 'no score' is distinguishable
    from a score of zero."""
    if value is None:
        return None
    return _as_float(value)


# ---------------------------------------------------------------------------
# UserInput — sent BY the frontend TO the backend (POST /consultations)
# ---------------------------------------------------------------------------
@dataclass
class UserInput:
    business_idea: str
    technology_preference: str
    cloud_preference: str
    expected_daily_traffic: int
    delivery_timeline_months: int
    data_hosting_country: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "business_idea": self.business_idea,
            "technology_preference": self.technology_preference,
            "cloud_preference": self.cloud_preference,
            "expected_daily_traffic": self.expected_daily_traffic,
            "delivery_timeline_months": self.delivery_timeline_months,
            "data_hosting_country": self.data_hosting_country,
        }


# ---------------------------------------------------------------------------
# Agent outputs — received FROM the backend (GET /consultations/{id}/result)
# ---------------------------------------------------------------------------
@dataclass
class BusinessAnalysis:
    problem_statement: str = ""
    users: List[str] = field(default_factory=list)
    stakeholders: List[str] = field(default_factory=list)
    functional_requirements: List[str] = field(default_factory=list)
    non_functional_requirements: List[str] = field(default_factory=list)
    mvp_scope: List[str] = field(default_factory=list)
    future_scope: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "BusinessAnalysis":
        d = d or {}
        return BusinessAnalysis(
            problem_statement=d.get("problem_statement", ""),
            users=d.get("users", []),
            stakeholders=d.get("stakeholders", []),
            functional_requirements=d.get("functional_requirements", []),
            non_functional_requirements=d.get("non_functional_requirements", []),
            mvp_scope=d.get("mvp_scope", []),
            future_scope=d.get("future_scope", []),
            constraints=d.get("constraints", []),
            assumptions=d.get("assumptions", []),
            risks=d.get("risks", []),
            open_questions=d.get("open_questions", []),
        )


@dataclass
class SolutionArchitecture:
    architecture_style: str = ""
    components: List[Dict[str, str]] = field(default_factory=list)
    connections: List[Dict[str, str]] = field(default_factory=list)
    database: Dict[str, str] = field(default_factory=dict)
    cache: Dict[str, Any] = field(default_factory=dict)
    data_flow: List[str] = field(default_factory=list)
    security: List[str] = field(default_factory=list)
    scalability: List[str] = field(default_factory=list)
    mvp_architecture: List[str] = field(default_factory=list)
    future_evolution: List[str] = field(default_factory=list)
    architecture_rationale: str = ""
    architecture_risks: List[str] = field(default_factory=list)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "SolutionArchitecture":
        d = d or {}
        return SolutionArchitecture(
            architecture_style=d.get("architecture_style", ""),
            components=d.get("components", []),
            connections=d.get("connections", []),
            database=d.get("database", {}),
            cache=d.get("cache", {}),
            data_flow=d.get("data_flow", []),
            security=d.get("security", []),
            scalability=d.get("scalability", []),
            mvp_architecture=d.get("mvp_architecture", []),
            future_evolution=d.get("future_evolution", []),
            architecture_rationale=d.get("architecture_rationale", ""),
            architecture_risks=d.get("architecture_risks", []),
        )


@dataclass
class TechnologyRecommendation:
    technologies: List[Dict[str, str]] = field(default_factory=list)
    cloud: Dict[str, Any] = field(default_factory=dict)
    technology_strategy: str = ""
    alternatives: List[Dict[str, str]] = field(default_factory=list)
    trade_offs: List[Dict[str, Any]] = field(default_factory=list)
    security_considerations: List[str] = field(default_factory=list)
    scalability_considerations: List[str] = field(default_factory=list)
    technology_risks: List[str] = field(default_factory=list)
    lock_in_considerations: List[str] = field(default_factory=list)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "TechnologyRecommendation":
        d = d or {}
        return TechnologyRecommendation(
            technologies=d.get("technologies", []),
            cloud=d.get("cloud", {}),
            technology_strategy=d.get("technology_strategy", ""),
            alternatives=d.get("alternatives", []),
            trade_offs=d.get("trade_offs", []),
            security_considerations=d.get("security_considerations", []),
            scalability_considerations=d.get("scalability_considerations", []),
            technology_risks=d.get("technology_risks", []),
            lock_in_considerations=d.get("lock_in_considerations", []),
        )


@dataclass
class DeliveryPlan:
    workstreams: List[Dict[str, Any]] = field(default_factory=list)
    team_roles: List[Dict[str, Any]] = field(default_factory=list)
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    milestones: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    risks: List[Dict[str, str]] = field(default_factory=list)
    testing_strategy: List[str] = field(default_factory=list)
    deployment_strategy: str = ""
    release_strategy: str = ""
    future_evolution: List[str] = field(default_factory=list)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "DeliveryPlan":
        d = d or {}
        return DeliveryPlan(
            workstreams=d.get("workstreams", []),
            team_roles=d.get("team_roles") or d.get("team", []),
            timeline=d.get("timeline", []),
            milestones=d.get("milestones", []),
            dependencies=d.get("dependencies", []),
            risks=d.get("risks", []),
            testing_strategy=d.get("testing_strategy", []),
            deployment_strategy=d.get("deployment_strategy") or _join_items(d.get("deployment_plan", [])),
            release_strategy=d.get("release_strategy", ""),
            future_evolution=d.get("future_evolution") or d.get("future_scope", []),
        )


@dataclass
class JudgeCriterion:
    """One rubric criterion as scored by the Judge."""

    name: str = ""
    weight: float = 0.0
    score: int = 0
    weighted_score: float = 0.0
    assessment: str = ""
    evidence: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    improvements: List[str] = field(default_factory=list)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "JudgeCriterion":
        d = d or {}
        return JudgeCriterion(
            name=d.get("name", ""),
            weight=_as_float(d.get("weight")),
            score=int(_as_float(d.get("score"))),
            weighted_score=_as_float(d.get("weighted_score")),
            assessment=d.get("assessment", ""),
            evidence=d.get("evidence") or [],
            issues=d.get("issues") or [],
            improvements=d.get("improvements") or [],
        )


@dataclass
class HardConstraintCheck:
    """A deterministic PASS/WARN/FAIL check produced by the backend."""

    constraint: str = ""
    status: str = ""
    severity: str = ""
    evidence: str = ""
    recommendation: str = ""

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "HardConstraintCheck":
        d = d or {}
        return HardConstraintCheck(
            constraint=d.get("constraint", ""),
            status=(d.get("status") or "").upper(),
            severity=(d.get("severity") or "").upper(),
            evidence=d.get("evidence") or d.get("detail") or "",
            recommendation=d.get("recommendation") or "",
        )


@dataclass
class JudgeEvaluation:
    """The full judge_output dict from the backend.

    Mirrors what `backend/judge/judge.py::build_judge_output` returns, which
    is also what `backend/utils/blueprint_generator.py::render_judge` renders.
    """

    overall_score: Optional[float] = None
    quality_band: str = ""
    quality_band_description: str = ""
    raw_weighted_score: Optional[float] = None
    constraint_penalty: Optional[float] = None
    scoring_explanation: str = ""
    judge_status: str = ""
    judge_summary: str = ""
    cross_agent_consistency: str = ""
    criteria: List[JudgeCriterion] = field(default_factory=list)
    hard_constraint_checks: List[HardConstraintCheck] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    critical_issues: List[str] = field(default_factory=list)
    recommended_improvements: List[str] = field(default_factory=list)
    failed_constraints: List[str] = field(default_factory=list)
    warned_constraints: List[str] = field(default_factory=list)
    criteria_missing: List[str] = field(default_factory=list)
    llm_evaluation_available: bool = False

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "JudgeEvaluation":
        d = d or {}
        return JudgeEvaluation(
            overall_score=_as_optional_float(d.get("overall_score")),
            quality_band=d.get("quality_band", ""),
            quality_band_description=d.get("quality_band_description", ""),
            raw_weighted_score=_as_optional_float(d.get("raw_weighted_score")),
            constraint_penalty=_as_optional_float(d.get("constraint_penalty")),
            scoring_explanation=d.get("scoring_explanation", ""),
            judge_status=d.get("judge_status", ""),
            judge_summary=d.get("judge_summary", ""),
            cross_agent_consistency=d.get("cross_agent_consistency", ""),
            criteria=[JudgeCriterion.from_dict(c) for c in (d.get("criteria") or [])
                      if isinstance(c, dict)],
            hard_constraint_checks=[
                HardConstraintCheck.from_dict(c)
                for c in (d.get("hard_constraint_checks") or [])
                if isinstance(c, dict)
            ],
            strengths=d.get("strengths") or [],
            weaknesses=d.get("weaknesses") or [],
            critical_issues=d.get("critical_issues") or [],
            recommended_improvements=d.get("recommended_improvements") or [],
            failed_constraints=d.get("failed_constraints") or [],
            warned_constraints=d.get("warned_constraints") or [],
            criteria_missing=d.get("criteria_missing") or [],
            llm_evaluation_available=bool(d.get("llm_evaluation_available")),
        )

    @property
    def failed_count(self) -> int:
        return sum(1 for c in self.hard_constraint_checks if c.status == "FAIL")

    @property
    def warned_count(self) -> int:
        return sum(1 for c in self.hard_constraint_checks if c.status == "WARN")


@dataclass
class ConsultationResult:
    """The full, combined payload returned by GET /consultations/{id}"""
    business_analysis: BusinessAnalysis = field(default_factory=BusinessAnalysis)
    solution_architecture: SolutionArchitecture = field(default_factory=SolutionArchitecture)
    technology_recommendation: TechnologyRecommendation = field(default_factory=TechnologyRecommendation)
    delivery_plan: DeliveryPlan = field(default_factory=DeliveryPlan)
    judge_output: Optional[JudgeEvaluation] = None
    user_input: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ConsultationResult":
        d = d or {}
        agent_outputs = d.get("agent_outputs") or d
        raw_judge = d.get("judge_output")
        # A `{"raw": ...}` judge payload means the judge degraded to prose.
        if isinstance(raw_judge, dict) and set(raw_judge.keys()) <= {"raw"}:
            raw_judge = None
        return ConsultationResult(
            business_analysis=BusinessAnalysis.from_dict(agent_outputs.get("business_analysis", {})),
            solution_architecture=SolutionArchitecture.from_dict(agent_outputs.get("solution_architecture", {})),
            technology_recommendation=TechnologyRecommendation.from_dict(agent_outputs.get("technology_recommendation", {})),
            delivery_plan=DeliveryPlan.from_dict(agent_outputs.get("delivery_plan", {})),
            judge_output=JudgeEvaluation.from_dict(raw_judge) if raw_judge else None,
            user_input=d.get("user_input", {}),
        )
