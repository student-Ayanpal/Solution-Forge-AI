"""
Offline Judge test — no LLM, no MongoDB, no network.

The Judge is the one part of the pipeline that is almost entirely
deterministic, so it is the one part that can be tested for real without
spending tokens or waiting four minutes for a crew run.

What is covered:
    1. rubric weight validation
    2. the weighted-score + penalty maths
    3. timeline week estimation across every timeline shape the Delivery
       Planner can produce
    4. the hard-constraint checks against realistic agent outputs
    5. graceful degradation when an agent produced nothing usable
    6. build_judge_output() end to end, incl. the raw-JSON fallback
    7. the blueprint HTML actually renders the Judge section

Run from the repo root:
    python -m backend.tests.test_judge_unit
"""

import json

from backend.judge.constraints import (
    check_cloud_provider,
    check_data_residency,
    check_mvp_coverage,
    check_timeline,
    check_technology_preference,
    check_traffic_propagation,
    coerce_agent_output,
    estimate_delivery_weeks,
)
from backend.judge.judge import build_judge_output, evaluation_from_task_output
from backend.judge.rubric import (
    CRITERION_ORDER,
    DEFAULT_WEIGHTS,
    RubricError,
    band_for_score,
    normalise_weights,
)
from backend.judge.scoring import compute_overall
from backend.models.delivery_planner import DeliveryPlan
from backend.models.solution_architecture import SolutionArchitecture
from backend.models.technology_advisor import TechnologyRecommendation
from backend.schemas.evaluation import (
    CriterionEvaluation,
    HardConstraintCheck,
    JudgeEvaluation,
)

