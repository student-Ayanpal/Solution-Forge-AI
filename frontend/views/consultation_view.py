"""
views/consultation_view.py
===========================
"New Consultation" page — matches the mockup: business idea textarea,
technology preference, cloud preference, expected daily traffic, delivery
timeline slider, country search-select, and a "Generate Solution Blueprint"
submit button.

On submit, the page opens an SSE stream to POST /consultations and renders
agent outputs live as each agent finishes — no page navigation needed.
"""

import html

import streamlit as st
import api_client
import config
import session_state as ss
import styles
from api_client import ApiError
from models import UserInput
from validators import consultation_errors, validate_consultation_form


# Map backend agent keys to human-readable labels
AGENT_LABELS = {
    "business_analysis": "Business Analyst",
    "solution_architecture": "Solution Architect",
    "technology_recommendation": "Technology Advisor",
    "delivery_plan": "Delivery Planner",
    "judge": "Judge",
}

# The pipeline the backend actually runs. "judge" is last because the Judge
# consumes all four upstream outputs; the backend streams it as a 5th
# `agent_finished` event once the deterministic score has been computed.
AGENT_ORDER = [
    "business_analysis",
    "solution_architecture",
    "technology_recommendation",
    "delivery_plan",
    "judge",
]

# Tab labels, in the same order as AGENT_ORDER.
AGENT_TABS = [
    "Business Analyst",
    "Solution Architect",
    "Technology Advisor",
    "Delivery Planner",
    "Judge",
]


def render() -> None:
    if "consult_submitted" not in st.session_state:
        st.session_state.consult_submitted = False

    if st.session_state.consult_submitted:
        # Already submitted — show header + results directly.
        # IMPORTANT: if the stream already finished, re-render the SAVED
        # results instead of POSTing a brand-new consultation on every
        # Streamlit rerun (this was creating duplicate consultations).
        col_title, col_btn = st.columns([5, 1])
        with col_title:
            styles.page_header("Live Blueprint")
        with col_btn:
            if st.button("← Back", key="new_consult_btn", use_container_width=True):
                st.session_state.consult_submitted = False
                st.session_state.pop("consult_results", None)
                st.session_state.pop("active_consultation_id", None)
                st.rerun()
        if st.session_state.get("consult_results"):
            _render_saved_results()
        else:
            _submit(**st.session_state.consult_form_data)
        return

    # --- First visit or after clicking Back: show the form ---
    styles.page_header("New Consultation")

    form_container = st.empty()
    with form_container.container():
        notice = st.session_state.pop("form_notice", None)
        if notice:
            st.error(notice)

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown('<div class="sf-section-label">Business Context</div>', unsafe_allow_html=True)
            business_idea = st.text_area(
                "Business Idea / Problem Statement",
                key="consult_business_idea",
                placeholder="Healthcare Patient Platform",
                height=160,
            )
            technology_preference = st.selectbox(
                "Technology Preference",
                options=config.TECHNOLOGY_PREFERENCE_OPTIONS,
                key="consult_tech_preference",
            )
            delivery_timeline_months = st.slider(
                "Delivery Timeline (Months)",
                min_value=0, max_value=10, value=0, step=1,
                key="consult_timeline",
                help="Starting at 0 — slide up to the number of months for delivery.",
            )

        with col_right:
            st.markdown('<div class="sf-section-label">Delivery Constraints</div>', unsafe_allow_html=True)
            cloud_preference = st.selectbox(
                "Cloud Preference",
                options=config.CLOUD_PREFERENCE_OPTIONS,
                key="consult_cloud_preference",
            )
            expected_daily_traffic = st.number_input(
                "Expected Daily Traffic",
                min_value=0, step=100, value=0, key="consult_daily_traffic",
                help="Approximate number of daily active users / requests. Starts at 0 — add it to unlock the button.",
            )
            data_hosting_country = st.selectbox(
                "Country",
                options=[""] + config.COUNTRY_OPTIONS,
                key="consult_country",
                format_func=lambda c: "Search a country..." if c == "" else c,
            )
        st.write("")
        is_valid = bool(
            business_idea.strip()
            and data_hosting_country
            and expected_daily_traffic > 0
            and delivery_timeline_months > 0
        )
        submit = st.button("🚀  Generate Solution Blueprint", key="consult_submit",
                     type="primary", use_container_width=True,
                     disabled=not is_valid)

    if submit:
        form_container.empty()
        st.session_state.consult_submitted = True
        st.session_state.consult_form_data = {
            "business_idea": business_idea,
            "technology_preference": technology_preference,
            "cloud_preference": cloud_preference,
            "expected_daily_traffic": expected_daily_traffic,
            "delivery_timeline_months": delivery_timeline_months,
            "data_hosting_country": data_hosting_country,
        }
        _submit(**st.session_state.consult_form_data)


