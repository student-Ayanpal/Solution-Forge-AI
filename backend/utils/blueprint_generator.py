"""
backend/utils/blueprint_generator.py

Converts the four CrewAI agent outputs (Business Analyst, Solution Architect,
Technology Advisor, Delivery Planner) plus the Judge's evaluation JSON into a
single, self-contained, styled "blueprint.html" report.

This is the module that plugs into the TODO in
backend/routers/consultations.py:

    # 3) Mark completed. (judge + blueprint_html filled in a later phase)

Usage
-----
    from backend.utils.blueprint_generator import generate_blueprint_html

    html = generate_blueprint_html(
        user_input=payload.model_dump(mode="json"),
        agent_outputs=saved,            # dict returned by run_consultation()
        judge_output=judge_result,      # dict from scoring.compute_overall() + LLM narrative fields, or None
    )
    complete_consultation(consultation.id, judge_result, html)

Design notes
------------
- Every renderer is defensive: agent outputs coming out of
  ``crew_service._output_to_dict`` are either the structured Pydantic dict
  (BusinessAnalysis / SolutionArchitecture / TechnologyRecommendation /
  DeliveryPlan, see app/models/*.py) OR a ``{"raw": "..."}`` fallback if the
  LLM did not return valid structured output. Both are handled.
- The Judge section expects the shape produced by
  ``app/judge/scoring.py::compute_overall()`` (criteria / raw_weighted_score /
  constraint_penalty / overall_score / quality_band / scoring_explanation),
  merged with the narrative fields the Judge LLM prompt
  (app/judge/judge.py) asks for: strengths, weaknesses, critical_issues,
  recommended_improvements, cross_agent_consistency, judge_summary, and
  optionally hard_constraint_checks (list of the HardConstraintCheck dicts
  app/judge/constraints.py produces). None of these keys are required — any
  missing piece is simply skipped in the render.
- No external dependencies beyond the Python standard library.
"""

from __future__ import annotations
import base64
import html as _html
from pathlib import Path

from datetime import datetime, timedelta, timezone
from string import Template
from typing import Any, Iterable, Optional

IST_OFFSET = timezone(timedelta(hours=5, minutes=30))


def _ist_now() -> datetime:
    """Current time in Indian Standard Time (UTC+5:30)."""
    return datetime.now(timezone.utc).astimezone(IST_OFFSET)


# ---------------------------------------------------------------------------
# Small rendering helpers
# ---------------------------------------------------------------------------

def esc(value: Any) -> str:
    """HTML-escape anything, tolerating None."""
    if value is None:
        return ""
    return _html.escape(str(value), quote=True)


