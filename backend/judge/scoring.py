"""Deterministic scoring.

The LLM scores individual criteria and supplies evidence. This module — not
the model — computes the weighted total, applies hard-constraint penalties and
assigns the quality band. That keeps the headline number reproducible and
auditable: the same criterion scores always yield the same result.

Formula
-------
    weighted_score(c) = criterion_score(c) * weight(c) / 100
    raw_weighted_total = sum(weighted_score(c) for c in criteria)
    constraint_penalty = min(MAX_TOTAL_PENALTY,
                             sum(penalty[severity] for each FAILED check))
    overall_score = clamp(raw_weighted_total - constraint_penalty, 0, 100)

WARN checks carry half the penalty of a FAIL at the same severity; PASS checks
carry none.
"""
from __future__ import annotations

from ..schemas.evaluation import (
    CriterionEvaluation,
    HardConstraintCheck,
    ScoredCriterion,
)
from .rubric import (
    CRITERION_ORDER,
    MAX_TOTAL_PENALTY,
    QualityBand,
    band_for_score,
    normalise_penalties,
    normalise_weights,
)

WARN_PENALTY_FACTOR = 0.5


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def score_criteria(
    evaluations: list[CriterionEvaluation],
    weights: dict[str, float] | None = None,
) -> tuple[list[ScoredCriterion], float]:
    """Apply weights to the LLM's criterion scores.

    A criterion the model failed to return is scored 0 rather than dropped —
    otherwise omitting a criterion would silently raise the average.
    """
    resolved = normalise_weights(weights)
    by_name = {e.name.strip(): e for e in evaluations if e.name}

    scored: list[ScoredCriterion] = []
    for name in CRITERION_ORDER:
        weight = resolved.get(name, 0.0)
        evaluation = by_name.get(name)

        if evaluation is None:
            scored.append(
                ScoredCriterion(
                    name=name,
                    weight=weight,
                    score=0,
                    weighted_score=0.0,
                    assessment=(
                        "The judging model did not return an evaluation for this "
                        "criterion, so it scores zero."
                    ),
                    issues=["Criterion missing from judge output."],
                )
            )
            continue

        criterion_score = int(clamp(float(evaluation.score or 0)))
        scored.append(
            ScoredCriterion(
                name=name,
                weight=weight,
                score=criterion_score,
                weighted_score=round(criterion_score * weight / 100.0, 2),
                assessment=evaluation.assessment,
                evidence=evaluation.evidence,
                issues=evaluation.issues,
                improvements=evaluation.improvements,
            )
        )

    raw_total = round(sum(c.weighted_score for c in scored), 2)
    return scored, raw_total


def constraint_penalty(
    checks: list[HardConstraintCheck],
    penalties: dict[str, float] | None = None,
) -> tuple[float, list[str]]:
    """Total deduction from failed/warned hard constraints, plus a
    human-readable breakdown of how it was derived."""
    table = normalise_penalties(penalties)
    total = 0.0
    breakdown: list[str] = []

    for check in checks:
        status = (check.status or "").upper()
        severity = (check.severity or "INFO").upper()
        base = table.get(severity, 0.0)
        if base <= 0:
            continue

        if status == "FAIL":
            amount = base
        elif status == "WARN":
            amount = base * WARN_PENALTY_FACTOR
        else:
            continue

        total += amount
        breakdown.append(
            f"{check.constraint}: {status} ({severity}) -{amount:g}"
        )

    capped = min(total, MAX_TOTAL_PENALTY)
    if capped < total:
        breakdown.append(
            f"Total penalty capped at {MAX_TOTAL_PENALTY:g} (uncapped {total:g})."
        )
    return round(capped, 2), breakdown


def compute_overall(
    evaluations: list[CriterionEvaluation],
    checks: list[HardConstraintCheck],
    *,
    weights: dict[str, float] | None = None,
    penalties: dict[str, float] | None = None,
    bands: list[QualityBand] | None = None,
) -> dict:
    scored, raw_total = score_criteria(evaluations, weights)
    penalty, breakdown = constraint_penalty(checks, penalties)
    overall = round(clamp(raw_total - penalty), 1)
    band = band_for_score(overall, bands)

    explanation_lines = [
        "Each criterion is scored 0-100 by the judging model and multiplied by "
        "its rubric weight; the application sums the results.",
        f"Weighted criterion total: {raw_total:g}/100.",
    ]
    if breakdown:
        explanation_lines.append(
            "Hard-constraint deductions: " + "; ".join(breakdown) + "."
        )
    else:
        explanation_lines.append("No hard-constraint deductions were applied.")
    explanation_lines.append(
        f"Final score: {raw_total:g} - {penalty:g} = {overall:g} "
        f"({band.name} — {band.description})"
    )

    failed = [c.constraint for c in checks if (c.status or "").upper() == "FAIL"]
    warned = [c.constraint for c in checks if (c.status or "").upper() == "WARN"]

    return {
        # Pydantic models are dumped here so the result is a plain dict that
        # can go straight into MongoDB and into the SSE payload.
        "criteria": [c.model_dump(mode="json") for c in scored],
        "raw_weighted_score": raw_total,
        "constraint_penalty": penalty,
        "overall_score": overall,
        "quality_band": band.name,
        "quality_band_description": band.description,
        "scoring_explanation": " ".join(explanation_lines),
        "rubric_weights": normalise_weights(weights),
        "failed_constraints": failed,
        "warned_constraints": warned,
    }