def _submit(business_idea, technology_preference, cloud_preference,
            expected_daily_traffic, delivery_timeline_months, data_hosting_country) -> None:
    is_valid, error = validate_consultation_form(
        business_idea=business_idea,
        expected_daily_traffic=expected_daily_traffic,
        delivery_timeline_months=delivery_timeline_months,
        data_hosting_country=data_hosting_country,
    )
    if not is_valid:
        st.error(error)
        return

    user_input = UserInput(
        business_idea=business_idea.strip(),
        technology_preference=technology_preference,
        cloud_preference=cloud_preference,
        expected_daily_traffic=int(expected_daily_traffic),
        delivery_timeline_months=int(delivery_timeline_months),
        data_hosting_country=data_hosting_country,
    )

    # --- Agent pipeline status pills (updated live) ---
    pipeline_placeholder = st.empty()
    # --- Status message ---
    status_placeholder = st.empty()
    # --- Agent output appears below in horizontal tabs ---
    tabs = st.tabs(AGENT_TABS)
    
    # Create an empty placeholder inside each tab so we can update them live
    tab_placeholders = {
        key: tabs[idx].empty()
        for idx, key in enumerate(AGENT_ORDER)
    }

    # Track which agents are done, in_progress, or pending
    agent_statuses = {key: "pending" for key in AGENT_ORDER}
    agent_results = {}

    def _render_pipeline():
        """Redraw the 5 agent status pills into the placeholder."""
        cols = pipeline_placeholder.columns(len(AGENT_ORDER))
        for idx, (col, key) in enumerate(zip(cols, AGENT_ORDER), start=1):
            status = agent_statuses[key]
            label = AGENT_LABELS[key]
            css_class = styles.agent_status_class(status)
            sub_label = {
                "done": "Done ✔",
                "in_progress": "Working now…",
                "pending": "Waiting",
                "error": "Error",
            }.get(status, "Waiting")
            with col:
                st.markdown(
                    f"""<div class="sf-agent-pill {css_class}">
                            {idx}. {label}
                            <span class="sf-agent-sub">{sub_label}</span>
                        </div>""",
                    unsafe_allow_html=True,
                )

    # Initial render — first agent starts immediately
    agent_statuses[AGENT_ORDER[0]] = "in_progress"
    _render_pipeline()
    status_placeholder.info("🚀 Starting your AI consulting team… **Business Analyst** is working…")

    try:
        stream = api_client.stream_consultation(
            token=st.session_state["auth_token"],
            user_input=user_input.to_dict(),
        )

        for event in stream:
            event_type = event.get("event")

            if event_type == "agent_finished":
                agent_key = event.get("agent", "")
                agent_data = event.get("data", {})

                if agent_key not in AGENT_ORDER:
                    # The backend added a pipeline step this build doesn't know
                    # about. Say so instead of crashing on a missing tab.
                    status_placeholder.warning(
                        f"Received output for an unrecognised step "
                        f"'{agent_key}' — it will not be displayed."
                    )
                    continue

                # Mark this agent done
                agent_statuses[agent_key] = "done"
                agent_results[agent_key] = agent_data

                # Mark the NEXT agent as in_progress (if any)
                current_idx = AGENT_ORDER.index(agent_key)
                if current_idx + 1 < len(AGENT_ORDER):
                    agent_statuses[AGENT_ORDER[current_idx + 1]] = "in_progress"

                # Re-render the pipeline pills
                _render_pipeline()

                done_count = sum(1 for s in agent_statuses.values() if s == "done")
                status_placeholder.info(
                    f"✅ **{AGENT_LABELS.get(agent_key, agent_key)}** finished. "
                    f"({done_count}/{len(AGENT_ORDER)} steps done)"
                )

                # Render this agent in its respective tab
                with tab_placeholders[agent_key].container():
                    _render_agent_output(agent_key, agent_results[agent_key])

            elif event_type == "complete":
                # All done
                _render_pipeline()
                status_placeholder.success(
                    "🎉 **All agents and the Judge finished!** Your solution "
                    "blueprint is ready. Click the tabs above to view details."
                )

                # Store the consultation id so the blueprint can be downloaded
                consultation_id = event.get("consultation_id") or st.session_state.get("active_consultation_id")
                if consultation_id:
                    st.session_state["active_consultation_id"] = consultation_id

                # Persist the finished results so later Streamlit reruns re-render
                # these instead of POSTing a duplicate consultation.
                st.session_state["consult_results"] = {
                    "agent_results": agent_results,
                    "agent_statuses": dict(agent_statuses),
                    "status_label": "completed",
                }

                st.markdown("")
                if consultation_id:
                    try:
                        html_report = api_client.export_blueprint_html(
                            token=st.session_state["auth_token"],
                            consultation_id=consultation_id,
                        )
                        st.download_button(
                            "📥 Download Blueprint (HTML)",
                            data=html_report,
                            file_name="blueprint.html",
                            mime="text/html",
                            type="primary",
                        )
                    except ApiError as dlerr:
                        st.warning(f"Blueprint ready, but download failed: {dlerr}")

            elif event_type == "error":
                status_placeholder.error(
                    f"❌ Pipeline error: {event.get('message', 'Unknown error')}"
                )
                return

    except ApiError as err:
        if getattr(err, "status_code", 0) == 422:
            # Backend rejected the input (e.g. prompt injection). Go back to
            # the New Consultation form and show WHY it was stopped.
            _reset_to_form(f"⛔ {err}")
        else:
            status_placeholder.error(str(err))