def as_list(value: Any) -> list:
    """Coerce a possibly-missing field into a list."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def bullet_list(items: Iterable[Any], empty_text: str = "Not specified.") -> str:
    items = [i for i in as_list(items) if str(i).strip()]
    if not items:
        return f'<p class="muted">{esc(empty_text)}</p>'
    lis = "".join(f"<li>{esc(i)}</li>" for i in items)
    return f"<ul class='bullet-list'>{lis}</ul>"


def is_raw_fallback(section: Any) -> bool:
    """True if the agent output degraded to the {'raw': '...'} fallback."""
    return isinstance(section, dict) and set(section.keys()) <= {"raw"} and "raw" in section


def raw_fallback_html(section: dict) -> str:
    text = esc(section.get("raw", ""))
    return (
        "<div class='raw-fallback'>"
        "<p class='muted'>The agent did not return structured output for this "
        "section, showing the raw response instead:</p>"
        f"<pre>{text}</pre></div>"
    )


def section_card(title: str, body_html: str, icon: str = "") -> str:
    return (
        "<div class='sub-card'>"
        f"<h3>{icon} {esc(title)}</h3>"
        f"{body_html}"
        "</div>"
    )


BAND_COLORS = {
    "Excellent": "#1a9b5c",
    "Strong": "#2f6bff",
    "Usable": "#d9a300",
    "Weak": "#e06b1f",
    "Critical": "#e0342f",
}

STATUS_COLORS = {
    "PASS": ("#e6f7ee", "#1a9b5c"),
    "WARN": ("#fff6e0", "#c98a00"),
    "FAIL": ("#fdeaea", "#d9342c"),
}

SEVERITY_COLORS = {
    "CRITICAL": "#d9342c",
    "MAJOR": "#e06b1f",
    "MINOR": "#c98a00",
    "INFO": "#6b7280",
}


# ---------------------------------------------------------------------------
# Section renderers — Business Analyst
# ---------------------------------------------------------------------------

def render_business_analysis(ba: Optional[dict]) -> str:
    if not ba:
        return "<p class='muted'>Business analysis has not been generated yet.</p>"
    if is_raw_fallback(ba):
        return raw_fallback_html(ba)

    parts = []
    parts.append(section_card(
        "Problem Statement",
        f"<p>{esc(ba.get('problem_statement'))}</p>" if ba.get("problem_statement")
        else "<p class='muted'>Not specified.</p>",
        "🎯",
    ))
    parts.append(
        "<div class='grid-2'>"
        + section_card("Users", bullet_list(ba.get("users")), "👤")
        + section_card("Stakeholders", bullet_list(ba.get("stakeholders")), "🤝")
        + "</div>"
    )
    parts.append(
        "<div class='grid-2'>"
        + section_card("Functional Requirements", bullet_list(ba.get("functional_requirements")), "⚙️")
        + section_card("Non-Functional Requirements", bullet_list(ba.get("non_functional_requirements")), "📐")
        + "</div>"
    )
    parts.append(
        "<div class='grid-2'>"
        + section_card("MVP Scope", bullet_list(ba.get("mvp_scope")), "✅")
        + section_card("Future Scope", bullet_list(ba.get("future_scope")), "🔭")
        + "</div>"
    )
    parts.append(
        "<div class='grid-2'>"
        + section_card("Constraints", bullet_list(ba.get("constraints")), "🚧")
        + section_card("Assumptions", bullet_list(ba.get("assumptions")), "💭")
        + "</div>"
    )
    parts.append(
        "<div class='grid-2'>"
        + section_card("Risks", bullet_list(ba.get("risks")), "⚠️")
        + section_card("Open Questions", bullet_list(ba.get("open_questions")), "❓")
        + "</div>"
    )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Section renderers — Solution Architect
# ---------------------------------------------------------------------------

def render_architecture(sa: Optional[dict]) -> str:
    if not sa:
        return "<p class='muted'>Architecture has not been generated yet.</p>"
    if is_raw_fallback(sa):
        return raw_fallback_html(sa)

    parts = []
    parts.append(section_card(
        "Architecture Style",
        f"<p>{esc(sa.get('architecture_style'))}</p>" if sa.get("architecture_style")
        else "<p class='muted'>Not specified.</p>",
        "🏗️",
    ))

    components = as_list(sa.get("components"))
    if components:
        rows = "".join(
            f"<tr><td>{esc(c.get('name') if isinstance(c, dict) else c)}</td>"
            f"<td>{esc(c.get('responsibility') if isinstance(c, dict) else '')}</td></tr>"
            for c in components
        )
        comp_html = (
            "<table class='data-table'><thead><tr><th>Component</th>"
            f"<th>Responsibility</th></tr></thead><tbody>{rows}</tbody></table>"
        )
    else:
        comp_html = "<p class='muted'>Not specified.</p>"
    parts.append(section_card("Major Components", comp_html, "🧩"))

    db = sa.get("database") or {}
    cache = sa.get("cache") or {}
    db_html = (
        f"<p><strong>Type:</strong> {esc(db.get('type', '—'))}</p>"
        f"<p><strong>Purpose:</strong> {esc(db.get('purpose', '—'))}</p>"
    ) if db else "<p class='muted'>Not specified.</p>"
    cache_html = (
        f"<p><strong>Required:</strong> {'Yes' if cache.get('required') else 'No'}</p>"
        f"<p><strong>Purpose:</strong> {esc(cache.get('purpose', '—'))}</p>"
    ) if cache else "<p class='muted'>Not specified.</p>"
    parts.append(
        "<div class='grid-2'>"
        + section_card("Database Design", db_html, "🗄️")
        + section_card("Cache Design", cache_html, "⚡")
        + "</div>"
    )

    parts.append(section_card("Data Flow", bullet_list(sa.get("data_flow")), "🔀"))

    parts.append(
        "<div class='grid-2'>"
        + section_card("Security Approach", bullet_list(sa.get("security")), "🔒")
        + section_card("Scalability Approach", bullet_list(sa.get("scalability")), "📈")
        + "</div>"
    )
    parts.append(
        "<div class='grid-2'>"
        + section_card("MVP Architecture", bullet_list(sa.get("mvp_architecture")), "✅")
        + section_card("Future Evolution", bullet_list(sa.get("future_evolution")), "🔭")
        + "</div>"
    )
    if sa.get("architecture_rationale"):
        parts.append(section_card("Rationale", f"<p>{esc(sa.get('architecture_rationale'))}</p>", "💡"))
    parts.append(section_card("Architecture Risks", bullet_list(sa.get("architecture_risks")), "⚠️"))

    return "".join(parts)


def architecture_diagram_html(sa: Optional[dict], ta: Optional[dict]) -> str:
    """A simple horizontal box diagram, in the spirit of the reference UI's
    'High-Level Architecture' strip, built from whatever components/cloud
    services the agents actually returned."""
    components = as_list((sa or {}).get("components")) if sa and not is_raw_fallback(sa) else []
    boxes = []
    if components:
        for c in components[:6]:
            name = c.get("name") if isinstance(c, dict) else str(c)
            boxes.append(f"<div class='diagram-box'><span>{esc(name)}</span></div>")
    else:
        boxes = [f"<div class='diagram-box'><span>{n}</span></div>" for n in
                 ["Client", "API Layer", "Backend Services", "Data Layer"]]

    cloud = (ta or {}).get("cloud") if ta and not is_raw_fallback(ta) else None
    cloud_html = ""
    if cloud and cloud.get("provider"):
        services = "".join(f"<div class='diagram-chip'>{esc(s)}</div>" for s in as_list(cloud.get("services"))[:6])
        cloud_html = (
            "<div class='diagram-cloud'>"
            f"<div class='diagram-cloud-label'>☁️ {esc(cloud.get('provider'))} Cloud Infrastructure</div>"
            f"<div class='diagram-chip-row'>{services}</div>"
            "</div>"
        )

    arrow = "<div class='diagram-arrow'>&rarr;</div>"
    row = arrow.join(boxes)
    return (
        "<div class='arch-diagram'>"
        f"<div class='diagram-row'>{row}</div>"
        f"{cloud_html}"
        "</div>"
    )


# ---------------------------------------------------------------------------
# Section renderers — Technology Advisor
# ---------------------------------------------------------------------------

def render_technology(ta: Optional[dict]) -> str:
    if not ta:
        return "<p class='muted'>Technology recommendations have not been generated yet.</p>"
    if is_raw_fallback(ta):
        return raw_fallback_html(ta)

    parts = []
    technologies = as_list(ta.get("technologies"))
    if technologies:
        rows = "".join(
            "<tr>"
            f"<td>{esc(t.get('category') if isinstance(t, dict) else '')}</td>"
            f"<td><strong>{esc(t.get('technology') if isinstance(t, dict) else t)}</strong></td>"
            f"<td>{esc(t.get('reason') if isinstance(t, dict) else '')}</td>"
            "</tr>"
            for t in technologies
        )
        tech_html = (
            "<table class='data-table'><thead><tr><th>Category</th><th>Technology</th>"
            f"<th>Reason</th></tr></thead><tbody>{rows}</tbody></table>"
        )
    else:
        tech_html = "<p class='muted'>Not specified.</p>"
    parts.append(section_card("Recommended Technology Stack", tech_html, "💻"))

    cloud = ta.get("cloud") or {}
    if cloud:
        services = "".join(f"<span class='pill'>{esc(s)}</span>" for s in as_list(cloud.get("services")))
        cloud_html = f"<p><strong>Provider:</strong> {esc(cloud.get('provider', '—'))}</p><div class='pill-row'>{services}</div>"
    else:
        cloud_html = "<p class='muted'>Not specified.</p>"
    parts.append(section_card("Cloud Services", cloud_html, "☁️"))

    if ta.get("technology_strategy"):
        parts.append(section_card("Technology Strategy", f"<p>{esc(ta.get('technology_strategy'))}</p>", "🧭"))

    alternatives = as_list(ta.get("alternatives"))
    if alternatives:
        rows = "".join(
            "<tr>"
            f"<td>{esc(a.get('category'))}</td><td>{esc(a.get('recommended'))}</td>"
            f"<td>{esc(a.get('alternative'))}</td><td>{esc(a.get('reason'))}</td>"
            "</tr>" for a in alternatives if isinstance(a, dict)
        )
        alt_html = (
            "<table class='data-table'><thead><tr><th>Category</th><th>Recommended</th>"
            f"<th>Alternative</th><th>Reason</th></tr></thead><tbody>{rows}</tbody></table>"
        )
        parts.append(section_card("Meaningful Alternatives", alt_html, "🔁"))

    trade_offs = as_list(ta.get("trade_offs"))
    if trade_offs:
        cards = ""
        for t in trade_offs:
            if not isinstance(t, dict):
                continue
            cards += (
                "<div class='tradeoff-card'>"
                f"<h4>{esc(t.get('decision'))}</h4>"
                "<div class='grid-2'>"
                f"<div><strong class='ok'>Advantages</strong>{bullet_list(t.get('advantages'))}</div>"
                f"<div><strong class='bad'>Disadvantages</strong>{bullet_list(t.get('disadvantages'))}</div>"
                "</div></div>"
            )
        parts.append(section_card("Trade-offs", cards, "⚖️"))

    parts.append(
        "<div class='grid-2'>"
        + section_card("Security Considerations", bullet_list(ta.get("security_considerations")), "🔒")
        + section_card("Scalability Considerations", bullet_list(ta.get("scalability_considerations")), "📈")
        + "</div>"
    )
    parts.append(
        "<div class='grid-2'>"
        + section_card("Technology Risks", bullet_list(ta.get("technology_risks")), "⚠️")
        + section_card("Lock-in Considerations", bullet_list(ta.get("lock_in_considerations")), "🔗")
        + "</div>"
    )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Section renderers — Delivery Planner
# ---------------------------------------------------------------------------

def render_delivery(dp: Optional[dict]) -> str:
    if not dp:
        return "<p class='muted'>Delivery plan has not been generated yet.</p>"
    if is_raw_fallback(dp):
        return raw_fallback_html(dp)

    parts = []
    if dp.get("delivery_overview"):
        parts.append(section_card("Delivery Overview", f"<p>{esc(dp.get('delivery_overview'))}</p>", "📋"))
    parts.append(
        "<div class='grid-2'>"
        + section_card("MVP Scope", bullet_list(dp.get("mvp_scope")), "✅")
        + section_card("Future Scope", bullet_list(dp.get("future_scope")), "🔭")
        + "</div>"
    )
    parts.append(section_card("Implementation Workstreams", bullet_list(dp.get("workstreams")), "🧵"))
    parts.append(section_card("Timeline & Milestones", bullet_list(dp.get("timeline")), "🗓️"))
    parts.append(
        "<div class='grid-2'>"
        + section_card(
            "Effort Assessment",
            bullet_list(dp.get("effort_assessment"), "Not estimated."),
            "⏱️",
        )
        + section_card(
            "Complexity Assessment",
            bullet_list(dp.get("complexity_assessment"), "Not assessed."),
            "🧠",
        )
        + "</div>"
    )
    parts.append(section_card("Recommended Team & Roles", bullet_list(dp.get("team")), "👥"))
    parts.append(section_card("Dependencies", bullet_list(dp.get("dependencies")), "🔗"))
    parts.append(section_card("Delivery Risks", bullet_list(dp.get("risks")), "⚠️"))
    parts.append(
        "<div class='grid-2'>"
        + section_card("Testing Strategy", bullet_list(dp.get("testing_strategy")), "🧪")
        + section_card("Deployment Plan", bullet_list(dp.get("deployment_plan")), "🚀")
        + "</div>"
    )
    parts.append(section_card("Maintenance Plan", bullet_list(dp.get("maintenance_plan")), "🛠️"))
    parts.append(
        "<div class='grid-2'>"
        + section_card("Assumptions", bullet_list(dp.get("assumptions")), "💭")
        + section_card("Open Questions", bullet_list(dp.get("open_questions")), "❓")
        + "</div>"
    )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Section renderer — Judge  (the new "domains, click to expand" section)
# ---------------------------------------------------------------------------

def _score_bar(score: float) -> str:
    score = max(0, min(100, float(score or 0)))
    color = "#1a9b5c" if score >= 75 else "#d9a300" if score >= 50 else "#d9342c"
    return (
        "<div class='score-bar'>"
        f"<div class='score-bar-fill' style='width:{score}%;background:{color}'></div>"
        "</div>"
    )


def render_judge(judge: Optional[dict]) -> str:
    if not judge:
        return (
            "<div class='empty-state'>"
            "<p class='muted'>The Judge has not evaluated this blueprint. This "
            "happens when the consultation is still running, or when the Judge "
            "step failed — re-run the consultation to get a score, the "
            "hard-constraint checks and the per-domain evaluation.</p>"
            "</div>"
        )
    if is_raw_fallback(judge):
        return raw_fallback_html(judge)

    overall = judge.get("overall_score")
    band = judge.get("quality_band", "—")
    band_color = BAND_COLORS.get(band, "#2f6bff")

    header = (
        "<div class='judge-header'>"
        "<div class='judge-score-ring' style="
        f"'--pct:{overall or 0}; --ring-color:{band_color}'>"
        f"<div class='judge-score-value'>{esc(overall) if overall is not None else '—'}</div>"
        "<div class='judge-score-label'>/ 100</div>"
        "</div>"
        "<div class='judge-header-text'>"
        f"<span class='badge' style='background:{band_color}22;color:{band_color}'>{esc(band)}</span>"
        f"<p>{esc(judge.get('scoring_explanation', ''))}</p>"
        "<div class='judge-subscores'>"
        f"<span>Raw weighted score: <strong>{esc(judge.get('raw_weighted_score', '—'))}</strong></span>"
        f"<span>Constraint penalty: <strong>-{esc(judge.get('constraint_penalty', 0))}</strong></span>"
        "</div>"
        "</div>"
        "</div>"
    )

    # --- Domains: the 9 rubric criteria, click to expand -------------------
    criteria = as_list(judge.get("criteria"))
    domain_cards = []
    for i, c in enumerate(criteria):
        if not isinstance(c, dict):
            continue
        cid = f"domain-{i}"
        name = c.get("name", f"Criterion {i+1}")
        score = c.get("score", 0)
        weight = c.get("weight", "")
        domain_cards.append(
            "<div class='domain-card'>"
            f"<button type='button' class='domain-toggle' onclick=\"toggleDomain('{cid}')\">"
            "<span class='domain-toggle-main'>"
            f"<span class='domain-name'>{esc(name)}</span>"
            f"<span class='domain-weight'>weight {esc(weight)}%</span>"
            "</span>"
            "<span class='domain-toggle-right'>"
            f"<span class='domain-score'>{esc(score)}</span>"
            f"<span class='chevron' id='chevron-{cid}'>&#9662;</span>"
            "</span>"
            "</button>"
            f"{_score_bar(score)}"
            f"<div class='domain-detail' id='{cid}'>"
            f"<p>{esc(c.get('assessment', 'No assessment provided.'))}</p>"
            + (f"<h5>Evidence</h5>{bullet_list(c.get('evidence'), 'No evidence recorded.')}" if c.get('evidence') else "")
            + (f"<h5>Issues</h5>{bullet_list(c.get('issues'), 'No issues recorded.')}" if c.get('issues') else "")
            + (f"<h5>Suggested improvements</h5>{bullet_list(c.get('improvements'), 'None suggested.')}" if c.get('improvements') else "")
            + "</div></div>"
        )
    domains_html = "".join(domain_cards) if domain_cards else "<p class='muted'>No per-domain evaluation available.</p>"

    # --- Hard constraint checks ---------------------------------------------
    checks = as_list(judge.get("hard_constraint_checks"))
    if checks:
        rows = []
        for chk in checks:
            if not isinstance(chk, dict):
                continue
            status = str(chk.get("status", "")).upper()
            bg, fg = STATUS_COLORS.get(status, ("#eef1f6", "#4b5563"))
            severity = str(chk.get("severity", "")).upper()
            sev_color = SEVERITY_COLORS.get(severity, "#6b7280")
            # `HardConstraintCheck` carries `evidence` + `recommendation`;
            # `detail` is accepted as a fallback for older stored payloads.
            evidence = chk.get("evidence") or chk.get("detail") or ""
            recommendation = chk.get("recommendation") or ""
            detail_html = f"<div>{esc(evidence)}</div>"
            if recommendation:
                detail_html += (
                    "<div style='margin-top:4px; color:var(--muted);'>"
                    f"<strong>Fix:</strong> {esc(recommendation)}</div>"
                )
            rows.append(
                "<tr>"
                f"<td>{esc(chk.get('constraint'))}</td>"
                f"<td><span class='badge' style='background:{bg};color:{fg}'>{esc(status)}</span></td>"
                f"<td><span style='color:{sev_color};font-weight:600'>{esc(severity)}</span></td>"
                f"<td>{detail_html}</td>"
                "</tr>"
            )
        checks_html = (
            "<table class='data-table'><thead><tr><th>Constraint</th><th>Status</th>"
            f"<th>Severity</th><th>Evidence &amp; Fix</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"
        )
    else:
        checks_html = "<p class='muted'>No hard-constraint checks recorded.</p>"

    # Score provenance: what was deducted, and why. Without this the headline
    # number is not reproducible from what is on screen.
    provenance = ""
    failed = as_list(judge.get("failed_constraints"))
    warned = as_list(judge.get("warned_constraints"))
    if failed or warned:
        provenance = section_card(
            "Deduction Breakdown",
            (f"<p><strong>Failed:</strong> {esc(', '.join(failed))}</p>" if failed else "")
            + (f"<p><strong>Warned:</strong> {esc(', '.join(warned))}</p>" if warned else ""),
            "🧮",
        )

    missing = as_list(judge.get("criteria_missing"))
    incomplete_note = ""
    if missing:
        incomplete_note = (
            "<p class='muted'><strong>Note:</strong> the judging model did not "
            f"score {esc(len(missing))} of {esc(len(as_list(judge.get('rubric_criteria'))) or len(missing))} "
            "criteria, so those contribute zero to the total above.</p>"
        )

    narrative = (
        "<div class='grid-2'>"
        + section_card("Strengths", bullet_list(judge.get("strengths")), "💪")
        + section_card("Weaknesses", bullet_list(judge.get("weaknesses")), "🩹")
        + "</div>"
        + "<div class='grid-2'>"
        + section_card("Critical Issues", bullet_list(judge.get("critical_issues"), "None identified."), "🚨")
        + section_card("Recommended Improvements", bullet_list(judge.get("recommended_improvements")), "🛠️")
        + "</div>"
    )
    if judge.get("cross_agent_consistency"):
        narrative += section_card("Cross-Agent Consistency", f"<p>{esc(judge.get('cross_agent_consistency'))}</p>", "🔄")
    if judge.get("judge_summary"):
        narrative += section_card("Judge Summary", f"<p>{esc(judge.get('judge_summary'))}</p>", "📝")

    return (
        header
        + (incomplete_note or "")
        + section_card("Evaluation Domains — click a domain to see the Judge's detailed output", domains_html, "🧭")
        + section_card("Hard Constraint Checks", checks_html, "✅")
        + provenance
        + narrative
    )


# ---------------------------------------------------------------------------
# Overview tab: quick-summary cards + accordion + architecture diagram
# ---------------------------------------------------------------------------

def render_overview(user_input: dict, ba, sa, ta, dp, judge) -> str:
    mvp_scope_preview = ", ".join(str(x) for x in as_list((dp or {}).get("mvp_scope"))[:3]) or \
        ", ".join(str(x) for x in as_list((ba or {}).get("mvp_scope"))[:3]) or "MVP scope not yet available."

    stack_preview = ", ".join(
        (t.get("technology") if isinstance(t, dict) else str(t))
        for t in as_list((ta or {}).get("technologies"))[:4]
    ) or "Technology stack not yet available."

    timeline = user_input.get("delivery_timeline_months") or user_input.get("delivery_timeline")
    timeline_text = f"{timeline} months (Production-ready MVP)" if timeline else "Not specified."

    team_size = len(as_list((dp or {}).get("team"))) or None
    team_text = f"{team_size} roles recommended" if team_size else "Not yet available."

    judge_card = ""
    if judge and not is_raw_fallback(judge):
        score = judge.get("overall_score", "—")
        band = judge.get("quality_band", "—")
        color = BAND_COLORS.get(band, "#2f6bff")
        judge_card = (
            "<div class='summary-card' style=\"--chip:#f4e9ff;--chip-fg:#7b3fe4\">"
            "<div class='summary-icon'>🧭</div>"
            "<h4>Judge Score</h4>"
            f"<p><strong style='color:{color}'>{esc(score)}/100</strong> &middot; {esc(band)}</p>"
            "</div>"
        )

    summary_cards = (
        "<div class='summary-grid'>"
        "<div class='summary-card' style=\"--chip:#e6edff;--chip-fg:#2f6bff\">"
        "<div class='summary-icon'>💡</div><h4>MVP Scope</h4>"
        f"<p>{esc(mvp_scope_preview)}</p></div>"

        "<div class='summary-card' style=\"--chip:#e6f7ee;--chip-fg:#1a9b5c\">"
        "<div class='summary-icon'>⚙️</div><h4>Recommended Stack</h4>"
        f"<p>{esc(stack_preview)}</p></div>"

        "<div class='summary-card' style=\"--chip:#f4e9ff;--chip-fg:#7b3fe4\">"
        "<div class='summary-icon'>🗓️</div><h4>Timeline</h4>"
        f"<p>{esc(timeline_text)}</p></div>"

        "<div class='summary-card' style=\"--chip:#fff2e0;--chip-fg:#e0791f\">"
        "<div class='summary-icon'>👥</div><h4>Team Size</h4>"
        f"<p>{esc(team_text)}</p></div>"
        f"{judge_card}"
        "</div>"
    )

    accordion_items = [
        ("1", "🧑‍💼", "Business Analysis", "Problem, users, requirements, MVP scope, constraints, risks…"),
        ("2", "🏗️", "Solution Architecture", "System design, components, data flow, security, scalability…"),
        ("3", "💻", "Technology Stack", "Technology recommendations, alternatives, trade-offs…"),
        ("4", "📅", "Delivery Plan", "Workstreams, team roles, timeline, milestones…"),
    ]
    if judge and not is_raw_fallback(judge):
        accordion_items.append(("5", "🧭", "Judge Evaluation", "Rubric scores, hard-constraint checks, strengths & risks…"))

    accordion_html = "<div class='accordion'>"
    for num, icon, title, sub in accordion_items:
        target = title.lower().replace(" ", "-")
        accordion_html += (
            "<div class='accordion-item'>"
            f"<button type='button' class='accordion-trigger' onclick=\"goToTab('{target}')\">"
            f"<span class='accordion-icon'>{icon}</span>"
            f"<span class='accordion-text'><strong>{num}. {esc(title)}</strong><br><span class='muted small'>{esc(sub)}</span></span>"
            "<span class='chevron'>&rsaquo;</span>"
            "</button></div>"
        )
    accordion_html += "</div>"

    diagram = architecture_diagram_html(sa, ta)

    return (
        summary_cards
        + section_card("Solution Blueprint Details", accordion_html, "📄")
        + section_card("High-Level Architecture", diagram, "🗺️")
    )


# ---------------------------------------------------------------------------
# Report tab — everything, concatenated, for printing / a single scroll
# ---------------------------------------------------------------------------

def render_report(user_input, ba, sa, ta, dp, judge) -> str:
    return (
        "<div class='report-view'>"
        "<h2>1. Business Analysis</h2>" + render_business_analysis(ba) +
        "<h2>2. Solution Architecture</h2>" + render_architecture(sa) +
        "<h2>3. Technology Stack</h2>" + render_technology(ta) +
        "<h2>4. Delivery Plan</h2>" + render_delivery(dp) +
        ("<h2>5. Judge Evaluation</h2>" + render_judge(judge) if judge else "") +
        "</div>"
    )


# ---------------------------------------------------------------------------
# Stepper (top of page)
# ---------------------------------------------------------------------------

def render_stepper(has_judge: bool) -> str:
    steps = [
        ("1", "💡", "Business Analyst", "Understanding your needs"),
        ("2", "📐", "Solution Architect", "Designing the architecture"),
        ("3", "🧪", "Technology Advisor", "Selecting the right stack"),
        ("4", "🗓️", "Delivery Planner", "Building the roadmap"),
    ]
    if has_judge:
        steps.append(("5", "🧭", "Quality Judge", "Scoring against requirements"))

    html_parts = []
    for i, (num, icon, title, sub) in enumerate(steps):
        html_parts.append(
            "<div class='step'>"
            f"<div class='step-icon'>{icon}</div>"
            f"<div class='step-num'>{num}</div>"
            f"<div class='step-text'><strong>{esc(title)}</strong><br><span class='muted small'>{esc(sub)}</span></div>"
            "</div>"
        )
        if i < len(steps) - 1:
            html_parts.append("<div class='step-connector'></div>")
    html_parts.append("<div class='step-connector'></div>")
    html_parts.append(
        "<div class='step'><div class='step-icon complete'>&#10003;</div>"
        "<div class='step-text'><strong>Complete</strong><br><span class='muted small'>Your solution blueprint</span></div></div>"
    )
    return "".join(html_parts)


# ---------------------------------------------------------------------------
# Master HTML template
# ---------------------------------------------------------------------------

PAGE_TEMPLATE = Template(r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Solution Blueprint — $BUSINESS_TITLE</title>
<style>
  :root{
    --bg:#f4f6fb; --card:#ffffff; --ink:#1f2430; --muted:#6b7280;
    --border:#e6e9f2; --primary:#3b5bfd; --primary-dark:#101a34;
    --shadow: 0 4px 14px rgba(20,30,60,0.06);
  }
  *{box-sizing:border-box;}
  body{margin:0;font-family:'Segoe UI',Roboto,Tahoma,Geneva,Verdana,sans-serif;background:var(--bg);color:var(--ink);}
  .app{display:flex;min-height:100vh;}
  .sidebar{width:230px;background:var(--primary-dark);color:#cdd6ee;flex-shrink:0;padding:22px 16px;display:flex;flex-direction:column;}
  .sidebar .logo{display:flex;align-items:center;gap:10px;color:#fff;font-weight:700;font-size:17px;margin-bottom:4px;}
  .sidebar .logo-mark{width:32px;height:32px;border-radius:8px;object-fit:contain;flex-shrink:0;}
  .sidebar .tagline{font-size:11px;color:#8891ab;margin-bottom:28px;}
  .sidebar nav a{display:flex;align-items:center;gap:10px;color:#c3cbe4;text-decoration:none;padding:10px 12px;border-radius:8px;font-size:14px;margin-bottom:4px;}
  .sidebar nav a.active{background:#22305a;color:#fff;}
  .sidebar .foot{margin-top:auto;font-size:11px;color:#7d87a3;line-height:1.5;}
  .main{flex:1;padding:28px 36px;max-width:1200px;}
  .topbar{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:18px;flex-wrap:wrap;gap:12px;}
  .topbar h1{margin:0 0 2px 0;font-size:26px;}
  .topbar .subtitle{color:var(--primary);font-weight:600;margin:0 0 6px 0;}
  .topbar p.desc{margin:0;color:var(--muted);}
  .user-chip{display:flex;align-items:center;gap:8px;background:var(--card);border:1px solid var(--border);padding:8px 14px;border-radius:999px;box-shadow:var(--shadow);font-size:14px;white-space:nowrap;}
  .stepper{display:flex;align-items:center;background:var(--card);border-radius:14px;padding:18px 24px;box-shadow:var(--shadow);margin-bottom:22px;flex-wrap:wrap;gap:6px;}
  .step{display:flex;align-items:center;gap:10px;}
  .step-icon{width:36px;height:36px;border-radius:50%;background:#eef1fb;color:var(--primary);display:flex;align-items:center;justify-content:center;font-size:16px;}
  .step-icon.complete{background:#1a9b5c;color:#fff;}
  .step-num{display:none;}
  .step-text{font-size:13px;line-height:1.3;}
  .step-connector{flex:1;min-width:20px;height:2px;background:var(--border);margin:0 6px;}
  .status-banner{display:inline-flex;align-items:center;gap:8px;background:#e6f7ee;color:#1a9b5c;padding:5px 12px;border-radius:999px;font-size:13px;font-weight:600;margin-left:10px;}
  .tabs{display:flex;gap:4px;background:var(--card);border-radius:12px;padding:6px;box-shadow:var(--shadow);margin-bottom:20px;flex-wrap:wrap;}
  .tab-btn{border:none;background:transparent;padding:10px 18px;border-radius:9px;font-size:14px;font-weight:600;color:var(--muted);cursor:pointer;}
  .tab-btn.active{background:var(--primary);color:#fff;}
  .tab-panel{display:none;}
  .tab-panel.active{display:block;animation:fade .15s ease-in;}
  @keyframes fade{from{opacity:0}to{opacity:1}}
  .panel-card{background:var(--card);border-radius:14px;padding:26px;box-shadow:var(--shadow);margin-bottom:22px;}
  .panel-card > h2:first-child, .panel-card > h3:first-child{margin-top:0;}
  .sub-card{border:1px solid var(--border);border-radius:12px;padding:18px 20px;margin-bottom:16px;background:#fbfcfe;}
  .sub-card h3{margin:0 0 10px 0;font-size:15px;color:#26314d;}
  .grid-2{display:grid;grid-template-columns:1fr 1fr;gap:16px;}
  @media(max-width:760px){.grid-2{grid-template-columns:1fr;} .app{flex-direction:column;} .sidebar{width:100%;}}
  .bullet-list{margin:0;padding-left:20px;}
  .bullet-list li{margin-bottom:6px;line-height:1.5;}
  .muted{color:var(--muted);}
  .small{font-size:12px;}
  .data-table{width:100%;border-collapse:collapse;margin-top:6px;font-size:13.5px;}
  .data-table th,.data-table td{border:1px solid var(--border);padding:10px 12px;text-align:left;vertical-align:top;}
  .data-table th{background:#f1f4fb;color:#374362;}
  .pill{display:inline-block;background:#eef1fb;color:#2f4bd6;padding:4px 10px;border-radius:999px;font-size:12.5px;margin:0 6px 6px 0;}
  .pill-row{margin-top:6px;}
  .tradeoff-card{border:1px solid var(--border);border-radius:10px;padding:14px;margin-bottom:12px;background:#fff;}
  .tradeoff-card h4{margin:0 0 8px 0;}
  .ok{color:#1a9b5c;} .bad{color:#d9342c;}
  .raw-fallback pre{white-space:pre-wrap;background:#f6f7fb;border:1px solid var(--border);border-radius:8px;padding:14px;font-size:13px;}
  .accordion-item{border:1px solid var(--border);border-radius:12px;margin-bottom:10px;overflow:hidden;}
  .accordion-trigger{width:100%;display:flex;align-items:center;gap:14px;background:#fff;border:none;padding:16px 18px;cursor:pointer;text-align:left;font:inherit;}
  .accordion-trigger:hover{background:#f7f9ff;}
  .accordion-icon{width:34px;height:34px;border-radius:9px;background:#eef1fb;display:flex;align-items:center;justify-content:center;flex-shrink:0;}
  .accordion-text{flex:1;}
  .chevron{color:var(--muted);font-size:18px;}
  .arch-diagram{overflow-x:auto;padding-top:6px;}
  .diagram-row{display:flex;align-items:center;gap:4px;min-width:max-content;}
  .diagram-box{border:1px solid var(--border);border-radius:10px;background:#fff;padding:16px 20px;font-size:13.5px;font-weight:600;color:#26314d;white-space:nowrap;}
  .diagram-arrow{color:var(--muted);font-size:18px;padding:0 6px;}
  .diagram-cloud{margin-top:16px;border:1px dashed #c9bfff;border-radius:12px;padding:14px 18px;background:#faf8ff;}
  .diagram-cloud-label{font-weight:700;color:#7b3fe4;margin-bottom:10px;font-size:13.5px;}
  .diagram-chip-row{display:flex;gap:8px;flex-wrap:wrap;}
  .diagram-chip{background:#fff;border:1px solid #e3d9ff;color:#5b2fc4;padding:6px 12px;border-radius:8px;font-size:12.5px;}
  .summary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:16px;margin-bottom:22px;}
  .summary-card{background:var(--card);border-radius:14px;padding:18px;box-shadow:var(--shadow);}
  .summary-icon{width:38px;height:38px;border-radius:10px;background:var(--chip);color:var(--chip-fg);display:flex;align-items:center;justify-content:center;font-size:18px;margin-bottom:10px;}
  .summary-card h4{margin:0 0 6px 0;font-size:14px;color:var(--muted);}
  .summary-card p{margin:0;font-size:13.5px;font-weight:500;}
  .badge{display:inline-block;padding:4px 10px;border-radius:999px;font-size:12.5px;font-weight:700;}
  .judge-header{display:flex;gap:24px;align-items:center;flex-wrap:wrap;margin-bottom:18px;}
  .judge-score-ring{width:110px;height:110px;border-radius:50%;flex-shrink:0;
    background:conic-gradient(var(--ring-color) calc(var(--pct)*3.6deg), #eceffa 0deg);
    display:flex;align-items:center;justify-content:center;position:relative;}
  .judge-score-ring::before{content:"";position:absolute;width:82px;height:82px;border-radius:50%;background:#fff;}
  .judge-score-value{position:relative;font-size:26px;font-weight:800;}
  .judge-score-label{position:relative;font-size:11px;color:var(--muted);margin-top:26px;margin-left:-24px;}
  .judge-header-text{flex:1;min-width:220px;}
  .judge-subscores{display:flex;gap:18px;margin-top:8px;font-size:13px;color:var(--muted);flex-wrap:wrap;}
  .domain-card{border:1px solid var(--border);border-radius:12px;margin-bottom:10px;padding:14px 16px;background:#fff;}
  .domain-toggle{width:100%;display:flex;justify-content:space-between;align-items:center;background:none;border:none;cursor:pointer;font:inherit;padding:0;}
  .domain-toggle-main{display:flex;flex-direction:column;text-align:left;}
  .domain-name{font-weight:700;font-size:14px;}
  .domain-weight{font-size:11.5px;color:var(--muted);}
  .domain-toggle-right{display:flex;align-items:center;gap:10px;}
  .domain-score{font-weight:800;font-size:16px;}
  .score-bar{height:6px;background:#eceffa;border-radius:999px;margin:10px 0;overflow:hidden;}
  .score-bar-fill{height:100%;border-radius:999px;}
  .domain-detail{display:none;border-top:1px dashed var(--border);margin-top:10px;padding-top:10px;font-size:13.5px;}
  .domain-detail.open{display:block;}
  .domain-detail h5{margin:10px 0 4px 0;font-size:12.5px;text-transform:uppercase;letter-spacing:.03em;color:var(--muted);}
  .report-view h2{border-bottom:2px solid var(--primary);padding-bottom:8px;margin-top:32px;}
  .empty-state{padding:24px;text-align:center;}
  .footer-note{color:var(--muted);font-size:12px;text-align:center;margin-top:10px;}
  @media print{ .sidebar,.tabs,.stepper{display:none;} .tab-panel{display:block !important;} .main{max-width:100%;} }
</style>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <div class="logo">
    <img src="$LOGO_ICON" class="logo-mark" alt="SolutionForge Logo">
    SolutionForge AI
</div>
    <div class="tagline">From Ideas to Implementable Solutions</div>
    <nav>
      <a href="#" class="active">🏠 Your Solution</a>
    </nav>
    <div class="foot">AI-powered multi-agent consulting for your technology journey.</div>
  </aside>

  <main class="main">
    <div class="topbar">
      <div>
        <h1>SolutionForge AI</h1>
        <p class="subtitle">Your AI Solution Consultant</p>
        <p class="desc">Transform your business idea into a structured, decision-ready solution blueprint.</p>
      </div>
      <div class="user-chip">👤 $GENERATED_LABEL</div>
    </div>

    <div class="stepper">
      $STEPPER_HTML
    </div>

    <div class="tabs">
      <button class="tab-btn active" data-tab="overview" onclick="showTab('overview')">Overview</button>
      <button class="tab-btn" data-tab="business-analysis" onclick="showTab('business-analysis')">Business Analysis</button>
      <button class="tab-btn" data-tab="solution-architecture" onclick="showTab('solution-architecture')">Architecture</button>
      <button class="tab-btn" data-tab="technology-stack" onclick="showTab('technology-stack')">Technology</button>
      <button class="tab-btn" data-tab="delivery-plan" onclick="showTab('delivery-plan')">Delivery Plan</button>
      $JUDGE_TAB_BTN
      <button class="tab-btn" data-tab="report" onclick="showTab('report')">Report</button>
    </div>

    <div id="tab-overview" class="tab-panel active">
      <span class="badge" style="background:#e6f7ee;color:#1a9b5c">● Generated Successfully</span>
      <span class="muted small" style="margin-left:8px">$GENERATED_AT</span>
      <div style="height:14px"></div>
      $OVERVIEW_HTML
    </div>

    <div id="tab-business-analysis" class="tab-panel">
      <div class="panel-card"><h2>Business Analysis</h2>$BUSINESS_ANALYSIS_HTML</div>
    </div>

    <div id="tab-solution-architecture" class="tab-panel">
      <div class="panel-card"><h2>Solution Architecture</h2>$ARCHITECTURE_HTML</div>
    </div>

    <div id="tab-technology-stack" class="tab-panel">
      <div class="panel-card"><h2>Technology Stack</h2>$TECHNOLOGY_HTML</div>
    </div>

    <div id="tab-delivery-plan" class="tab-panel">
      <div class="panel-card"><h2>Delivery Plan</h2>$DELIVERY_HTML</div>
    </div>

    $JUDGE_TAB_PANEL

    <div id="tab-report" class="tab-panel">
      <div class="panel-card">$REPORT_HTML</div>
    </div>

    <p class="footer-note">Generated by SolutionForge AI — CrewAI-powered multi-agent solution consultant.</p>
  </main>
</div>

<script>
function showTab(name){
  document.querySelectorAll('.tab-panel').forEach(function(p){p.classList.remove('active');});
  document.querySelectorAll('.tab-btn').forEach(function(b){b.classList.remove('active');});
  var panel = document.getElementById('tab-' + name);
  if(panel){ panel.classList.add('active'); }
  var btn = document.querySelector('.tab-btn[data-tab="' + name + '"]');
  if(btn){ btn.classList.add('active'); }
  window.scrollTo({top:0, behavior:'smooth'});
}
function goToTab(name){ showTab(name); }
function toggleDomain(id){
  var el = document.getElementById(id);
  var chevron = document.getElementById('chevron-' + id);
  if(!el) return;
  var open = el.classList.toggle('open');
  if(chevron){ chevron.innerHTML = open ? '&#9652;' : '&#9662;'; }
}
</script>
</body>
</html>
""")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def _logo_data_uri() -> str:
    """Return the logo as a base64 data URI so the standalone blueprint.html
    keeps its image when downloaded or served at any URL."""
    logo_path = Path(__file__).resolve().parents[2] / "frontend" / "assets" / "logo_icon.png"
    try:
        return "data:image/png;base64," + base64.b64encode(logo_path.read_bytes()).decode("ascii")
    except OSError:
        return ""