results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    results.append((name, bool(condition), detail))
    print(f"[{'PASS' if condition else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    return bool(condition)


def expect_raises(name: str, fn, exc_type) -> None:
    try:
        fn()
    except exc_type:
        check(name, True, f"raised {exc_type.__name__} as expected")
    except Exception as other:  # noqa: BLE001
        check(name, False, f"raised {type(other).__name__} instead of {exc_type.__name__}")
    else:
        check(name, False, "did not raise")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

USER_INPUT = {
    "business_idea": "An e-commerce marketplace for handmade crafts and local artisans.",
    "technology_preference": "Open-source",
    "cloud_preference": "AWS",
    "expected_daily_traffic": 2000,
    "delivery_timeline_months": 6,
    "data_hosting_country": "India",
}

BA = {
    "problem_statement": "Artisans cannot sell online.",
    "users": ["Buyers", "Artisans"],
    "stakeholders": ["Artisan guild"],
    "functional_requirements": ["Product listing", "Checkout", "Order tracking"],
    "non_functional_requirements": ["Handle 2,000 daily users"],
    "mvp_scope": [
        "Product listing and search for handmade crafts",
        "Shopping cart and checkout",
        "Order tracking for buyers",
    ],
    "future_scope": ["Mobile apps", "Auction module"],
    "constraints": ["AWS", "India data residency"],
    "assumptions": ["Payments via third party"],
    "risks": ["Payment gateway availability"],
    "open_questions": ["Who handles refunds?"],
}

SA = {
    "architecture_style": "Three-tier modular monolith",
    "components": [
        {"id": "web", "name": "Web Client", "responsibility": "Storefront UI"},
        {"id": "api", "name": "API", "responsibility": "Business logic"},
        {"id": "db", "name": "Postgres", "responsibility": "Primary store"},
    ],
    "connections": [
        {"source": "web", "target": "api", "label": "HTTPS"},
        {"source": "api", "target": "db", "label": "SQL"},
    ],
    "database": {"type": "PostgreSQL", "purpose": "Transactional store"},
    "cache": {"required": True, "purpose": "Product listing cache"},
    "data_flow": ["Client to API", "API to Postgres"],
    "security": ["TLS everywhere", "OAuth login"],
    "scalability": ["Horizontal scaling of the API tier", "Read replicas"],
    "mvp_architecture": ["Single deployable service"],
    "future_evolution": ["Split into microservices"],
    "architecture_rationale": "A modular monolith fits a 2,000 DAU MVP.",
    "architecture_risks": ["Single point of failure"],
}

TA = {
    "technologies": [
        {"category": "Backend", "technology": "Django", "reason": "Batteries included"},
        {"category": "Database", "technology": "PostgreSQL", "reason": "Relational fit"},
        {"category": "Cache", "technology": "Redis", "reason": "Listing cache"},
    ],
    "cloud": {"provider": "AWS", "services": ["EC2", "RDS", "ElastiCache", "S3"]},
    "technology_strategy": "Lean open-source stack on AWS.",
    "alternatives": [],
    "trade_offs": [],
    "security_considerations": ["IAM roles", "Secrets Manager"],
    "scalability_considerations": ["Auto Scaling group"],
    "technology_risks": ["Managed service lock-in"],
    "lock_in_considerations": ["Keep S3 behind an abstraction"],
}

DP = {
    "delivery_overview": "Six-month MVP in four phases.",
    "mvp_scope": ["Listing", "Checkout", "Order tracking"],
    "future_scope": ["Mobile apps"],
    "workstreams": [
        "Discovery and product listing",
        "Cart and checkout",
        "Order tracking",
    ],
    "timeline": [
        "Month 1: Discovery and product listing setup",
        "Month 2-3: Cart and checkout build",
        "Month 4-5: Order tracking integration",
        "Month 6: Launch and hardening",
    ],
    "team": ["Backend Engineer", "Frontend Engineer", "QA Engineer"],
    "dependencies": ["Payment gateway contract"],
    "risks": ["Payment gateway delay"],
    "testing_strategy": ["Unit and integration tests"],
    "deployment_plan": ["CI/CD to AWS"],
    "maintenance_plan": ["Weekly triage"],
    "assumptions": ["Third-party payments"],
    "open_questions": ["Refund policy"],
    "effort_assessment": ["~180 person-days"],
    "complexity_assessment": ["Overall: Medium"],
}


def _criteria(**overrides) -> list[CriterionEvaluation]:
    """One CriterionEvaluation per rubric criterion, with a default score."""
    defaults = {
        "Requirement Coverage": 80,
        "Architecture Feasibility": 78,
        "Technology Alignment": 90,
        "Scalability": 70,
        "Security": 64,
        "Timeline Feasibility": 58,
        "Constraint Compliance": 88,
        "MVP Focus": 80,
        "Avoid Over-engineering": 95,
    }
    defaults.update(overrides)
    return [
        CriterionEvaluation(
            name=name,
            score=score,
            assessment=f"{name} assessed.",
            evidence=["Evidence taken from the agent outputs."],
        )
        for name, score in defaults.items()
    ]


# ---------------------------------------------------------------------------
# 1. Rubric
# ---------------------------------------------------------------------------

def test_rubric() -> None:
    print("\n--- 1. Rubric ---")
    check("Default weights total 100", sum(DEFAULT_WEIGHTS.values()) == 100,
          f"= {sum(DEFAULT_WEIGHTS.values())}")
    check("Nine criteria defined", len(CRITERION_ORDER) == 9, f"= {len(CRITERION_ORDER)}")
    check("normalise_weights(None) -> defaults",
          normalise_weights(None) == DEFAULT_WEIGHTS)
    expect_raises("Unknown criterion rejected",
                  lambda: normalise_weights({"Vibes": 100}), RubricError)
    expect_raises("Weights not totalling 100 rejected",
                  lambda: normalise_weights({"Security": 90}), RubricError)
    expect_raises("Negative weight rejected",
                  lambda: normalise_weights({"Security": -5, "Scalability": 25}),
                  RubricError)
    check("Band boundaries resolve",
          band_for_score(95).name == "Excellent"
          and band_for_score(80).name == "Strong"
          and band_for_score(65).name == "Usable"
          and band_for_score(45).name == "Weak"
          and band_for_score(10).name == "Critical",
          f"95->{band_for_score(95).name}, 80->{band_for_score(80).name}, "
          f"65->{band_for_score(65).name}, 45->{band_for_score(45).name}, "
          f"10->{band_for_score(10).name}")


# ---------------------------------------------------------------------------
# 2. Scoring maths
# ---------------------------------------------------------------------------

def test_scoring() -> None:
    print("\n--- 2. Scoring ---")
    checks_list = [HardConstraintCheck(constraint="All good", status="PASS", severity="INFO")]

    result = compute_overall(_criteria(), checks_list)
    scored = result["criteria"]
    raw = result["raw_weighted_score"]
    check("9 scored criteria returned", len(scored) == 9, f"= {len(scored)}")
    check("All scores are ints", all(isinstance(c["score"], int) for c in scored))
    check("Weighted total is a float", isinstance(raw, float), f"= {raw}")

    # Recompute the expected weighted total independently.
    expected = round(sum(
        DEFAULT_WEIGHTS[name] * score / 100.0
        for name, score in {
            "Requirement Coverage": 80, "Architecture Feasibility": 78,
            "Technology Alignment": 90, "Scalability": 70, "Security": 64,
            "Timeline Feasibility": 58, "Constraint Compliance": 88,
            "MVP Focus": 80, "Avoid Over-engineering": 95,
        }.items()
    ), 2)
    check("Weighted total matches hand calculation", abs(raw - expected) < 0.01,
          f"got {raw}, expected {expected}")

    # A missing criterion must score 0, not be silently dropped.
    partial = [c for c in _criteria() if c.name != "Security"]
    raw_partial = compute_overall(partial, checks_list)["raw_weighted_score"]
    check("Missing criterion scores 0 (not dropped)",
          abs((expected - raw_partial) - (64 * 10 / 100.0)) < 0.01,
          f"delta={expected - raw_partial:.2f}, expected 6.40")

    # Penalties
    fail_critical = [HardConstraintCheck(
        constraint="Cloud provider must be AWS", status="FAIL", severity="CRITICAL")]
    scored_pen = compute_overall(_criteria(), fail_critical)
    check("CRITICAL FAIL costs 20", scored_pen["constraint_penalty"] == 20.0,
          f"= {scored_pen['constraint_penalty']}")
    check("CRITICAL FAIL recorded in failed_constraints",
          scored_pen["failed_constraints"] == ["Cloud provider must be AWS"])
    # overall_score is deliberately rounded to 1 dp, so compare against the
    # rounded expectation rather than the raw float.
    check("Overall = raw - penalty (rounded to 1dp)",
          scored_pen["overall_score"] == round(raw - 20.0, 1),
          f"= {scored_pen['overall_score']}, expected {round(raw - 20.0, 1)}")

    warn_minor = [HardConstraintCheck(
        constraint="Traffic", status="WARN", severity="MINOR")]
    scored_warn = compute_overall(_criteria(), warn_minor)
    check("WARN costs half the severity penalty (1.5)",
          scored_warn["constraint_penalty"] == 1.5,
          f"= {scored_warn['constraint_penalty']}")
    check("WARN recorded in warned_constraints",
          scored_warn["warned_constraints"] == ["Traffic"])

    # Cap: 6 CRITICAL failures would be -120, but the cap is 45.
    many = [HardConstraintCheck(constraint=f"C{i}", status="FAIL", severity="CRITICAL")
            for i in range(6)]
    scored_cap = compute_overall(_criteria(), many)
    check("Penalty capped at 45", scored_cap["constraint_penalty"] == 45.0,
          f"= {scored_cap['constraint_penalty']}")
    check("Capped score = raw - 45 (rounded to 1dp)",
          scored_cap["overall_score"] == round(raw - 45.0, 1),
          f"= {scored_cap['overall_score']}, expected {round(raw - 45.0, 1)}")

    # Floor: a low raw score minus the maximum penalty must clamp at 0, not
    # go negative.
    floor = compute_overall(_criteria(**{name: 0 for name in CRITERION_ORDER}), many)
    check("Score never goes below 0", floor["overall_score"] == 0.0,
          f"= {floor['overall_score']}")

    # JSON-safety: this dict goes into MongoDB and the SSE payload.
    try:
        json.dumps(scored_pen)
        check("compute_overall() output is JSON-serialisable", True)
    except TypeError as exc:
        check("compute_overall() output is JSON-serialisable", False, str(exc))

    # Clamping of a nonsense LLM score
    clamped = CriterionEvaluation(name="Security", score=9999)
    check("Out-of-range LLM score is clamped to 100", clamped.score == 100,
          f"= {clamped.score}")


# ---------------------------------------------------------------------------
# 3. Timeline week estimation
# ---------------------------------------------------------------------------

def test_timeline_estimation() -> None:
    print("\n--- 3. Timeline estimation ---")
    cases = [
        ("month ranges", ["Month 1: a", "Month 2-3: b", "Month 4: c"], 4 * 4.33),
        ("explicit weeks", ["Phase 1 (4 weeks)", "Phase 2 (6 weeks)"], 10.0),
        ("dict durations",
         [{"phase": "a", "duration_weeks": 3}, {"phase": "b", "duration_weeks": 5}], 8.0),
        ("days only", ["Sprint 1: 10 days", "Sprint 2: 10 days"], 4.0),
        ("plain string", ["Month 1-2: discovery", "Month 3-4: build"], 17.3),
    ]
    for name, timeline, expected in cases:
        got = estimate_delivery_weeks(timeline)
        check(f"estimate_delivery_weeks: {name}", abs(got - expected) < 0.05,
              f"got {got}, expected {expected}")
    check("estimate_delivery_weeks: empty -> 0", estimate_delivery_weeks([]) == 0.0)
    check("estimate_delivery_weeks: None -> 0", estimate_delivery_weeks(None) == 0.0)
    check("estimate_delivery_weeks: junk -> 0", estimate_delivery_weeks(["TBD"]) == 0.0)


# ---------------------------------------------------------------------------
# 4. Hard-constraint checks
# ---------------------------------------------------------------------------

def test_constraint_checks() -> None:
    print("\n--- 4. Hard-constraint checks ---")
    sa = coerce_agent_output(SolutionArchitecture, SA)
    ta = coerce_agent_output(TechnologyRecommendation, TA)
    dp = coerce_agent_output(DeliveryPlan, DP)
    check("SA/TA/DP coerce from stored dicts", None not in (sa, ta, dp))
    check("raw fallback is rejected by coerce",
          coerce_agent_output(TechnologyRecommendation, {"raw": "not json"}) is None)
    check("None is rejected by coerce",
          coerce_agent_output(TechnologyRecommendation, None) is None)

    cloud = check_cloud_provider(USER_INPUT, ta)
    check("Cloud provider: AWS requested, AWS chosen -> PASS",
          cloud.status == "PASS", f"= {cloud.status}")

    azure_ta = TechnologyRecommendation.model_validate({**TA, "cloud": {
        "provider": "Microsoft Azure", "services": ["App Service"]}})
    cloud_bad = check_cloud_provider(USER_INPUT, azure_ta)
    check("Cloud provider: AWS requested, Azure chosen -> FAIL/CRITICAL",
          cloud_bad.status == "FAIL" and cloud_bad.severity == "CRITICAL",
          f"= {cloud_bad.status}/{cloud_bad.severity}")

    no_pref = {**USER_INPUT, "cloud_preference": "No Specific Preference"}
    cloud_none = check_cloud_provider(no_pref, ta)
    check("Cloud: 'No Specific Preference' is treated as no preference -> PASS",
          cloud_none.status == "PASS", f"= {cloud_none.status}")

    residency = check_data_residency(USER_INPUT, ta, sa)
    check("Data residency: India not mentioned in outputs -> not a silent PASS",
          residency.status in ("WARN", "FAIL"), f"= {residency.status}")

    india_ta = TechnologyRecommendation.model_validate(
        {**TA, "security_considerations": ["Data stored in ap-south-1 (Mumbai)"]})
    residency_ok = check_data_residency(USER_INPUT, india_ta, sa)
    check("Data residency: ap-south-1 mentioned -> PASS",
          residency_ok.status == "PASS", f"= {residency_ok.status}")

    tech = check_technology_preference(USER_INPUT, ta)
    check("Tech preference: open-source stack -> PASS",
          tech.status == "PASS", f"= {tech.status}")

    vendor_ta = TechnologyRecommendation.model_validate({**TA, "technologies": [
        {"category": "Database", "technology": "Oracle Database", "reason": "x"},
        {"category": "Search", "technology": "Splunk", "reason": "y"},
    ]})
    tech_bad = check_technology_preference(USER_INPUT, vendor_ta)
    check("Tech preference: 2 proprietary in open-source ask -> FAIL/MAJOR",
          tech_bad.status == "FAIL" and tech_bad.severity == "MAJOR",
          f"= {tech_bad.status}/{tech_bad.severity}")

    timeline = check_timeline(USER_INPUT, dp)
    check("Timeline: 6-month plan for a 6-month target -> PASS",
          timeline.status == "PASS", f"= {timeline.status}")

    slow_dp = DeliveryPlan.model_validate({**DP, "timeline": [
        "Month 1-2: a", "Month 3-4: b", "Month 5-6: c",
        "Month 7-8: d", "Month 9: e", "Month 10-11: f",
    ]})
    timeline_bad = check_timeline(USER_INPUT, slow_dp)
    check("Timeline: 11-month plan for a 6-month target -> FAIL",
          timeline_bad.status == "FAIL", f"= {timeline_bad.status}/{timeline_bad.severity}")

    empty_dp = DeliveryPlan.model_validate({**DP, "timeline": ["TBD"]})
    timeline_junk = check_timeline(USER_INPUT, empty_dp)
    check("Timeline: no durations -> FAIL/MAJOR",
          timeline_junk.status == "FAIL" and timeline_junk.severity == "MAJOR",
          f"= {timeline_junk.status}/{timeline_junk.severity}")

    traffic = check_traffic_propagation(USER_INPUT, sa, ta, BA)
    check("Traffic: 2,000 referenced in outputs -> PASS",
          traffic.status == "PASS", f"= {traffic.status}")

    # Strip the figure out of every output so only the *discussion* of scale
    # remains — that is the WARN branch.
    ba_no_figure = {**BA, "non_functional_requirements": ["Must be fast"]}
    sa_no_figure = SolutionArchitecture.model_validate({
        **SA,
        "architecture_rationale": "Fits the goal.",
        "scalability": ["Scale horizontally as load increases"],
    })
    ta_no_figure = TechnologyRecommendation.model_validate({
        **TA,
        "technology_strategy": "Lean.",
        "scalability_considerations": ["Nothing about a specific figure"],
    })
    traffic_warn = check_traffic_propagation(
        USER_INPUT, sa_no_figure, ta_no_figure, ba_no_figure)
    check("Traffic: scale discussed but no figure -> WARN",
          traffic_warn.status == "WARN", f"= {traffic_warn.status}")

    # Everything stripped: no figure anywhere, and no scale vocabulary either.
    bare_sa = SolutionArchitecture.model_validate({
        **SA,
        "architecture_rationale": "Fits the goal.",
        "scalability": ["Handled as required"],
        "data_flow": ["One to two"],
        "security": ["Standard"],
        "mvp_architecture": ["Single service"],
    })
    bare_ta = TechnologyRecommendation.model_validate({
        **TA,
        "technology_strategy": "Lean.",
        "scalability_considerations": ["As needed"],
        "security_considerations": ["Standard"],
    })
    traffic_fail = check_traffic_propagation(
        USER_INPUT, bare_sa, bare_ta, {"mvp_scope": ["A thing"]})
    check("Traffic: figure and scale both absent -> FAIL/MAJOR",
          traffic_fail.status == "FAIL" and traffic_fail.severity == "MAJOR",
          f"= {traffic_fail.status}/{traffic_fail.severity}")

    mvp = check_mvp_coverage(BA, dp)
    check("MVP coverage: BA scope traceable into DP -> PASS",
          mvp.status == "PASS", f"= {mvp.status}")

    mvp_fail = check_mvp_coverage({**BA, "mvp_scope": []}, dp)
    check("MVP coverage: no BA MVP scope -> FAIL/MAJOR",
          mvp_fail.status == "FAIL" and mvp_fail.severity == "MAJOR",
          f"= {mvp_fail.status}/{mvp_fail.severity}")


# ---------------------------------------------------------------------------
# 5. Degradation
# ---------------------------------------------------------------------------

def test_degradation() -> None:
    print("\n--- 5. Degradation when agents fail ---")
    for label, ta, sa, dp, ba in [
        ("TA missing", None, coerce_agent_output(SolutionArchitecture, SA),
         coerce_agent_output(DeliveryPlan, DP), BA),
        ("all missing", None, None, None, None),
        ("raw fallbacks", None, {"raw": "prose"}, {"raw": "prose"}, {"raw": "prose"}),
    ]:
        c = check_cloud_provider(USER_INPUT, ta)
        t = check_timeline(USER_INPUT, dp)
        m = check_mvp_coverage(ba, dp)
        ok = (
            c.severity == "INFO" and t.severity == "INFO" and m.severity == "INFO"
        )
        check(f"{label}: checks degrade to INFO (no penalty)", ok,
              f"cloud={c.status}/{c.severity}, timeline={t.status}/{t.severity}, "
              f"mvp={m.status}/{m.severity}")


# ---------------------------------------------------------------------------
# 6. build_judge_output
# ---------------------------------------------------------------------------

class _FakeTaskOutput:
    """Stands in for a CrewAI TaskOutput."""

    def __init__(self, pydantic=None, json_dict=None, raw=None):
        self.pydantic = pydantic
        self.json_dict = json_dict
        self.raw = raw


def test_build_judge_output() -> None:
    print("\n--- 6. build_judge_output ---")
    agent_outputs = {
        "business_analysis": BA,
        "solution_architecture": SA,
        "technology_recommendation": TA,
        "delivery_plan": DP,
    }

    evaluation = JudgeEvaluation(
        criteria=_criteria(),
        strengths=["Lean open-source stack", "Realistic MVP scope"],
        weaknesses=["Security is thin", "Timeline is optimistic"],
        critical_issues=[],
        recommended_improvements=["Add SSO before launch"],
        cross_agent_consistency="BA/SA/TA agree; DP is the most optimistic.",
        judge_summary="A solid lean MVP plan with a security gap to close.",
    )

    out = build_judge_output(USER_INPUT, agent_outputs, evaluation)

    check("judge_status == complete", out["judge_status"] == "complete",
          f"= {out['judge_status']}")
    check("9 criteria scored", len(out["criteria"]) == 9, f"= {len(out['criteria'])}")
    check("overall_score is numeric", isinstance(out["overall_score"], (int, float)),
          f"= {out['overall_score']}")
    check("quality_band assigned", bool(out["quality_band"]), f"= {out['quality_band']}")
    check("6 hard-constraint checks returned",
          len(out["hard_constraint_checks"]) == 6,
          f"= {len(out['hard_constraint_checks'])}")
    check("checks carry evidence",
          all(c.get("evidence") for c in out["hard_constraint_checks"]))
    check("narrative carried through",
          out["strengths"] == evaluation.strengths
          and out["judge_summary"] == evaluation.judge_summary)
    check("llm_evaluation_available is True", out["llm_evaluation_available"] is True)
    try:
        json.dumps(out)
        check("judge_output is JSON-serialisable (MongoDB + SSE safe)", True)
    except TypeError as exc:
        check("judge_output is JSON-serialisable (MongoDB + SSE safe)", False, str(exc))

    # TaskOutput passthrough (pydantic / json_dict / raw JSON / prose)
    pyd_out = build_judge_output(USER_INPUT, agent_outputs,
                                 _FakeTaskOutput(pydantic=evaluation))
    check("Accepts a TaskOutput with .pydantic",
          pyd_out["overall_score"] == out["overall_score"])

    dict_out = build_judge_output(
        USER_INPUT, agent_outputs, evaluation.model_dump(mode="json"))
    check("Accepts a plain dict", dict_out["overall_score"] == out["overall_score"])

    raw_out = build_judge_output(
        USER_INPUT, agent_outputs,
        _FakeTaskOutput(raw="Sure! Here you go:\n" + json.dumps(evaluation.model_dump(mode="json"))))
    check("Recovers evaluation from raw JSON in prose",
          raw_out["overall_score"] == out["overall_score"])

    junk_out = build_judge_output(USER_INPUT, agent_outputs,
                                  _FakeTaskOutput(raw="I could not evaluate this."))
    check("Prose-only judge output degrades without crashing",
          junk_out["llm_evaluation_available"] is False
          and junk_out["judge_status"] == "partial"
          and "did not return a usable evaluation" in junk_out["judge_summary"],
          f"status={junk_out['judge_status']}")

    none_out = build_judge_output(USER_INPUT, agent_outputs, None)
    check("evaluation=None still yields a judge_output",
          none_out["llm_evaluation_available"] is False
          and len(none_out["hard_constraint_checks"]) == 6)

    empty_out = build_judge_output(USER_INPUT, {}, None)
    check("Empty agent_outputs does not raise", len(empty_out["hard_constraint_checks"]) == 6)

    # A bad weight override must fall back, not explode.
    bad_weights = build_judge_output(USER_INPUT, agent_outputs, evaluation,
                                     weights={"Security": 90})
    check("Invalid weight override falls back to defaults",
          bad_weights["rubric_weights"] == DEFAULT_WEIGHTS
          and "rejected" in bad_weights["scoring_explanation"])

    # A CRITICAL violation must be visible in the headline number.
    azure_ta = {**TA, "cloud": {"provider": "Microsoft Azure", "services": ["App Service"]}}
    violated = build_judge_output(
        USER_INPUT, {**agent_outputs, "technology_recommendation": azure_ta}, evaluation)
    check("CRITICAL constraint violation lowers the score and is listed",
          violated["overall_score"] == out["overall_score"] - 20.0
          and len(violated["failed_constraints"]) >= 1,
          f"{out['overall_score']} -> {violated['overall_score']}, "
          f"failed={violated['failed_constraints']}")

    check("evaluation_from_task_output(None) is None",
          evaluation_from_task_output(None) is None)


# ---------------------------------------------------------------------------
# 7. Blueprint rendering
# ---------------------------------------------------------------------------

def test_blueprint_renders_judge() -> None:
    print("\n--- 7. Blueprint HTML ---")
    from backend.utils.blueprint_generator import generate_blueprint_html

    agent_outputs = {
        "business_analysis": BA,
        "solution_architecture": SA,
        "technology_recommendation": TA,
        "delivery_plan": DP,
    }
    judge = build_judge_output(USER_INPUT, agent_outputs, JudgeEvaluation(
        criteria=_criteria(),
        strengths=["Lean open-source stack"],
        weaknesses=["Security is thin"],
        recommended_improvements=["Add SSO before launch"],
        cross_agent_consistency="Mostly consistent.",
        judge_summary="Solid MVP with a security gap.",
    ))

    html = generate_blueprint_html(USER_INPUT, agent_outputs, judge)

    check("Blueprint has a Judge tab", 'id="tab-judge"' in html)
    check("Blueprint has a Judge tab button", "showTab('judge')" in html)
    check("Stepper shows the Quality Judge step", "Quality Judge" in html)
    check("Blueprint renders 9 evaluation domains",
          html.count("domain-card") >= 9, f"= {html.count('domain-card')}")
    check("Blueprint renders the hard-constraint table",
          "Hard Constraint Checks" in html and "Evidence &amp; Fix" in html)
    check("Blueprint renders criterion names",
          all(name in html for name in CRITERION_ORDER))
    check("Blueprint renders the score", str(judge["overall_score"]) in html)
    check("Blueprint renders the band", judge["quality_band"] in html)
    check("Blueprint renders the summary", "Solid MVP with a security gap." in html)
    check("Judge also appears in the combined Report tab",
          html.count("Judge Evaluation") >= 2)
    check("Overview shows a Judge score card", "Judge Score" in html)
    check("Blueprint starts with DOCTYPE", html.lstrip().startswith("<!DOCTYPE html>"))

    # judge_output=None must still produce a valid page.
    html_none = generate_blueprint_html(USER_INPUT, agent_outputs, None)
    check("judge_output=None -> no Judge tab", 'id="tab-judge"' not in html_none)
    check("judge_output=None -> still a valid page",
          html_none.lstrip().startswith("<!DOCTYPE html>") and len(html_none) > 10000)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 66)
    print("SOLUTION-FORGE-AI  JUDGE UNIT TEST (offline: no LLM, no DB)")
    print("=" * 66)

    test_rubric()
    test_scoring()
    test_timeline_estimation()
    test_constraint_checks()
    test_degradation()
    test_build_judge_output()
    test_blueprint_renders_judge()

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print("\n" + "=" * 66)
    print(f"SUMMARY: {passed}/{total} passed")
    for name, ok, detail in results:
        if not ok:
            print(f"  FAIL -> {name}" + (f"  ({detail})" if detail else ""))
    print("=" * 66)
    raise SystemExit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
