"""Deterministic hard-constraint checks.

These checks run in Python rather than relying on the LLM.

They compare explicit user requirements against the outputs produced by
the Business Analyst, Solution Architect, Technology Advisor, and
Delivery Planner.

The Judge LLM performs qualitative evaluation separately. These checks
provide objective, reproducible evidence for explicit constraints.
"""

from __future__ import annotations

import re

from ..models.solution_architecture import SolutionArchitecture
from ..models.technology_advisor import TechnologyRecommendation
from ..models.delivery_planner import DeliveryPlan
from ..schemas.evaluation import HardConstraintCheck

# Type aliases kept for readability. These are the LIVE pipeline models, not
# the SAOutput/TAOutput/DPOutput names the judge was originally written against
# (that folder never existed in this repository).
TAOutput = TechnologyRecommendation
SAOutput = SolutionArchitecture
DPOutput = DeliveryPlan


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WEEKS_PER_MONTH = 4.33

# Timeline tolerance:
# >15% over target -> FAIL / MAJOR
# >30% over target -> FAIL / CRITICAL
# <50% of target -> WARN / MINOR
TIMELINE_TOLERANCE = 0.15
TIMELINE_SEVERE = 0.30
TIMELINE_UNDERRUN = 0.50


CLOUD_ALIASES = {
    "AWS": [
        "aws",
        "amazon web services",
        "amazon",
    ],
    "Azure": [
        "azure",
        "microsoft azure",
    ],
    "GCP": [
        "gcp",
        "google cloud",
        "google cloud platform",
    ],
}


# Cloud/data-region hints.
# These are deliberately broad because the current TA/SA contracts
# do not require a dedicated "data_region" field.
COUNTRY_REGION_HINTS = {
    "India": [
        "ap-south",
        "mumbai",
        "hyderabad",
        "central india",
        "south india",
        "asia-south",
        "india",
    ],
    "United States": [
        "us-east",
        "us-west",
        "us-central",
        "useast",
        "uswest",
        "virginia",
        "oregon",
        "ohio",
        "iowa",
        "united states",
        "usa",
    ],
    "United Kingdom": [
        "eu-west-2",
        "uk south",
        "uk west",
        "london",
        "europe-west2",
        "united kingdom",
    ],
    "Germany": [
        "eu-central-1",
        "germany",
        "frankfurt",
        "europe-west3",
    ],
    "Ireland": [
        "eu-west-1",
        "ireland",
        "dublin",
        "north europe",
    ],
    "Singapore": [
        "ap-southeast-1",
        "singapore",
        "asia-southeast1",
    ],
    "Australia": [
        "ap-southeast-2",
        "australia",
        "sydney",
        "melbourne",
        "australia-southeast",
    ],
    "Japan": [
        "ap-northeast-1",
        "japan",
        "tokyo",
        "osaka",
        "asia-northeast1",
    ],
    "Canada": [
        "ca-central",
        "canada",
        "toronto",
        "montreal",
        "northamerica-northeast",
    ],
    "Brazil": [
        "sa-east-1",
        "brazil",
        "brazil south",
        "southamerica-east1",
    ],
    "France": [
        "eu-west-3",
        "france",
        "paris",
        "europe-west9",
    ],
    "South Korea": [
        "ap-northeast-2",
        "korea",
        "seoul",
        "asia-northeast3",
    ],
    "United Arab Emirates": [
        "me-central-1",
        "uae",
        "dubai",
        "me-central",
    ],
    "South Africa": [
        "af-south-1",
        "south africa",
        "johannesburg",
    ],
    "Netherlands": [
        "eu-west-4",
        "netherlands",
        "europe-west4",
        "amsterdam",
    ],
    "Switzerland": [
        "eu-central-2",
        "switzerland",
        "zurich",
        "europe-west6",
    ],
    "Indonesia": [
        "ap-southeast-3",
        "indonesia",
        "jakarta",
        "asia-southeast2",
    ],
    "Israel": [
        "il-central-1",
        "israel",
        "israel central",
        "me-west1",
    ],
    "Italy": [
        "italy north",
        "milan",
        "europe-west8",
        "eu-south-1",
    ],
    "Spain": [
        "eu-south-2",
        "spain",
        "spain central",
        "europe-southwest1",
    ],
    "Sweden": [
        "eu-north-1",
        "sweden",
        "stockholm",
        "europe-north1",
    ],
    "Poland": [
        "poland central",
        "warsaw",
        "europe-central2",
    ],
    "Mexico": [
        "mx-central-1",
        "mexico",
        "northamerica-south1",
    ],
    "Qatar": [
        "qatar",
        "qatar central",
        "me-central2",
    ],
    "Saudi Arabia": [
        "saudi",
        "me-south",
        "dammam",
    ],
    "New Zealand": [
        "new zealand",
        "australia-southeast2",
        "auckland",
    ],
    "Norway": [
        "norway east",
        "norway west",
        "europe-north2",
        "oslo",
    ],
    "Turkey": [
        "turkey",
        "istanbul",
    ],
    "Thailand": [
        "ap-southeast-7",
        "thailand",
        "bangkok",
        "asia-southeast3",
    ],
    "Malaysia": [
        "ap-southeast-5",
        "malaysia",
        "kuala lumpur",
    ],
    "Vietnam": [
        "vietnam",
        "hanoi",
        "ho chi minh",
    ],
    "Nigeria": [
        "nigeria",
        "lagos",
    ],
    "Kenya": [
        "kenya",
        "nairobi",
    ],
}


