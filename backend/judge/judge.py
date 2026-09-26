"""The Solution Judge — pipeline step 5 (after the 4 agents, before blueprint).

The Judge is deliberately split in two halves:

1. **Qualitative** — `backend/agents/judge.py` runs the Judge LLM through
   CrewAI and returns a `JudgeEvaluation`: one score + evidence bundle per
   rubric criterion, plus strengths/weaknesses/summary. It is explicitly NOT
   allowed to produce an overall score.

2. **Deterministic** — this module. It runs the Python hard-constraint checks
   and computes the weighted total, the penalties and the quality band, then
   merges the LLM narrative onto that number.

Keeping the headline number in Python means the same criterion scores always
produce the same result, so a score can be audited and re-derived from the
stored inputs without re-running the model.

The Judge never generates or edits the solution itself — it only scores what
the other four agents produced.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from backend.models.solution_architecture import SolutionArchitecture
from backend.models.technology_advisor import TechnologyRecommendation
from backend.models.delivery_planner import DeliveryPlan
from backend.schemas.evaluation import (
    CriterionEvaluation,
    HardConstraintCheck,
    JudgeEvaluation,
)
from backend.judge.constraints import (
    coerce_agent_output,
    run_hard_constraint_checks,
)
from backend.judge.rubric import (
    CRITERION_ORDER,
    DEFAULT_WEIGHTS,
    RubricError,
    normalise_weights,
)
from backend.judge.scoring import compute_overall

logger = logging.getLogger(__name__)

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.S)


# ---------------------------------------------------------------------------
# Reading the Judge LLM's output
# ---------------------------------------------------------------------------

def _coerce_criteria(raw: Any) -> list[CriterionEvaluation]:
    """Best-effort conversion of a criteria payload into CriterionEvaluation.

    Accepts a list of dicts, a list of already-built models, or None. Bad
    entries are skipped rather than raised: `scoring.score_criteria` already
    treats a missing criterion as a zero, and the judge must never crash the
    consultation because one LLM field was malformed.
    """
    if raw is None:
        return []
    if isinstance(raw, dict):
        raw = raw.get("criteria") or []
    if not isinstance(raw, list):
        return []

    out: list[CriterionEvaluation] = []
    for item in raw:
        if isinstance(item, CriterionEvaluation):
            out.append(item)
        elif isinstance(item, dict):
            try:
                out.append(CriterionEvaluation.model_validate(item))
            except Exception:
                continue
    return out


def _as_list(value: Any) -> list[str]:
    """Coerce an LLM narrative field into a list of non-empty strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value)]


def evaluation_from_task_output(task_output: Any) -> Optional[JudgeEvaluation]:
    """Pull a JudgeEvaluation out of a CrewAI TaskOutput.

    Tries, in order:
      1. `task_output.pydantic` (the normal path — `output_pydantic` validated it)
      2. `task_output.json_dict`
      3. the first {...} block inside `task_output.raw` (model returned prose)

    Returns None when nothing usable came back, so the caller can still emit a
    judge_output built purely from the deterministic checks.
    """
    if task_output is None:
        return None

    pydantic_out = getattr(task_output, "pydantic", None)
    if isinstance(pydantic_out, JudgeEvaluation):
        return pydantic_out
    if isinstance(pydantic_out, dict):
        return _build_evaluation(pydantic_out)

    json_dict = getattr(task_output, "json_dict", None)
    if isinstance(json_dict, dict) and json_dict:
        return _build_evaluation(json_dict)

    raw = getattr(task_output, "raw", None) or str(task_output or "")
    match = _JSON_BLOCK_RE.search(raw)
    if match:
        try:
            return _build_evaluation(json.loads(match.group(0)))
        except (ValueError, TypeError):
            return None
    return None


