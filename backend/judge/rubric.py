"""The Judge rubric: criteria, weights, quality bands and severity penalties.

All of it is overridable per user through Settings, but the defaults here are
the documented rubric and the weights must always total 100.
"""
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_WEIGHTS: dict[str, float] = {
    "Requirement Coverage": 20,
    "Architecture Feasibility": 15,
    "Technology Alignment": 15,
    "Scalability": 10,
    "Security": 10,
    "Timeline Feasibility": 10,
    "Constraint Compliance": 10,
    "MVP Focus": 5,
    "Avoid Over-engineering": 5,
}

CRITERION_ORDER: list[str] = list(DEFAULT_WEIGHTS)


@dataclass(frozen=True)
class QualityBand:
    name: str
    minimum: float
    description: str


# Ordered high to low; the first band whose minimum is met wins.
DEFAULT_BANDS: list[QualityBand] = [
    QualityBand("Excellent", 90, "Excellent satisfaction with only minor issues."),
    QualityBand("Strong", 75, "Strong solution with some meaningful improvements possible."),
    QualityBand("Usable", 60, "Usable but has notable weaknesses."),
    QualityBand("Weak", 40, "Major weaknesses or inconsistencies."),
    QualityBand(
        "Critical", 0,
        "Severely incomplete, infeasible, or violates major constraints.",
    ),
]

# Points deducted from the weighted total per failed hard constraint, by
# severity. A critical violation must be visible in the headline number rather
# than averaged away behind nine criteria.
DEFAULT_SEVERITY_PENALTIES: dict[str, float] = {
    "CRITICAL": 20.0,
    "MAJOR": 10.0,
    "MINOR": 3.0,
    "INFO": 0.0,
}

# Cap on total constraint penalty so a solution never scores below the floor
# purely through stacked deductions.
MAX_TOTAL_PENALTY: float = 45.0

SEVERITY_ORDER = ["CRITICAL", "MAJOR", "MINOR", "INFO"]


class RubricError(ValueError):
    pass


def normalise_weights(weights: dict[str, float] | None) -> dict[str, float]:
    """Validate a weight set. Missing criteria inherit the default weight;
    unknown criteria are rejected; the total must be 100."""
    if not weights:
        return dict(DEFAULT_WEIGHTS)

    unknown = set(weights) - set(DEFAULT_WEIGHTS)
    if unknown:
        raise RubricError(f"Unknown judge criteria: {', '.join(sorted(unknown))}")

    merged = dict(DEFAULT_WEIGHTS)
    for name, value in weights.items():
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            raise RubricError(f"Weight for '{name}' must be a number.")
        if numeric < 0:
            raise RubricError(f"Weight for '{name}' cannot be negative.")
        merged[name] = numeric

    total = round(sum(merged.values()), 4)
    if abs(total - 100.0) > 0.01:
        raise RubricError(f"Judge rubric weights must total 100 (currently {total:g}).")
    return merged


def normalise_penalties(penalties: dict[str, float] | None) -> dict[str, float]:
    if not penalties:
        return dict(DEFAULT_SEVERITY_PENALTIES)

    merged = dict(DEFAULT_SEVERITY_PENALTIES)
    for key, value in penalties.items():
        severity = str(key).upper()
        if severity not in DEFAULT_SEVERITY_PENALTIES:
            raise RubricError(
                f"Unknown severity '{key}'. Use one of: "
                f"{', '.join(SEVERITY_ORDER)}."
            )
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            raise RubricError(f"Penalty for '{severity}' must be a number.")
        if not 0 <= numeric <= 100:
            raise RubricError(f"Penalty for '{severity}' must be between 0 and 100.")
        merged[severity] = numeric
    return merged


def band_for_score(
    score: float, bands: list[QualityBand] | None = None
) -> QualityBand:
    for band in bands or DEFAULT_BANDS:
        if score >= band.minimum:
            return band
    return (bands or DEFAULT_BANDS)[-1]


def bands_as_dicts(bands: list[QualityBand] | None = None) -> list[dict]:
    return [
        {"name": b.name, "minimum": b.minimum, "description": b.description}
        for b in (bands or DEFAULT_BANDS)
    ]


def bands_from_config(raw: list[dict] | None) -> list[QualityBand]:
    if not raw:
        return list(DEFAULT_BANDS)
    bands = [
        QualityBand(
            name=str(item.get("name", "Band")),
            minimum=float(item.get("minimum", 0)),
            description=str(item.get("description", "")),
        )
        for item in raw
    ]
    return sorted(bands, key=lambda b: b.minimum, reverse=True)