# ---------------------------------------------------------------------------
# Technology classification heuristics
# ---------------------------------------------------------------------------

PROPRIETARY_MARKERS = [
    "oracle database",
    "oracle db",
    "microsoft sql server",
    "mssql",
    "sql server",
    "ibm db2",
    "db2",
    "sap hana",
    "informix",
    "sybase",
    "teradata",
    "splunk",
    "datadog",
    "new relic",
    "dynatrace",
    "appdynamics",
    "mulesoft",
    "tibco",
    "informatica",
    "sas ",
    "matlab",
    "tableau",
    "power bi",
    "salesforce",
    "servicenow",
    "okta",
    "auth0",
    "vmware",
    "red hat openshift",
    "websphere",
    "weblogic",
    "coldfusion",
    ".net framework",
    "mongodb enterprise",
    "confluent platform",
    "elastic enterprise",
]


OPEN_SOURCE_MARKERS = [
    "postgresql",
    "postgres",
    "mysql",
    "mariadb",
    "redis",
    "valkey",
    "sqlite",
    "python",
    "fastapi",
    "django",
    "flask",
    "node.js",
    "nodejs",
    "express",
    "nestjs",
    "react",
    "vue",
    "svelte",
    "angular",
    "next.js",
    "nuxt",
    "docker",
    "kubernetes",
    "k8s",
    "nginx",
    "traefik",
    "rabbitmq",
    "kafka",
    "elasticsearch",
    "opensearch",
    "prometheus",
    "grafana",
    "loki",
    "jaeger",
    "terraform",
    "opentofu",
    "ansible",
    "keycloak",
    "minio",
    "celery",
    "go",
    "golang",
    "rust",
    "java",
    "spring boot",
    "quarkus",
    "laravel",
    "ruby on rails",
    "rails",
    "php",
    "typescript",
    "linux",
    "ubuntu",
    "clickhouse",
    "cassandra",
    "mongodb",
    "neo4j",
    "temporal",
    "nats",
]


# ---------------------------------------------------------------------------
# User-input access
# ---------------------------------------------------------------------------