def _build_evaluation(payload: dict) -> Optional[JudgeEvaluation]:
    """Validate a plain dict into a JudgeEvaluation, or None if unusable."""
    if not isinstance(payload, dict) or not payload:
        return None
    try:
        return JudgeEvaluation.model_validate(payload)
    except Exception:
        # Retry with just the criteria, so a bad narrative field does not cost
        # us the whole qualitative evaluation.
        criteria = _coerce_criteria(payload.get("criteria"))
        if not criteria:
            return None
        return JudgeEvaluation(criteria=criteria)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_judge_output(
    user_input: dict,
    agent_outputs: dict,
    evaluation: Any = None,
    *,
    weights: Optional[dict[str, float]] = None,
) -> dict:
    """Produce the single `judge_output` dict for a consultation.

    Parameters
    ----------
    user_input : the 6 fields submitted by the user (see models/user_input.py)
    agent_outputs : the 4 stored agent outputs, exactly as
                    `crew_service._output_to_dict` saved them
    evaluation : a JudgeEvaluation, a TaskOutput, or a raw dict from the
                 Judge LLM. None is tolerated.
    weights : optional rubric-weight overrides; must total 100.

    Returns
    -------
    A JSON-safe dict containing the criteria table, the hard-constraint
    checks, the headline score/band and the Judge's narrative — the exact
    shape `backend/utils/blueprint_generator.py::render_judge` renders and
    `Consultation.judge_output` stores.
    """
    if evaluation is not None and not isinstance(evaluation, JudgeEvaluation):
        extracted = evaluation_from_task_output(evaluation)
        if extracted is not None:
            evaluation = extracted
        elif isinstance(evaluation, dict):
            evaluation = _build_evaluation(evaluation)
        else:
            evaluation = None

    agent_outputs = agent_outputs or {}
    ba = agent_outputs.get("business_analysis")
    sa_raw = agent_outputs.get("solution_architecture")
    ta_raw = agent_outputs.get("technology_recommendation")
    dp_raw = agent_outputs.get("delivery_plan")

    sa = coerce_agent_output(SolutionArchitecture, sa_raw)
    ta = coerce_agent_output(TechnologyRecommendation, ta_raw)
    dp = coerce_agent_output(DeliveryPlan, dp_raw)

    ba_dict = ba if isinstance(ba, dict) else {}

    checks: list[HardConstraintCheck] = run_hard_constraint_checks(
        user_input or {},
        ba_dict,
        sa,
        ta,
        dp,
    )

    # A bad weight override must not take the whole consultation down — fall
    # back to the documented defaults and say so in the output.
    try:
        resolved_weights = normalise_weights(weights)
        weight_note = ""
    except RubricError as exc:
        logger.warning("Falling back to default judge weights: %s", exc)
        resolved_weights = dict(DEFAULT_WEIGHTS)
        weight_note = (
            f" Supplied rubric weights were rejected ({exc}); the default "
            "rubric was used instead."
        )

    criteria = list(evaluation.criteria) if isinstance(evaluation, JudgeEvaluation) else []

    scored = compute_overall(criteria, checks, weights=resolved_weights)
    if weight_note:
        scored["scoring_explanation"] = scored["scoring_explanation"] + weight_note

    missing = [name for name in CRITERION_ORDER if name not in {c.name.strip() for c in criteria}]

    judge_output: dict[str, Any] = {
        **scored,
        "judge_status": "complete" if not missing else "partial",
        "criteria_missing": missing,
        "rubric_criteria": list(CRITERION_ORDER),
        "hard_constraint_checks": [c.model_dump(mode="json") for c in checks],
        "strengths": _as_list(getattr(evaluation, "strengths", None)),
        "weaknesses": _as_list(getattr(evaluation, "weaknesses", None)),
        "critical_issues": _as_list(getattr(evaluation, "critical_issues", None)),
        "recommended_improvements": _as_list(
            getattr(evaluation, "recommended_improvements", None)
        ),
        "cross_agent_consistency": (
            getattr(evaluation, "cross_agent_consistency", "") or ""
        ),
        "judge_summary": getattr(evaluation, "judge_summary", "") or "",
        "llm_evaluation_available": bool(criteria),
    }

    if not criteria:
        judge_output["judge_summary"] = (
            "The Judge's language model did not return a usable evaluation, "
            "so only the deterministic hard-constraint checks contributed to "
            "this score."
        )

    return judge_output