def _reset_to_form(message: str) -> None:
    """Return to the New Consultation form and show a clear notice."""
    st.session_state["form_notice"] = message
    st.session_state["consult_submitted"] = False
    st.session_state.pop("consult_results", None)
    st.session_state.pop("active_consultation_id", None)
    st.session_state.pop("consult_form_data", None)
    for key in ("consult_business_idea", "consult_tech_preference",
                "consult_cloud_preference", "consult_timeline",
                "consult_daily_traffic", "consult_country"):
        st.session_state.pop(key, None)
    st.rerun()


def _render_agent_output(agent_key: str, data: dict, expanded: bool = True) -> None:
    """Route the rendering to specialized components based on the agent type."""
    if not data or (len(data) == 1 and "raw" in data):
        st.markdown(data.get("raw", "_No structured output._"))
        return

    if agent_key == "business_analysis":
        _render_business_analysis(data)
    elif agent_key == "solution_architecture":
        _render_solution_architecture(data)
    elif agent_key == "technology_recommendation":
        _render_technology_recommendation(data)
    elif agent_key == "delivery_plan":
        _render_delivery_plan(data)
    elif agent_key == "judge":
        _render_judge(data)
    else:
        # Fallback for unknown agent keys
        for k, v in data.items():
            st.write(f"**{k}**: {v}")


def _esc(value) -> str:
    """HTML-escape any dynamic value before it goes into unsafe HTML."""
    return html.escape("" if value is None else str(value), quote=True)