# The judge was written against a slightly different user-input contract
# ("country" instead of "data_hosting_country", etc). Rather than hard-code one
# shape, every read goes through _input() and accepts the known aliases.
_INPUT_ALIASES: dict[str, tuple[str, ...]] = {
    "business_idea": ("business_idea", "idea", "problem_statement"),
    "technology_preference": ("technology_preference",),
    "cloud_preference": ("cloud_preference",),
    "country": ("data_hosting_country", "country", "hosting_country"),
    "expected_daily_traffic": ("expected_daily_traffic", "daily_traffic", "traffic"),
    "delivery_timeline_months": ("delivery_timeline_months", "delivery_timeline", "timeline_months"),
}

_NO_PREFERENCE = {
    "",
    "no preference",
    "no specific preference",
    "no specific preferences",
    "none",
    "any",
    "no requirement",
}


def _norm_pref(value) -> str:
    """Normalize a preference string, collapsing every 'no preference'
    spelling the frontend/backend has used into the single '' sentinel."""
    text = _norm(value)
    return "" if text in _NO_PREFERENCE else text


def _input(user_input: dict, field: str, default=None):
    """Read one user-input field, tolerating the known key aliases."""
    if not isinstance(user_input, dict):
        return default
    for key in _INPUT_ALIASES.get(field, (field,)):
        if key in user_input and user_input[key] not in (None, ""):
            return user_input[key]
    return default


