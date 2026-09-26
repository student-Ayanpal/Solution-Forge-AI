"""
views/help_view.py
===================
Simple static Help & Support page, present in the sidebar nav per the
mockup. Expand with real FAQ / contact content as needed.
"""

import streamlit as st

import styles


def render() -> None:
    styles.page_header("Help & Support")

    st.markdown('<div class="sf-card">', unsafe_allow_html=True)
    st.markdown("### Frequently Asked Questions")

    with st.expander("What does SolutionForge AI do?"):
        st.write(
            "It transforms a business idea and delivery constraints into a "
            "structured, consulting-style solution blueprint using a "
            "four-agent AI workflow: Business Analyst → Solution Architect "
            "→ Technology Advisor → Delivery Planner."
        )

    with st.expander("How long does a consultation take?"):
        st.write(
            "Each of the four agents runs in sequence, passing context to "
            "the next. You can watch live progress on the Live Results page."
        )

    with st.expander("Can I revisit a past blueprint?"):
        st.write(
            "Yes — open the Chat History page and click 'View Blueprint' "
            "on any past consultation."
        )

    st.markdown("### Contact Support")
    st.write("Email us at **support@solutionforge.ai** and we'll get back to you within one business day.")
    st.markdown("</div>", unsafe_allow_html=True)