def _card(title: str, body_html: str) -> None:
    """Render a compact branded card with a title and HTML body."""
    st.markdown(
        f"""<div class="sf-card" style="padding:1rem 1.2rem; margin-bottom:0.7rem;">
            <div class="sf-card-title" style="margin-bottom:0.5rem; font-size:0.88rem;">{_esc(title)}</div>
            <div style="font-size:0.84rem; line-height:1.5; color:var(--sf-text);">{body_html}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def _list_to_html(items: list, compact: bool = True, empty_text: str = "None") -> str:
    """Convert a list of strings or dicts into compact (escaped) HTML."""
    if not items:
        return f"<em>{_esc(empty_text)}</em>"
    parts = []
    for item in items:
        if isinstance(item, dict):
            inner = " · ".join(
                f"<strong>{_esc(k.replace('_', ' ').title())}:</strong> {_esc(v)}"
                for k, v in item.items()
            )
            parts.append(f"<li style='margin-bottom:2px;'>{inner}</li>")
        else:
            parts.append(f"<li style='margin-bottom:2px;'>{_esc(item)}</li>")
    pad = "margin:0; padding-left:1.2rem;" if compact else "padding-left:1.2rem;"
    return f"<ul style='{pad}'>{''.join(parts)}</ul>"


def _render_generic_remaining(data: dict, handled_keys: set) -> None:
    """Render any fields that weren't explicitly formatted above as cards."""
    remaining = {k: v for k, v in data.items() if k not in handled_keys and v}
    if not remaining:
        return
    cards_html = []
    for key, value in remaining.items():
        title = key.replace("_", " ").title()
        if isinstance(value, list):
            body = _list_to_html(value)
        elif isinstance(value, dict):
            body = _list_to_html([f"<strong>{_esc(k.replace('_', ' ').title())}:</strong> {_esc(v)}" for k, v in value.items()])
        else:
            body = _esc(value)
        cards_html.append((title, body))

    # Render in 2-column rows
    for i in range(0, len(cards_html), 2):
        cols = st.columns(2)
        for j, col in enumerate(cols):
            if i + j < len(cards_html):
                with col:
                    _card(cards_html[i + j][0], cards_html[i + j][1])


def _render_business_analysis(data: dict) -> None:
    handled = {"problem_statement", "users", "mvp_scope", "risks"}

    problem = data.get("problem_statement", "")
    if problem:
        _card("📋 Problem Statement", f"<p style='margin:0;'>{_esc(problem)}</p>")

    c1, c2, c3 = st.columns(3)
    with c1:
        _card("👥 Users", _list_to_html(data.get("users", [])))
    with c2:
        _card("🎯 MVP Scope", _list_to_html(data.get("mvp_scope", [])))
    with c3:
        _card("⚠️ Risks", _list_to_html(data.get("risks", [])))

    _render_generic_remaining(data, handled)


def _generate_mermaid_code(components: list, connections: list) -> str:
    if not components:
        return ""
    
    init_str = """%%{
  init: {
    'theme': 'base',
    'themeVariables': {
      'primaryColor': '#ffffff',
      'primaryBorderColor': '#1d5fb8',
      'primaryTextColor': '#0f2a4d',
      'textColor': '#0f2a4d',
      'nodeTextColor': '#0f2a4d',
      'lineColor': '#1d5fb8',
      'secondaryColor': '#f3f5f9',
      'tertiaryColor': '#eaf1fd',
      'edgeLabelBackground': '#ffffff'
    }
  }
}%%"""

    # Explicit defaults take precedence over Streamlit's Mermaid theme, whose
    # dark node fill otherwise makes the navy labels difficult to read.
    lines = [
        init_str,
        "flowchart TD",
        "    classDef default fill:#ffffff,stroke:#1d5fb8,color:#0f2a4d,stroke-width:1px;",
    ]
    for comp in components:
        if isinstance(comp, dict):
            cid = comp.get("id", "").replace(" ", "_").replace("-", "_")
            cname = comp.get("name", "")
            lines.append(f"    {cid}[\"{cname}\"]")
    for conn in connections:
        if isinstance(conn, dict):
            src = conn.get("source", "").replace(" ", "_").replace("-", "_")
            tgt = conn.get("target", "").replace(" ", "_").replace("-", "_")
            lbl = conn.get("label", "")
            if lbl:
                lines.append(f"    {src} -->|{lbl}| {tgt}")
            else:
                lines.append(f"    {src} --> {tgt}")
    return "\n".join(lines)


def _render_solution_architecture(data: dict) -> None:
    handled = {"architecture_style", "components", "connections", "data_flow"}

    style = data.get("architecture_style", "")
    if style:
        _card("🏗️ Architecture Style",
              f"<div style='font-size:0.95rem; font-weight:700; color:var(--sf-navy); "
              f"background:var(--sf-blue-light); border:1px solid var(--sf-border); "
              f"border-radius:10px; padding:0.7rem 1rem; display:inline-block;'>{_esc(style)}</div>")

    comps = data.get("components", [])
    conns = data.get("connections", [])
    
    if comps and conns:
        st.markdown('<div class="sf-section-label" style="margin-top: 1rem;">Architecture Diagram</div>', unsafe_allow_html=True)
        mermaid_code = _generate_mermaid_code(comps, conns)
        st.markdown(f"```mermaid\n{mermaid_code}\n```")
        st.write("")

    c1, c2 = st.columns(2)
    comps = data.get("components", [])
    comp_html = ""
    for comp in comps:
        if isinstance(comp, dict):
            comp_html += f"<li style='margin-bottom:3px;'><strong>{_esc(comp.get('name', ''))}</strong>: {_esc(comp.get('description', ''))}</li>"
        else:
            comp_html += f"<li style='margin-bottom:3px;'>{_esc(comp)}</li>"
    with c1:
        _card("🧩 Components", f"<ul style='margin:0; padding-left:1.2rem;'>{comp_html}</ul>")

    flows = data.get("data_flow", [])
    if flows:
        flow_html = ""
        for i, flow in enumerate(flows, 1):
            flow_html += f"<li style='margin-bottom:3px;'>{_esc(flow)}</li>"
        with c2:
            _card("🔄 Data Flow", f"<ol style='margin:0; padding-left:1.2rem;'>{flow_html}</ol>")

    _render_generic_remaining(data, handled)


def _render_technology_recommendation(data: dict) -> None:
    handled = {"cloud", "technologies"}

    cloud = data.get("cloud", {})
    if isinstance(cloud, dict) and cloud:
        services = ", ".join(_esc(s) if s is not None else "" for s in cloud.get("services", []))
        _card("☁️ Cloud Provider",
              f"<strong>{_esc(cloud.get('provider', 'N/A'))}</strong>"
              f"<br><small style='color:var(--sf-text-muted);'>Services: {services}</small>")

    techs = data.get("technologies", [])
    if techs:
        rows = ""
        for tech in techs:
            if isinstance(tech, dict):
                rows += (f"<tr><td style='padding:4px 8px;'><strong>{_esc(tech.get('category', ''))}</strong></td>"
                         f"<td style='padding:4px 8px;'>{_esc(tech.get('technology', ''))}</td>"
                         f"<td style='padding:4px 8px; color:var(--sf-text-muted); font-size:0.8rem;'>{_esc(tech.get('reason', ''))}</td></tr>")
            else:
                rows += f"<tr><td style='padding:4px 8px;' colspan='3'>{_esc(tech)}</td></tr>"
        table = (f"<table style='width:100%; border-collapse:collapse; font-size:0.84rem;'>"
                 f"<tr style='border-bottom:1px solid var(--sf-border);'>"
                 f"<th style='padding:4px 8px; text-align:left;'>Category</th>"
                 f"<th style='padding:4px 8px; text-align:left;'>Technology</th>"
                 f"<th style='padding:4px 8px; text-align:left;'>Reason</th></tr>{rows}</table>")
        _card("🛠️ Recommended Stack", table)

    _render_generic_remaining(data, handled)


def _render_delivery_plan(data: dict) -> None:
    handled = {"timeline", "team_roles"}

    c1, c2 = st.columns([2, 1])

    timeline = data.get("timeline", [])
    if timeline:
        rows = ""
        for p in timeline:
            if isinstance(p, dict):
                rows += (f"<tr><td style='padding:4px 8px;'>{_esc(p.get('phase',''))}</td>"
                         f"<td style='padding:4px 8px;'>{_esc(p.get('duration_weeks',''))} wks</td></tr>")
            else:
                rows += f"<tr><td style='padding:4px 8px;' colspan='2'>{_esc(p)}</td></tr>"
        table = (f"<table style='width:100%; border-collapse:collapse; font-size:0.84rem;'>"
                 f"<tr style='border-bottom:1px solid var(--sf-border);'>"
                 f"<th style='padding:4px 8px; text-align:left;'>Phase</th>"
                 f"<th style='padding:4px 8px; text-align:left;'>Duration</th></tr>{rows}</table>")
        with c1:
            _card("📅 Timeline", table)

    roles = data.get("team_roles") or data.get("team", [])
    role_items = []
    for role in roles:
        if isinstance(role, dict):
            role_items.append(f"{_esc(role.get('count', '?'))}× {_esc(role.get('role', ''))}")
        else:
            role_items.append(_esc(str(role)))
    with c2:
        _card("👥 Team Roles", _list_to_html(role_items))

    _render_generic_remaining(data, handled)


# ---------------------------------------------------------------------------
# Judge (step 5)
# ---------------------------------------------------------------------------

# Same band -> colour mapping the HTML blueprint uses, so the score reads
# identically in the app and in the downloaded report.
_JUDGE_BAND_COLORS = {
    "Excellent": "#1a9b5c",
    "Strong": "#2f6bff",
    "Usable": "#d9a300",
    "Weak": "#e06b1f",
    "Critical": "#e0342f",
}

_JUDGE_STATUS_COLORS = {
    "PASS": ("#e6f7ee", "#1a9b5c"),
    "WARN": ("#fff6e0", "#c98a00"),
    "FAIL": ("#fdeaea", "#d9342c"),
}


def _judge_score_hero(judge) -> str:
    """The big score + band badge at the top of the Judge tab."""
    score = judge.overall_score
    band = judge.quality_band or "—"
    color = _JUDGE_BAND_COLORS.get(band, "#2f6bff")
    score_text = "—" if score is None else f"{score:g}"

    raw = judge.raw_weighted_score
    penalty = judge.constraint_penalty or 0
    subs = []
    if raw is not None:
        subs.append(f"Weighted criteria total <strong>{raw:g}</strong>")
    subs.append(f"Constraint deductions <strong>-{penalty:g}</strong>")
    if judge.failed_count:
        subs.append(
            f"<strong style='color:#e0342f'>{judge.failed_count} failed</strong>"
        )
    if judge.warned_count:
        subs.append(
            f"<strong style='color:#c98a00'>{judge.warned_count} warned</strong>"
        )

    return (
        "<div class='sf-card' style='padding:1.1rem 1.3rem; margin-bottom:0.8rem;'>"
        "<div style='display:flex; align-items:center; gap:1.4rem; flex-wrap:wrap;'>"
        f"<div style='font-size:2.6rem; font-weight:800; color:{color}; line-height:1;'>{_esc(score_text)}"
        "<span style='font-size:1rem; font-weight:600; color:var(--sf-text-muted);'>/100</span></div>"
        f"<div style='flex:1; min-width:220px;'>"
        f"<div style='font-size:1.05rem; font-weight:700; color:{color};'>{_esc(band)}</div>"
        f"<div style='font-size:0.82rem; color:var(--sf-text-muted); margin-top:2px;'>"
        f"{_esc(judge.quality_band_description)}</div>"
        f"<div style='font-size:0.8rem; color:var(--sf-text-muted); margin-top:6px;'>"
        f"{' &middot; '.join(subs)}</div>"
        "</div></div></div>"
    )


def _judge_criteria_block(judge) -> None:
    """One expandable row per rubric criterion, with a score bar."""
    if not judge.criteria:
        st.info("The Judge returned no per-criterion evaluation.")
        return

    for crit in judge.criteria:
        score = crit.score or 0
        color = "#1a9b5c" if score >= 75 else "#d9a300" if score >= 50 else "#d9342c"
        header = (
            f"**{crit.name}**  ·  score {score}/100  ·  weight {crit.weight:g}%"
        )
        with st.expander(header):
            if crit.assessment:
                st.markdown(f"*{crit.assessment}*")
            st.markdown(
                f"<div style='height:6px; background:#eceffa; border-radius:999px; "
                f"margin:6px 0 10px 0; overflow:hidden;'>"
                f"<div style='height:100%; width:{max(0, min(100, score))}%; "
                f"background:{color}; border-radius:999px;'></div></div>",
                unsafe_allow_html=True,
            )
            if crit.evidence:
                st.markdown("**Evidence**")
                st.markdown(_list_to_html(crit.evidence))
            if crit.issues:
                st.markdown("**Issues**")
                st.markdown(_list_to_html(crit.issues))
            if crit.improvements:
                st.markdown("**Suggested improvements**")
                st.markdown(_list_to_html(crit.improvements))


def _judge_checks_table(judge) -> None:
    """The deterministic PASS/WARN/FAIL checks."""
    if not judge.hard_constraint_checks:
        st.info("No hard-constraint checks were recorded.")
        return

    rows = ""
    for chk in judge.hard_constraint_checks:
        bg, fg = _JUDGE_STATUS_COLORS.get(chk.status, ("#eef1f6", "#4b5563"))
        detail = _esc(chk.evidence)
        if chk.recommendation:
            detail += (
                "<div style='margin-top:3px; color:var(--sf-text-muted);'>"
                f"<strong>Fix:</strong> {_esc(chk.recommendation)}</div>"
            )
        rows += (
            "<tr>"
            f"<td style='padding:5px 8px; vertical-align:top;'>{_esc(chk.constraint)}</td>"
            f"<td style='padding:5px 8px;'><span style='display:inline-block; "
            f"padding:2px 9px; border-radius:999px; font-size:0.75rem; font-weight:700; "
            f"background:{bg}; color:{fg};'>{_esc(chk.status)}</span></td>"
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


def _render_judge(data: dict) -> None:
    """Render the Judge result (the 5th pipeline step)."""
    from models import JudgeEvaluation

    judge = JudgeEvaluation.from_dict(data)
    if not data:
        st.info("The Judge did not return a result for this consultation.")
        return

    if judge.judge_status == "partial" or judge.criteria_missing:
        st.warning(
            f"The judging model did not score "
            f"{len(judge.criteria_missing) or 'all'} of the rubric criteria, so "
            "those contribute zero to the total. The score below is based only "
            "on what was returned."
        )

    st.markdown(_judge_score_hero(judge), unsafe_allow_html=True)

    if judge.judge_summary:
        _card("📝 Judge Summary", f"<p style='margin:0;'>{_esc(judge.judge_summary)}</p>")

    st.markdown("#### Evaluation Domains")
    st.caption("Open a domain to see the Judge's evidence, issues and improvements.")
    _judge_criteria_block(judge)

    st.markdown("#### Hard Constraint Checks")
    st.caption(
        "Deterministic rule-based checks run in Python, not by the model. "
        "Each failure deducts from the score by severity."
    )
    _judge_checks_table(judge)

    c1, c2 = st.columns(2)
    with c1:
        _card("💪 Strengths", _list_to_html(judge.strengths))
        _card("🚨 Critical Issues",
              _list_to_html(judge.critical_issues, empty_text="None identified."))
    with c2:
        _card("🩹 Weaknesses", _list_to_html(judge.weaknesses))
        _card("🛠️ Recommended Improvements",
              _list_to_html(judge.recommended_improvements,
                            empty_text="None suggested."))

    if judge.cross_agent_consistency:
        _card("🔄 Cross-Agent Consistency",
              f"<p style='margin:0;'>{_esc(judge.cross_agent_consistency)}</p>")

    if judge.scoring_explanation:
        st.caption(f"How this score was calculated: {judge.scoring_explanation}")


def _render_saved_results() -> None:
    """Re-render a completed consultation from session state.

    Called on Streamlit reruns after the pipeline already finished, so we
    don't POST /consultations again (which used to create duplicate docs).
    """
    saved = st.session_state["consult_results"]
    agent_results = saved.get("agent_results") or {}
    agent_statuses = saved.get("agent_statuses") or {}
    status_label = saved.get("status_label")

    if status_label == "completed":
        st.success("🎉 **All agents and the Judge finished!** Your solution "
                   "blueprint is ready. Click the tabs above to view details.")
    else:
        st.info("Consultation in progress…")

    consultation_id = st.session_state.get("active_consultation_id")
    if consultation_id:
        st.markdown("")
        try:
            html_report = api_client.export_blueprint_html(
                token=st.session_state["auth_token"],
                consultation_id=consultation_id,
            )
            st.download_button(
                "📥 Download Blueprint (HTML)",
                data=html_report,
                file_name="blueprint.html",
                mime="text/html",
                type="primary",
            )
        except ApiError as dlerr:
            st.warning(f"Blueprint ready, but download failed: {dlerr}")

    tabs = st.tabs(AGENT_TABS)
    for idx, key in enumerate(AGENT_ORDER):
        with tabs[idx]:
            if key in agent_results:
                _render_agent_output(key, agent_results[key])
            else:
                st.info("No output for this step yet.")