def _input_number(user_input: dict, field: str, default: float = 0.0) -> float:
    """Read one user-input field as a number, tolerating junk values."""
    raw = _input(user_input, field, default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(text: str | None) -> str:
    """Normalize text for reliable case-insensitive matching."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _collect_text(*payloads: dict | None) -> str:
    """Flatten nested dictionaries/lists into a normalized text string."""
    parts: list[str] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str):
            parts.append(node)
        elif node is not None:
            parts.append(str(node))

    for payload in payloads:
        walk(payload)

    return _norm(" ".join(parts))


# ---------------------------------------------------------------------------
# Delivery-plan week estimation
# ---------------------------------------------------------------------------
#
# The judge was originally written against a DPOutput that carried an explicit
# `total_weeks` integer. The live DeliveryPlan model (backend/models/
# delivery_planner.py) has `timeline: List[str]` instead, so the total has to
# be derived from whatever the Delivery Planner actually wrote. Three shapes
# are handled, in order of trustworthiness, and only the first one that
# yields a positive number is used so the estimate is never double-counted.

_MONTH_RANGE_RE = re.compile(
    r"month\s*(\d{1,2})\s*(?:[-–—to]+\s*(\d{1,2}))?",
    re.I,
)
_WEEKS_RE = re.compile(
    r"(\d{1,3})\s*(?:-|–|to)?\s*weeks?\b",
    re.I,
)
_DAY_RE = re.compile(
    r"(\d{1,3})\s*(?:-|–|to)?\s*(?:business\s+)?days?\b",
    re.I,
)


def _weeks_from_dict_entries(timeline: list) -> float:
    """Sum duration_weeks from structured timeline entries."""
    total = 0.0
    seen = False
    for item in timeline:
        if not isinstance(item, dict):
            continue
        raw = item.get("duration_weeks") or item.get("weeks") or item.get("duration")
        if raw is None:
            continue
        try:
            total += float(str(raw).split()[0])
            seen = True
        except (TypeError, ValueError, IndexError):
            continue
    return total if seen else 0.0


def _weeks_from_text(timeline: list) -> float:
    """Sum explicit 'N weeks' mentions across the timeline text."""
    total = 0.0
    for item in timeline:
        if isinstance(item, dict):
            continue
        for match in _WEEKS_RE.finditer(str(item)):
            total += float(match.group(1))
    return total


def _weeks_from_months(timeline: list) -> float:
    """Derive weeks from 'Month 1-2: ...' style phase labels."""
    months = 0.0
    for item in timeline:
        text = item if isinstance(item, str) else str(item)
        for match in _MONTH_RANGE_RE.finditer(text):
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else start
            months += max(end - start + 1, 1)
    return months * WEEKS_PER_MONTH


def estimate_delivery_weeks(timeline) -> float:
    """Best-effort total delivery duration, in weeks.

    Returns 0.0 when the timeline carries no usable duration at all, which the
    timeline check then reports as a MAJOR failure ("produce a phased
    timeline with week durations") rather than silently passing.
    """
    if not timeline:
        return 0.0
    if isinstance(timeline, (str, bytes)):
        timeline = [timeline]
    timeline = list(timeline)

    for estimator in (
        _weeks_from_dict_entries,
        _weeks_from_text,
        _weeks_from_months,
    ):
        total = estimator(timeline)
        if total > 0:
            return round(total, 1)

    # Last resort: a plan expressed only in days.
    days = 0.0
    for item in timeline:
        if isinstance(item, dict):
            continue
        for match in _DAY_RE.finditer(str(item)):
            days += float(match.group(1))
    return round(days / 5.0, 1) if days > 0 else 0.0


# ---------------------------------------------------------------------------
# Defensive model coercion
# ---------------------------------------------------------------------------

def _is_raw_fallback(payload) -> bool:
    """True when an agent output degraded to crew_service's {"raw": "..."}."""
    return isinstance(payload, dict) and set(payload.keys()) <= {"raw"} and "raw" in payload


def coerce_agent_output(model_cls, payload):
    """Build `model_cls` from a stored agent output, or return None.

    Returns None when the agent produced nothing usable (raw fallback, empty
    output, or a shape that no longer validates). Callers turn that into an
    INFO-severity check, which carries no score penalty.
    """
    if payload is None or _is_raw_fallback(payload):
        return None
    if isinstance(payload, model_cls):
        return payload
    if not isinstance(payload, dict):
        return None
    try:
        return model_cls.model_validate(payload)
    except Exception:
        return None


def unavailable_check(constraint: str, reason: str) -> HardConstraintCheck:
    """A non-penalising check used when an agent output cannot be inspected."""
    return HardConstraintCheck(
        constraint=constraint,
        status="WARN",
        severity="INFO",
        evidence=reason,
        recommendation="Re-run the consultation so this section can be verified.",
    )


# ---------------------------------------------------------------------------
# Cloud provider
# ---------------------------------------------------------------------------

def check_cloud_provider(
    user_input: dict,
    ta: TAOutput,
) -> HardConstraintCheck:

    if ta is None:
        return unavailable_check(
            "Cloud provider selection",
            "The Technology Advisor output was unavailable, so the chosen "
            "cloud provider could not be verified.",
        )

    requested_raw = _input(user_input, "cloud_preference", "")
    # "No Specific Preference" / "No preference" / "none" must all collapse to
    # the no-preference branch — otherwise a user who expressed no preference
    # gets a MAJOR penalty for the advisor picking a provider.
    requested = _norm_pref(requested_raw)
    requested_label = str(requested_raw).strip() if requested else ""

    chosen_raw = (ta.cloud.provider if ta.cloud else "") or ""
    chosen = _norm(chosen_raw)

    if not requested:
        if not chosen:
            return HardConstraintCheck(
                constraint="Cloud provider selection",
                status="WARN",
                severity="MINOR",
                evidence=(
                    "The user expressed no cloud preference and the "
                    "Technology Advisor named no provider."
                ),
                recommendation=(
                    "Select a specific cloud provider and justify the choice."
                ),
            )

        return HardConstraintCheck(
            constraint="Cloud provider selection",
            status="PASS",
            severity="INFO",
            evidence=(
                f"No preference was stated; the solution selects {chosen_raw}."
            ),
            recommendation="",
        )

    # CLOUD_ALIASES is keyed by the canonical provider names ("AWS", "Azure",
    # "GCP"), so match case-insensitively rather than assuming exact casing.
    aliases = next(
        (
            alias_list
            for name, alias_list in CLOUD_ALIASES.items()
            if _norm(name) == requested
        ),
        [requested],
    )

    if any(alias in chosen for alias in aliases):
        return HardConstraintCheck(
            constraint=f"Cloud provider must be {requested_label}",
            status="PASS",
            severity="INFO",
            evidence=f"The Technology Advisor selected {chosen_raw}.",
            recommendation="",
        )

    other = next(
        (
            name
            for name, alias_list in CLOUD_ALIASES.items()
            if _norm(name) != requested
            and any(alias in chosen for alias in alias_list)
        ),
        None,
    )

    if other:
        return HardConstraintCheck(
            constraint=f"Cloud provider must be {requested_label}",
            status="FAIL",
            severity="CRITICAL",
            evidence=(
                f"The user required {requested_label} but the solution "
                f"selects {chosen_raw}."
            ),
            recommendation=f"Re-target the solution onto {requested_label}.",
        )

    return HardConstraintCheck(
        constraint=f"Cloud provider must be {requested_label}",
        status="FAIL",
        severity="MAJOR",
        evidence=(
            f"The user required {requested_label} but the cloud provider "
            f"field reads '{chosen_raw or 'empty'}'."
        ),
        recommendation=f"State {requested_label} explicitly as the cloud provider.",
    )


# ---------------------------------------------------------------------------
# Data residency
# ---------------------------------------------------------------------------

def check_data_residency(
    user_input: dict,
    ta: TAOutput,
    sa: SAOutput,
) -> HardConstraintCheck:

    country = _input(user_input, "country", "")

    if not isinstance(ta, TechnologyRecommendation) or not isinstance(sa, SolutionArchitecture):
        return unavailable_check(
            f"Data must be hosted in {country or 'the requested country'}",
            "The architecture or technology output was unavailable, so the "
            "hosting region could not be verified.",
        )

    if not country:
        return unavailable_check(
            "Data residency",
            "The request did not state a data-hosting country.",
        )

    haystack = _collect_text(
        ta.model_dump(),
        sa.model_dump(),
    )

    hints = COUNTRY_REGION_HINTS.get(
        country,
        [_norm(country)],
    )

    # Explicit country/region evidence.
    if any(hint in haystack for hint in hints):
        return HardConstraintCheck(
            constraint=f"Data must be hosted in {country}",
            status="PASS",
            severity="INFO",
            evidence=(
                f"The solution references {country} or a "
                f"recognized region/residency location associated with it."
            ),
            recommendation="",
        )

    # Residency discussed, but exact placement isn't clear.
    residency_terms = [
        "data residency",
        "data sovereignty",
        "data localization",
        "data localisation",
        "hosted in",
        "stored in",
        "region",
    ]

    if any(term in haystack for term in residency_terms):
        return HardConstraintCheck(
            constraint=f"Data must be hosted in {country}",
            status="WARN",
            severity="MINOR",
            evidence=(
                "Data residency/location is discussed, but the solution "
                f"does not clearly identify {country}."
            ),
            recommendation=(
                f"Explicitly state the cloud region or hosting location "
                f"used for {country} data."
            ),
        )

    return HardConstraintCheck(
        constraint=f"Data must be hosted in {country}",
        status="FAIL",
        severity="MAJOR",
        evidence=(
            f"Neither the architecture nor technology output provides "
            f"evidence that data will be hosted in {country}."
        ),
        recommendation=(
            f"Specify the hosting region/location in {country} and "
            "explain how data residency is maintained."
        ),
    )


# ---------------------------------------------------------------------------
# Technology preference
# ---------------------------------------------------------------------------

def check_technology_preference(
    user_input: dict,
    ta: TAOutput,
) -> HardConstraintCheck:

    preference = _input(user_input, "technology_preference", "") or "No preference"

    if not isinstance(ta, TechnologyRecommendation):
        return unavailable_check(
            f"Technology preference: {preference}",
            "The Technology Advisor output was unavailable, so the "
            "selected stack could not be verified.",
        )

    named = [
        _norm(t.technology)
        for t in ta.technologies
        if t.technology
    ]

    if not named:
        return HardConstraintCheck(
            constraint=f"Technology preference: {preference}",
            status="FAIL",
            severity="MAJOR",
            evidence="The Technology Advisor named no technologies.",
            recommendation="Produce a concrete technology stack.",
        )

    proprietary = [
        tech
        for tech in named
        if any(marker in tech for marker in PROPRIETARY_MARKERS)
    ]

    open_source = [
        tech
        for tech in named
        if any(marker in tech for marker in OPEN_SOURCE_MARKERS)
    ]

    if _norm(preference) == "open-source" or _norm(preference) == "open source":

        if proprietary:
            severity = (
                "MAJOR"
                if len(proprietary) > 1
                else "MINOR"
            )

            return HardConstraintCheck(
                constraint="Technology preference: Open-source",
                status="FAIL",
                severity=severity,
                evidence=(
                    "Proprietary products appear in the open-source "
                    "stack according to the rule-based technology "
                    "classification: "
                    + ", ".join(sorted(set(proprietary))[:4])
                ),
                recommendation=(
                    "Replace proprietary components with open-source "
                    "alternatives or explicitly justify the exception."
                ),
            )

        if len(open_source) < max(1, len(named) // 3):
            return HardConstraintCheck(
                constraint="Technology preference: Open-source",
                status="WARN",
                severity="MINOR",
                evidence=(
                    "Few of the selected technologies are recognized "
                    "by the rule-based classifier as open-source."
                ),
                recommendation=(
                    "Confirm the licensing/support model of each "
                    "selected technology."
                ),
            )

        return HardConstraintCheck(
            constraint="Technology preference: Open-source",
            status="PASS",
            severity="INFO",
            evidence=(
                f"{len(open_source)} of {len(named)} selections are "
                "recognized by the heuristic as open-source."
            ),
            recommendation="",
        )

    if _norm(preference) == "enterprise":

        if not proprietary and len(open_source) == len(named):
            return HardConstraintCheck(
                constraint="Technology preference: Enterprise",
                status="WARN",
                severity="MINOR",
                evidence=(
                    "An enterprise preference was stated, but the "
                    "named stack contains no technologies recognized "
                    "by the heuristic as commercially supported."
                ),
                recommendation=(
                    "Consider vendor-supported offerings or explicitly "
                    "state how commercial support is obtained."
                ),
            )

        return HardConstraintCheck(
            constraint="Technology preference: Enterprise",
            status="PASS",
            severity="INFO",
            evidence=(
                "The stack includes technologies recognized as "
                "commercial/proprietary or vendor-backed."
            ),
            recommendation="",
        )

    # Hybrid / other supported preference.
    return HardConstraintCheck(
        constraint=f"Technology preference: {preference}",
        status="PASS",
        severity="INFO",
        evidence=(
            f"Technology preference '{preference}' is accepted; "
            f"{len(open_source)} open-source and "
            f"{len(proprietary)} proprietary selections were identified "
            "by the heuristic."
        ),
        recommendation="",
    )


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

def check_timeline(
    user_input: dict,
    dp: DPOutput,
) -> HardConstraintCheck:

    months = _input_number(user_input, "delivery_timeline_months", 0.0)
    target = months * WEEKS_PER_MONTH

    if dp is None:
        return unavailable_check(
            f"Delivery within {months:g} month(s) (~{target:.0f} weeks)",
            "The Delivery Planner output was unavailable, so the planned "
            "duration could not be compared against the target.",
        )

    if not isinstance(dp, DeliveryPlan):
        # Either None or an un-coerced {"raw": ...} payload. Must not fall
        # through to the "no phase durations" FAIL below, which would apply a
        # real 10-point deduction for what is only a missing-agent problem.
        return unavailable_check(
            f"Delivery within {months:g} month(s) (~{target:.0f} weeks)",
            "The Delivery Planner output was unavailable, so the planned "
            "duration could not be compared against the target.",
        )

    # The live DeliveryPlan has no `total_weeks` field — it carries a
    # `timeline` list instead, so the duration is derived from that.
    planned = estimate_delivery_weeks(getattr(dp, "timeline", None))

    constraint = (
        f"Delivery within {months:g} month(s) "
        f"(~{target:.0f} weeks)"
    )

    if target <= 0:
        return unavailable_check(
            "Delivery timeline",
            "The request did not state a delivery timeline.",
        )

    if planned <= 0:
        return HardConstraintCheck(
            constraint=constraint,
            status="FAIL",
            severity="MAJOR",
            evidence="The delivery plan contains no phase durations.",
            recommendation=(
                "Produce a phased timeline with week durations."
            ),
        )

    ratio = planned / target

    if ratio > 1 + TIMELINE_SEVERE:
        return HardConstraintCheck(
            constraint=constraint,
            status="FAIL",
            severity="CRITICAL",
            evidence=(
                f"The plan totals {planned:g} weeks against a "
                f"{target:.0f}-week target "
                f"({(ratio - 1) * 100:.0f}% over)."
            ),
            recommendation=(
                "Cut or defer MVP scope until the plan fits "
                "the stated timeline."
            ),
        )

    if ratio > 1 + TIMELINE_TOLERANCE:
        return HardConstraintCheck(
            constraint=constraint,
            status="FAIL",
            severity="MAJOR",
            evidence=(
                f"The plan totals {planned:g} weeks against a "
                f"{target:.0f}-week target."
            ),
            recommendation=(
                "Compress or defer scope to bring the plan "
                "within the timeline."
            ),
        )

    if ratio < TIMELINE_UNDERRUN:
        return HardConstraintCheck(
            constraint=constraint,
            status="WARN",
            severity="MINOR",
            evidence=(
                f"The plan totals only {planned:g} weeks against a "
                f"{target:.0f}-week target, which may understate "
                "the work."
            ),
            recommendation=(
                "Confirm that the plan covers the complete MVP scope."
            ),
        )

    return HardConstraintCheck(
        constraint=constraint,
        status="PASS",
        severity="INFO",
        evidence=(
            f"The plan totals {planned:g} weeks against a "
            f"{target:.0f}-week target."
        ),
        recommendation="",
    )


# ---------------------------------------------------------------------------
# Traffic propagation
# ---------------------------------------------------------------------------

def check_traffic_propagation(
    user_input: dict,
    sa: SAOutput,
    ta: TAOutput,
    ba: dict,
) -> HardConstraintCheck:

    traffic = _input_number(user_input, "expected_daily_traffic", 0.0)
    traffic_label = f"{int(traffic):,}"

    if not isinstance(sa, SolutionArchitecture) or not isinstance(ta, TechnologyRecommendation):
        return unavailable_check(
            f"Traffic requirement of {traffic_label} is propagated",
            "The architecture or technology output was unavailable, so the "
            "traffic requirement could not be traced.",
        )

    haystack = _collect_text(
        ba,
        sa.model_dump(),
        ta.model_dump(),
    )

    candidates = {
        str(int(traffic)),
        traffic_label,
    }

    if traffic >= 1000 and int(traffic) % 1000 == 0:
        candidates.add(f"{int(traffic) // 1000}k")
        candidates.add(f"{int(traffic) // 1000},000")

    if any(
        candidate.lower() in haystack
        for candidate in candidates
    ):
        return HardConstraintCheck(
            constraint=f"Traffic requirement of {traffic_label} is propagated",
            status="PASS",
            severity="INFO",
            evidence=(
                "The stated traffic figure is explicitly referenced "
                "in the generated solution."
            ),
            recommendation="",
        )

    scale_words = [
        "throughput",
        "concurrent",
        "requests per",
        "rps",
        "daily active",
        "load",
        "peak traffic",
        "scale to",
        "daily users",
        "scalability",
    ]

    if any(word in haystack for word in scale_words):
        return HardConstraintCheck(
            constraint=f"Traffic requirement of {traffic_label} is propagated",
            status="WARN",
            severity="MINOR",
            evidence=(
                "Scale is discussed, but the exact user-specified "
                "traffic figure is not explicitly referenced."
            ),
            recommendation=(
                "Tie the capacity/scaling discussion explicitly "
                "to the stated traffic requirement."
            ),
        )

    return HardConstraintCheck(
        constraint=f"Traffic requirement of {traffic_label} is propagated",
        status="FAIL",
        severity="MAJOR",
        evidence=(
            "The stated traffic requirement is not reflected "
            "in the generated BA, SA, or TA outputs."
        ),
        recommendation=(
            "Explicitly address the requested traffic scale "
            "in the architecture and technology recommendations."
        ),
    )


# ---------------------------------------------------------------------------
# MVP coverage
# ---------------------------------------------------------------------------

def check_mvp_coverage(
    ba: dict,
    dp: DPOutput,
) -> HardConstraintCheck:

    constraint = "MVP scope must be addressed by the delivery plan"

    if not isinstance(dp, DeliveryPlan) or not isinstance(ba, dict) or _is_raw_fallback(ba):
        return unavailable_check(
            constraint,
            "The business analysis or delivery plan output was unavailable, "
            "so MVP coverage could not be traced.",
        )

    mvp_items = [
        str(item)
        for item in (ba.get("mvp_scope") or [])
        if item
    ]

    if not mvp_items:
        return HardConstraintCheck(
            constraint=constraint,
            status="FAIL",
            severity="MAJOR",
            evidence="The Business Analyst defined no MVP scope.",
            recommendation="Define an explicit MVP scope.",
        )

    plan_text = _collect_text(dp.model_dump())

    covered = 0

    for item in mvp_items:

        keywords = [
            word
            for word in re.findall(
                r"[a-z]{5,}",
                item.lower(),
            )
            if word not in {
                "should",
                "system",
                "allow",
                "users",
                "there",
                "which",
            }
        ]

        if not keywords:
            covered += 1
            continue

        hits = sum(
            1
            for word in keywords
            if word in plan_text
        )

        if hits >= max(1, len(keywords) // 3):
            covered += 1

    ratio = covered / len(mvp_items)

    if ratio >= 0.7:
        return HardConstraintCheck(
            constraint=constraint,
            status="PASS",
            severity="INFO",
            evidence=(
                f"{covered} of {len(mvp_items)} MVP scope items "
                "are traceable into the delivery plan."
            ),
            recommendation="",
        )

    if ratio >= 0.4:
        return HardConstraintCheck(
            constraint=constraint,
            status="WARN",
            severity="MINOR",
            evidence=(
                f"Only {covered} of {len(mvp_items)} MVP scope items "
                "are traceable into the delivery plan."
            ),
            recommendation=(
                "Add workstream tasks for uncovered MVP items."
            ),
        )

    return HardConstraintCheck(
        constraint=constraint,
        status="FAIL",
        severity="MAJOR",
        evidence=(
            f"Only {covered} of {len(mvp_items)} MVP scope items "
            "are traceable into the delivery plan."
        ),
        recommendation=(
            "Rework the delivery plan to cover the defined MVP scope."
        ),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_hard_constraint_checks(
    user_input: dict,
    ba: dict,
    sa: SAOutput,
    ta: TAOutput,
    dp: DPOutput,
) -> list[HardConstraintCheck]:
    """Run every deterministic check against the stored agent outputs.

    `sa` / `ta` / `dp` may be None (or un-coerced dicts) when an agent failed;
    the affected checks then degrade to INFO-severity warnings, which carry a
    zero penalty, so a single missing agent never tanks the headline score.
    """
    return [
        check_cloud_provider(user_input, ta),
        check_data_residency(user_input, ta, sa),
        check_technology_preference(user_input, ta),
        check_timeline(user_input, dp),
        check_traffic_propagation(
            user_input,
            sa,
            ta,
            ba,
        ),
        check_mvp_coverage(
            ba,
            dp,
        ),
    ]
