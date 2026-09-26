"""
views/live_results_view.py
===========================
"Live Results" page — now used exclusively for viewing past/completed
consultations from chat history.

Live streaming of new consultations is handled inline in
consultation_view.py via SSE.
"""

import html

import streamlit as st

import api_client
import config
import styles
from api_client import ApiError
from models import ConsultationResult

# Band -> colour, matching backend/utils/blueprint_generator.py::BAND_COLORS
# so the headline score reads the same here, in the live tab, and in the
# downloaded HTML report.
_BAND_COLORS = {
    "Excellent": "#1a9b5c",
    "Strong": "#2f6bff",
    "Usable": "#d9a300",
    "Weak": "#e06b1f",
    "Critical": "#e0342f",
}

_STATUS_COLORS = {
    "PASS": ("#e6f7ee", "#1a9b5c"),
    "WARN": ("#fff6e0", "#c98a00"),
    "FAIL": ("#fdeaea", "#d9342c"),
    "INFO": ("#eef1f6", "#4b5563"),
}


def _esc(value) -> str:
    """HTML-escape any value so model output can never inject markup."""
    return html.escape(str(value if value is not None else ""))


def _list_html(items, empty_text: str = "None") -> str:
    if not items:
        return f"<em>{_esc(empty_text)}</em>"
    return "".join(
        f"<li style='margin:2px 0;'>{_esc(i)}</li>" for i in items
    )


def render() -> None:
    styles.page_header("Live Results")

    consultation_id = st.session_state.get("viewing_consultation_id") or st.session_state.get("active_consultation_id")
    if not consultation_id:
        st.info("No consultation selected yet. Start a new one from **New Consultation**, "
                 "or open a past one from **Chat History**.")
        return

    # Fetch the full consultation from the backend
    try:
        result_payload = api_client.get_consultation_result(
            token=st.session_state["auth_token"], consultation_id=consultation_id,
        )
    except ApiError as err:
        st.error(str(err))
        return

    result = ConsultationResult.from_dict(result_payload)
    _render_consultation_details_card(result_payload.get("user_input", {}))

    # Check if it's still in progress
    agent_outputs = result_payload.get("agent_outputs", {})
    if not agent_outputs or all(v is None for v in agent_outputs.values()):
        st.warning("This consultation is still processing. Results will appear once agents finish.")
        return

    _render_agent_pipeline_done(agent_outputs, result_payload.get("judge_output"))
    _render_ready_banner(consultation_id, result_payload)
    _render_summary_section(result)
    st.markdown("---")
    _render_judge_section(result)
    st.markdown("---")
    _render_full_blueprint(result)


def _render_consultation_details_card(summary: dict) -> None:
    if not summary:
        return
    st.markdown('<div class="sf-card">', unsafe_allow_html=True)
    st.markdown('<div class="sf-card-title">📋 Consultation Details</div>', unsafe_allow_html=True)
    idea = summary.get("business_idea", "")
    idea_preview = (idea[:80] + "…") if len(idea) > 80 else idea
    st.markdown(
        f"**Business Idea:** {idea_preview}  \n"
        f"**Scale:** ~{summary.get('expected_daily_traffic', 0):,} Daily Active Users  \n"
        f"**Constraints:** {summary.get('delivery_timeline_months', '?')}-month MVP, "
        f"{summary.get('cloud_preference', '')} · {summary.get('data_hosting_country', '')}"
    )
    st.markdown("</div>", unsafe_allow_html=True)


def _render_agent_pipeline_done(agent_outputs: dict, judge_output=None) -> None:
    """Show all 5 pipeline pills as done (for a completed consultation).

    The first four are read from `agent_outputs`; the Judge lives in its own
    `judge_output` field on the consultation, because the backend computes its
    score in Python rather than storing it as an agent output.
    """
    has_judge = bool(judge_output) and not (
        isinstance(judge_output, dict) and set(judge_output.keys()) <= {"raw"}
    )

    cols = st.columns(len(config.AGENT_PIPELINE))
    for idx, (col, agent) in enumerate(zip(cols, config.AGENT_PIPELINE), start=1):
        key = agent["key"]
        if key == "judge":
            has_output = has_judge
        else:
            has_output = agent_outputs.get(key) is not None
        status = "done" if has_output else "pending"
        css_class = styles.agent_status_class(status)
        sub_label = "Done ✔" if has_output else "Waiting"
        with col:
            st.markdown(
                f"""<div class="sf-agent-pill {css_class}">
                        {idx}. {agent['label']}
                        <span class="sf-agent-sub">{sub_label}</span>
                    </div>""",
                unsafe_allow_html=True,
            )
    st.write("")


