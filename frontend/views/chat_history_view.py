"""
views/chat_history_view.py
===========================
"Chat History" page — matches the mockup: a list of past consultations,
each with Title / Date / Cloud Preference / Status, and View Blueprint /
Export PDF actions.
"""

import streamlit as st

import api_client
import session_state as ss
import styles
from api_client import ApiError


def render() -> None:
    styles.page_header("Chat History")

    try:
        history = api_client.get_consultation_history(token=st.session_state["auth_token"])
    except ApiError as err:
        st.error(str(err))
        return

    if not history:
        st.info("You haven't run any consultations yet. Start one from **New Consultation**.")
        return

    for index, entry in enumerate(history):
        _render_history_row(entry, show_headings=index == 0)
        if index < len(history) - 1:
            st.divider()


def _render_history_row(entry: dict, show_headings: bool = False) -> None:
    col_title, col_date, col_cloud, col_status, col_view, col_export = st.columns(
        [3, 1.4, 1.4, 1.6, 1.2, 1.2]
    )

    user_input = entry.get("user_input") or {}
    business_idea = user_input.get("business_idea") or ""
    title = entry.get("title") or (business_idea[:60] + ("…" if len(business_idea) > 60 else ""))
    cloud_preference = entry.get("cloud_preference") or user_input.get("cloud_preference") or "—"

    timestamp = entry.get("timestamp") or entry.get("date")
    if isinstance(timestamp, str) and timestamp.endswith("Z"):
        timestamp = timestamp[:-1] + "UTC"
    try:
        # MongoDB stores UTC; show it in Indian Standard Time (UTC+5:30)
        from datetime import datetime, timedelta, timezone
        ist_offset = timezone(timedelta(hours=5, minutes=30))
        aware = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if aware.tzinfo is None:
            aware = aware.replace(tzinfo=timezone.utc)
        ist_dt = aware.astimezone(ist_offset)
        date_str = ist_dt.strftime("%d %b %Y, %I:%M %p")
    except Exception:
        date_str = str(timestamp) if timestamp else ""

    with col_title:
        if show_headings:
            st.markdown("**Title**")
        st.write(title or "Untitled")
    with col_date:
        if show_headings:
            st.markdown("**Date**")
        st.write(date_str)
    with col_cloud:
        if show_headings:
            st.markdown("**Cloud Preference**")
        st.write(cloud_preference)
    with col_status:
        if show_headings:
            st.markdown("**Status**")
        status_label = entry.get("status", "Processing")
        badge_class = styles.status_badge_class(status_label)
        st.markdown(f'<span class="sf-badge {badge_class}">{status_label}</span>', unsafe_allow_html=True)
    with col_view:
        st.write("")
        cid = entry.get("id") or entry.get("consultation_id")
        if st.button("View Blueprint", key=f"view_{cid}", use_container_width=True):
            st.session_state["viewing_consultation_id"] = cid
            ss.go_to("live_results")
            st.rerun()
    with col_export:
        st.write("")
        cid = entry.get("id") or entry.get("consultation_id")
        dl_key = f"html_export_{cid}"
        
        if dl_key in st.session_state:
            st.download_button(
                label="📥 Download",
                data=st.session_state[dl_key],
                file_name="blueprint.html",
                mime="text/html",
                use_container_width=True,
                key=f"dl_btn_{cid}"
            )
        else:
            if st.button("Export HTML", key=f"export_{cid}", use_container_width=True):
                try:
                    html_content = api_client.export_blueprint_html(st.session_state["auth_token"], cid)
                    st.session_state[dl_key] = html_content
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to fetch blueprint: {e}")