def generate_blueprint_html(
    user_input: dict,
    agent_outputs: dict,
    judge_output: Optional[dict] = None,
) -> str:
    """
    Build the full standalone blueprint.html string.

    Parameters
    ----------
    user_input : the 6 raw fields captured from the user (see
        app/models/user_input.py::UserInput) — business_idea,
        technology_preference, cloud_preference, expected_daily_traffic,
        delivery_timeline_months, data_hosting_country.
    agent_outputs : dict with keys "business_analysis", "solution_architecture",
        "technology_recommendation", "delivery_plan" — each either the
        structured Pydantic dict (see app/models/*.py) or a
        {"raw": "..."} fallback (see backend/services/crew_service.py).
    judge_output : the merged result of app/judge/scoring.py::compute_overall()
        plus the Judge LLM's narrative fields, or None if the Judge has not
        run yet.
    """
    agent_outputs = agent_outputs or {}
    ba = agent_outputs.get("business_analysis")
    sa = agent_outputs.get("solution_architecture")
    ta = agent_outputs.get("technology_recommendation")
    dp = agent_outputs.get("delivery_plan")

    business_title = (user_input or {}).get("business_idea", "Solution Blueprint")
    business_title_short = (business_title[:70] + "…") if len(business_title) > 70 else business_title

    has_judge = bool(judge_output)

    judge_tab_btn = (
        '<button class="tab-btn" data-tab="judge" onclick="showTab(\'judge\')">Judge</button>'
        if has_judge else ""
    )
    judge_tab_panel = (
        '<div id="tab-judge" class="tab-panel"><div class="panel-card">'
        f'<h2>Judge Evaluation</h2>{render_judge(judge_output)}</div></div>'
        if has_judge else ""
    )

    html = PAGE_TEMPLATE.safe_substitute(
        LOGO_ICON=_logo_data_uri(),
        BUSINESS_TITLE=esc(business_title_short),
        GENERATED_LABEL=esc((user_input or {}).get("requested_by", "Generated report")),
        GENERATED_AT=esc(_ist_now().strftime("%b %d, %Y • %I:%M %p IST")),
        STEPPER_HTML=render_stepper(has_judge),
        JUDGE_TAB_BTN=judge_tab_btn,
        JUDGE_TAB_PANEL=judge_tab_panel,
        OVERVIEW_HTML=render_overview(user_input or {}, ba, sa, ta, dp, judge_output),
        BUSINESS_ANALYSIS_HTML=render_business_analysis(ba),
        ARCHITECTURE_HTML=render_architecture(sa),
        TECHNOLOGY_HTML=render_technology(ta),
        DELIVERY_HTML=render_delivery(dp),
        REPORT_HTML=render_report(user_input or {}, ba, sa, ta, dp, judge_output),
    )
    return html