def _render_ready_banner(consultation_id: str, result_payload: dict) -> None:
    col_msg, col_btn = st.columns([3, 1.4])
    with col_msg:
        st.success("Your comprehensive solution blueprint is ready for delivery planning.")
    with col_btn:
        try:
            html_report = api_client.export_blueprint_html(
                token=st.session_state["auth_token"], consultation_id=consultation_id,
            )
            st.download_button(
                "⬇️ Download HTML Blueprint Report",
                data=html_report,
                file_name="blueprint.html",
                mime="text/html",
                use_container_width=True,
            )
        except ApiError as err:
            st.warning(f"Report download unavailable: {err}")


def _render_summary_section(result: ConsultationResult) -> None:
    """
    A short, scannable summary shown right below the ready banner — pulls the
    single most important fact out of each of the four agent outputs so the
    user gets the gist before scrolling into the full blueprint.
    """
    st.markdown("### Summary")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Architecture Style", result.solution_architecture.architecture_style or "—")
    with c2:
        tech_count = len(result.technology_recommendation.technologies)
        st.metric("Technologies Selected", tech_count)
    with c3:
        # Backend sends `team` as plain role-name strings (no count), so the
        # team size = number of distinct roles if no counts are present.
        roles = result.delivery_plan.team_roles
        counted = sum(
            int(role.get("count", 0)) if isinstance(role, dict) and role.get("count") else 0
            for role in roles
        )
        team_size = counted if counted else len([r for r in roles if r])
        st.metric("Recommended Team Size", team_size)
    with c4:
        # Backend sends `timeline` as strings like "Month 1-2: ...". Derive the
        # total duration from the month ranges when no dicts are available.
        timeline = result.delivery_plan.timeline
        total_weeks = sum(
            int(phase.get("duration_weeks", 0))
            if isinstance(phase, dict) and phase.get("duration_weeks")
            else 0
            for phase in timeline
        )
        if not total_weeks:
            total_weeks = _months_to_weeks(timeline)
        st.metric("Estimated Duration", f"{total_weeks} weeks")
    with c5:
        # Headline number from the Judge (5th pipeline step). Shown as "—"
        # for consultations completed before the Judge was integrated.
        judge = result.judge_output
        st.metric(
            "Judge Score",
            "—" if judge is None or judge.overall_score is None
            else f"{judge.overall_score:g}/100",
        )

    if result.business_analysis.problem_statement:
        st.markdown(f"**Problem Statement:** {result.business_analysis.problem_statement}")


def _months_to_weeks(timeline: list) -> int:
    """Convert month-range strings (e.g. 'Month 1-2: ...') into total weeks."""
    total_months = 0
    for item in timeline:
        if isinstance(item, dict):
            continue
        import re
        m = re.search(r"Month\s+(\d+)(?:\s*[-–]\s*(\d+))?", str(item))
        if not m:
            continue
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        total_months += max(end - start + 1, 1)
    return total_months * 4


