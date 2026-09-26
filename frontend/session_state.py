"""
session_state.py
=================
Centralised Streamlit session_state management: initial defaults, auth
helpers, and small routing helpers. Import `init_session_state()` once at
the top of app.py and use the getters/setters below everywhere else instead
of touching st.session_state keys directly — keeps key names consistent.
"""

import streamlit as st

DEFAULTS = {
    "page": "login",              # login | new_consultation | live_results | chat_history | help
    "auth_token": None,
    "user": None,                 # {"username": ..., "email": ...}
    "auth_tab": "Login",          # "Login" | "Register"
    "active_consultation_id": None,
    "consultation_summary": None,  # small dict shown in "Consultation Details" card
    "viewing_consultation_id": None,  # set when opening a past result from Chat History
}


def init_session_state() -> None:
    for key, value in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


def is_authenticated() -> bool:
    return bool(st.session_state.get("auth_token"))


def log_in(token: str, user: dict) -> None:
    st.session_state["auth_token"] = token
    st.session_state["user"] = user
    st.session_state["page"] = "new_consultation"


def log_out() -> None:
    for key, value in DEFAULTS.items():
        st.session_state[key] = value
    st.session_state["page"] = "login"


def go_to(page: str) -> None:
    st.session_state["page"] = page


def current_user_label() -> str:
    user = st.session_state.get("user") or {}
    return user.get("username") or user.get("email") or "there"
