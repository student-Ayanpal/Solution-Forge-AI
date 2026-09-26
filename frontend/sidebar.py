"""
sidebar.py
==========
Renders the left navigation sidebar: logo + app name, a welcome blurb,
nav links (only once logged in), and a date footer. Import
render_sidebar() and call it at the top of every page.
"""

from datetime import datetime

import streamlit as st

import config
import session_state as ss
from styles import logo_data_uri

NAV_ITEMS = [
    {"key": "new_consultation", "label": "🔍  New Consultation"},
    {"key": "chat_history", "label": "📄  Chat History"},
    {"key": "help", "label": "❓  Help & Support"},
]


def render_sidebar() -> None:
    with st.sidebar:
        logo = logo_data_uri(icon_only=True)
        logo_html = f'<img src="{logo}" alt="logo" />' if logo else "🧩"
        st.markdown(
            f'<div class="sf-brand-row">{logo_html}'
            f'<p class="sf-brand">{config.APP_NAME}</p></div>',
            unsafe_allow_html=True,
        )

        if not ss.is_authenticated():
            st.markdown(f'<p class="sf-welcome">{config.APP_TAGLINE}</p>', unsafe_allow_html=True)
            return

        st.markdown(
            f'<p class="sf-welcome">Welcome back, {ss.current_user_label()}.</p>',
            unsafe_allow_html=True,
        )

        current_page = st.session_state.get("page")
        for item in NAV_ITEMS:
            is_active = current_page == item["key"]
            if st.button(
                item["label"],
                key=f"nav_{item['key']}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                ss.go_to(item["key"])
                st.rerun()

        st.markdown("---")
        if st.button("↩️  Sign Out", key="nav_sign_out", use_container_width=True):
            ss.log_out()
            st.rerun()

        st.markdown("<br>" * 2, unsafe_allow_html=True)
        st.caption("Date")
        st.caption(datetime.now().strftime("%B %Y"))