def _render_judge_section(result: ConsultationResult) -> None:
    """
    The Judge verdict (5th pipeline step) as stored in `judge_output`.

    Note this is deliberately read from `result.judge_output`, not from
    `agent_outputs["judge"]` — the backend keeps the deterministic score in its
    own field on the consultation document.
    """
    judge = result.judge_output
    if judge is None:
        st.info("No Judge evaluation was recorded for this consultation. "
                "Consultations completed before the Judge was integrated do not "
                "have one.")
        return

    st.markdown("### ⚖️ Judge Verdict")

    if judge.criteria_missing:
        st.warning(
            f"The judging model did not score {len(judge.criteria_missing)} of "
            "the rubric criteria, so those contribute zero to the total: "
            + ", ".join(judge.criteria_missing)
        )

    # --- Headline score -----------------------------------------------------
    band = judge.quality_band or "—"
    color = _BAND_COLORS.get(band, "#2f6bff")
    score_text = "—" if judge.overall_score is None else f"{judge.overall_score:g}"
    raw = judge.raw_weighted_score
    penalty = judge.constraint_penalty or 0

    st.markdown(
        f"<div style='border:1px solid var(--sf-border); border-radius:10px; "
        f"padding:1rem 1.2rem; margin-bottom:0.9rem;'>"
        f"<div style='display:flex; align-items:center; gap:1.4rem; flex-wrap:wrap;'>"
        f"<div style='font-size:2.4rem; font-weight:800; color:{color}; line-height:1;'>"
        f"{_esc(score_text)}"
        f"<span style='font-size:0.95rem; font-weight:600; color:var(--sf-text-muted);'>/100</span></div>"
        f"<div style='flex:1; min-width:230px;'>"
        f"<div style='font-weight:700; color:{color};'>{_esc(band)}</div>"
        f"<div style='font-size:0.82rem; color:var(--sf-text-muted);'>{_esc(judge.quality_band_description)}</div>"
        f"<div style='font-size:0.79rem; color:var(--sf-text-muted); margin-top:5px;'>"
        f"Weighted criteria {_esc(raw if raw is not None else '—')}"
        f" &minus; constraint deductions {_esc(penalty)}"
        + (f" &middot; <strong>{judge.failed_count} failed</strong>" if judge.failed_count else "")
        + (f" &middot; <strong>{judge.warned_count} warned</strong>" if judge.warned_count else "")
        + "</div></div></div></div>",
        unsafe_allow_html=True,
    )

    if judge.judge_summary:
        st.markdown(f"**Summary:** {judge.judge_summary}")

    # --- Per-criterion scores ----------------------------------------------
    if judge.criteria:
        with st.expander("Evaluation domains (per-criterion scores & evidence)"):
            for crit in judge.criteria:
                score = crit.score or 0
                bar_color = (
                    "#1a9b5c" if score >= 75
                    else "#d9a300" if score >= 50
                    else "#d9342c"
                )
                st.markdown(
                    f"**{crit.name}** — {score}/100 "
                    f"(weight {crit.weight:g}%)"
                )
                st.markdown(
                    f"<div style='height:6px; background:#eceffa; border-radius:999px; "
                    f"overflow:hidden; margin:4px 0 8px 0;'>"
                    f"<div style='height:100%; width:{max(0, min(100, score))}%; "
                    f"background:{bar_color}; border-radius:999px;'></div></div>",
                    unsafe_allow_html=True,
                )
                if crit.assessment:
                    st.caption(crit.assessment)
                if crit.evidence:
                    st.markdown(f"<ul style='margin:0 0 4px 0;'>{_list_html(crit.evidence)}</ul>",
                                unsafe_allow_html=True)
                if crit.improvements:
                    st.markdown(
                        f"<div style='font-size:0.83rem; color:var(--sf-text-muted);'>"
                        f"<strong>Improvements:</strong> {_esc('; '.join(crit.improvements))}</div>",
                        unsafe_allow_html=True,
                    )
    else:
        st.info("The Judge returned no per-criterion evaluation.")

    # --- Deterministic constraint checks -----------------------------------
    if judge.hard_constraint_checks:
        st.markdown("**Hard constraint checks** (deterministic, computed in Python)")
        rows = ""
        for chk in judge.hard_constraint_checks:
            bg, fg = _STATUS_COLORS.get(chk.status, ("#eef1f6", "#4b5563"))
            detail = _esc(chk.evidence)
            if chk.recommendation:
                detail += (f"<div style='margin-top:3px; color:var(--sf-text-muted);'>"
                           f"<strong>Fix:</strong> {_esc(chk.recommendation)}</div>")
            rows += (
                "<tr>"
                f"<td style='padding:5px 8px; vertical-align:top;'>{_esc(chk.constraint)}</td>"
                f"<td style='padding:5px 8px;'><span style='display:inline-block; "
                f"padding:2px 9px; border-radius:999px; font-size:0.75rem; "
                f"font-weight:700; background:{bg}; color:{fg};'>{_esc(chk.status)}</span></td>"
                f"<td style='padding:5px 8px; color:var(--sf-text-muted); "
                f"font-size:0.8rem;'>{_esc(chk.severity)}</td>"
                f"<td style='padding:5px 8px; font-size:0.83rem;'>{detail}</td>"
                "</tr>"
            )
        st.markdown(
            "<table style='width:100%; border-collapse:collapse; font-size:0.85rem;'>"
            "<tr style='border-bottom:1px solid var(--sf-border);'>"
            "<th style='padding:5px 8px; text-align:left;'>Constraint</th>"
            "<th style='padding:5px 8px; text-align:left;'>Status</th>"
            "<th style='padding:5px 8px; text-align:left;'>Severity</th>"
            "<th style='padding:5px 8px; text-align:left;'>Evidence &amp; Fix</th>"
            f"</tr>{rows}</table>",
            unsafe_allow_html=True,
        )
    else:
        st.info("No hard-constraint checks were recorded.")

    # --- Narrative ----------------------------------------------------------
    n1, n2 = st.columns(2)
    with n1:
        st.markdown("**Strengths**")
        st.markdown(f"<ul>{_list_html(judge.strengths)}</ul>", unsafe_allow_html=True)
        st.markdown("**Critical issues**")
        st.markdown(
            f"<ul>{_list_html(judge.critical_issues, 'None identified.')}</ul>",
            unsafe_allow_html=True,
        )
    with n2:
        st.markdown("**Weaknesses**")
        st.markdown(f"<ul>{_list_html(judge.weaknesses)}</ul>", unsafe_allow_html=True)
        st.markdown("**Recommended improvements**")
        st.markdown(
            f"<ul>{_list_html(judge.recommended_improvements, 'None suggested.')}</ul>",
            unsafe_allow_html=True,
        )

    if judge.cross_agent_consistency:
        st.markdown(f"**Cross-agent consistency:** {judge.cross_agent_consistency}")


def _render_full_blueprint(result: ConsultationResult) -> None:
    col1, col2, col3 = st.columns(3)

    with col1:
        _render_delivery_overview(result)
        _render_recommended_stack(result)
        _render_implementation_workstreams(result)

    with col2:
        _render_technology_detail(result)
        _render_team_roles(result)

    with col3:
        _render_timeline_milestones(result)
        _render_risks(result)
        _render_future_evolution(result)


def _render_delivery_overview(result: ConsultationResult) -> None:
    st.markdown("**Delivery Overview**")
    dp = result.delivery_plan
    if dp.deployment_strategy:
        st.caption(dp.deployment_strategy)
    if dp.timeline:
        rows = ""
        for p in dp.timeline:
            if isinstance(p, dict):
                rows += f"<tr><td>{p.get('phase','')}</td><td>{p.get('duration_weeks','')} wks</td></tr>"
            else:
                rows += f"<tr><td colspan='2'>{p}</td></tr>"
        st.markdown(
            f"""<table style="width:100%; font-size:0.9rem;">
                    <tr><th align="left">Phase</th><th align="left">Duration</th></tr>
                    {rows}
                </table>""",
            unsafe_allow_html=True,
        )
    else:
        st.caption("No delivery phases returned yet.")


def _render_recommended_stack(result: ConsultationResult) -> None:
    st.markdown("**Recommended Technology Stack**")
    technologies = result.technology_recommendation.technologies
    if not technologies:
        st.caption("No technology recommendations yet.")
        return
    for tech in technologies:
        if isinstance(tech, dict):
            st.markdown(f"- **{tech.get('technology','')}** ({tech.get('category','')})")
        else:
            st.markdown(f"- {tech}")


def _render_implementation_workstreams(result: ConsultationResult) -> None:
    st.markdown("**Implementation Workstreams**")
    workstreams = result.delivery_plan.workstreams
    if not workstreams:
        st.caption("No workstreams returned yet.")
        return
    for ws in workstreams:
        if isinstance(ws, dict):
            tasks = ", ".join(ws.get("tasks", []))
            st.markdown(f"- **{ws.get('name','')}**: {tasks}")
        else:
            st.markdown(f"- {ws}")


def _render_technology_detail(result: ConsultationResult) -> None:
    st.markdown("**Technology Rationale**")
    for tech in result.technology_recommendation.technologies:
        if isinstance(tech, dict):
            with st.expander(f"{tech.get('technology','')} — {tech.get('category','')}"):
                st.write(tech.get("reason", "No rationale provided."))
        else:
            st.markdown(f"- {tech}")

    cloud = result.technology_recommendation.cloud
    if cloud:
        st.markdown(f"**Cloud:** {cloud.get('provider','')} — {', '.join(cloud.get('services', []))}")


def _render_team_roles(result: ConsultationResult) -> None:
    st.markdown("**Team Roles**")
    roles = result.delivery_plan.team_roles
    if not roles:
        st.caption("No team roles returned yet.")
        return
    for role in roles:
        if isinstance(role, dict):
            st.markdown(f"- {role.get('count','?')} x {role.get('role','')}")
        else:
            st.markdown(f"- {role}")


def _render_timeline_milestones(result: ConsultationResult) -> None:
    st.markdown("**Delivery Timeline & Milestones**")
    milestones = result.delivery_plan.milestones
    if not milestones:
        st.caption("No milestones returned yet.")
        return
    for m in milestones:
        st.markdown(f"- {m}")


def _render_risks(result: ConsultationResult) -> None:
    st.markdown("**Delivery Risks & Mitigations**")
    risks = result.delivery_plan.risks
    if not risks:
        st.caption("No risks returned yet.")
        return
    for r in risks:
        if isinstance(r, dict):
            st.markdown(f"- **{r.get('risk','')}** ({r.get('impact','')}) — _{r.get('mitigation','')}_")
        else:
            st.markdown(f"- {r}")


def _render_future_evolution(result: ConsultationResult) -> None:
    st.markdown("**Future Evolution**")
    items = result.delivery_plan.future_evolution
    if not items:
        st.caption("No future roadmap items returned yet.")
        return
    for item in items:
        st.markdown(f"- {item}")
