"""
views/auth_view.py
===================
Login / Register page — a two-panel "professional SaaS" layout: a dark
brand panel on the left (logo, tagline, value props) and a clean white
form panel on the right.

Two things fixed here on top of the redesign:

1. The Login/Register switch used to be st.tabs(), whose active-state
   indicator got lost under custom CSS and looked broken. It's plain
   buttons bound to st.session_state["auth_tab"] instead — unambiguous,
   and can't visually desync from what's rendered.

2. The "Don't have an account?" line used to end in a dead <a href="#">
   that couldn't do anything in Streamlit. It's now a real button next
   to the text that flips auth_tab and reruns, so clicking it actually
   opens the Register form (and vice versa on the Register form).

Validation (per spec):
    Username -> 3-32 chars
    Email    -> must look like a valid email
    Password -> min 6 chars
"""

import streamlit as st

import api_client
import session_state as ss
from api_client import ApiError
from styles import logo_data_uri
from validators import validate_login_form, validate_registration_form


def render() -> None:
    st.markdown('<div class="sf-auth-outer"><div class="sf-auth-shell">', unsafe_allow_html=True)

    col_brand, col_form = st.columns([1, 1.15], gap="small")

    with col_brand:
        _render_brand_panel()

    with col_form:
        st.markdown('<div class="sf-auth-form-pad">', unsafe_allow_html=True)

        active = st.session_state["auth_tab"]
        if active == "Login":
            st.markdown('<div class="sf-auth-title">Welcome back</div>', unsafe_allow_html=True)
            st.markdown('<div class="sf-auth-subtitle">Sign in to pick up where you left off.</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown('<div class="sf-auth-title">Create your account</div>', unsafe_allow_html=True)
            st.markdown('<div class="sf-auth-subtitle">Takes less than a minute.</div>',
                        unsafe_allow_html=True)

        _render_auth_toggle()

        if active == "Login":
            _render_login_form()
        else:
            _render_register_form()

        st.markdown("</div>", unsafe_allow_html=True)  # /sf-auth-form-pad

    st.markdown("</div></div>", unsafe_allow_html=True)  # /sf-auth-shell /sf-auth-outer


def _render_brand_panel() -> None:
    icon = logo_data_uri(icon_only=True)
    icon_html = f'<img class="sf-auth-icon" src="{icon}" alt="SolutionForge AI" />' if icon else ""
    html_content = (
        '<div class="sf-auth-brand">'
        f'{icon_html}'
        '<div class="sf-auth-brand-name">SolutionForge AI</div>'
        '<div class="sf-auth-brand-tagline">Turn a business idea into a complete, delivery-ready solution blueprint.</div>'
        '<div class="sf-auth-feature"><span class="sf-dot">🧠</span><span>Four AI agents cover business analysis, architecture, tech and delivery planning</span></div>'
        '<div class="sf-auth-feature"><span class="sf-dot">⚡</span><span>A full blueprint in minutes, not weeks</span></div>'
        '<div class="sf-auth-feature"><span class="sf-dot">📄</span><span>Exportable, shareable delivery plans</span></div>'
        '</div>'
    )
    st.markdown(html_content, unsafe_allow_html=True)


def _render_auth_toggle() -> None:
    st.markdown('<div class="sf-toggle-row">', unsafe_allow_html=True)
    col_login, col_register = st.columns(2)
    active = st.session_state["auth_tab"]

    with col_login:
        if st.button("Login", key="auth_toggle_login", use_container_width=True,
                     type="primary" if active == "Login" else "secondary"):
            st.session_state["auth_tab"] = "Login"
            st.rerun()
    with col_register:
        if st.button("Register", key="auth_toggle_register", use_container_width=True,
                     type="primary" if active == "Register" else "secondary"):
            st.session_state["auth_tab"] = "Register"
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def _render_switch_link(question: str, link_label: str, target_tab: str, key: str) -> None:
    """'<question> <clickable link_label>' on one line — actually switches auth_tab."""
    col_text, col_btn = st.columns([2.1, 1])
    with col_text:
        st.markdown(
            f'<div style="padding-top:0.4rem;" class="sf-auth-footer-text">{question}</div>',
            unsafe_allow_html=True,
        )
    with col_btn:
        st.markdown('<div class="sf-link-marker"></div>', unsafe_allow_html=True)
        if st.button(link_label, key=key, use_container_width=True):
            st.session_state["auth_tab"] = target_tab
            st.rerun()


def _render_login_form() -> None:
    email = st.text_input("Email Address", key="login_email", placeholder="you@example.com")
    password = st.text_input("Password", key="login_password", type="password")

    if st.button("Login", key="login_submit", type="primary", use_container_width=True):
        is_valid, error = validate_login_form(email, password)
        if not is_valid:
            st.error(error)
            return
        try:
            with st.spinner("Signing you in..."):
                response = api_client.login(email=email.strip(), password=password)
            token = response.get("access_token")
            user = response.get("user", {"email": email})
            if not token:
                st.error("Login succeeded but no session token was returned. Please contact support.")
                return
            ss.log_in(token=token, user=user)
            st.rerun()
        except ApiError as err:
            st.error(str(err))

    st.write("")
    _render_switch_link("Don't have an account?", "Register", "Register", key="login_go_register")


def _render_register_form() -> None:
    username = st.text_input(
        "Username", key="register_username",
        placeholder="3-32 characters", max_chars=32,
    )
    email = st.text_input("Email Address", key="register_email", placeholder="you@example.com")
    password = st.text_input("Password (min 6 characters)", key="register_password", type="password")
    confirm_password = st.text_input("Confirm Password", key="register_confirm_password", type="password")

    if st.button("Register", key="register_submit", type="primary", use_container_width=True):
        is_valid, error = validate_registration_form(username, email, password, confirm_password)
        if not is_valid:
            st.error(error)
            return
        try:
            with st.spinner("Creating your account..."):
                response = api_client.register(
                    username=username.strip(), email=email.strip(), password=password,
                )
            st.success(response.get("message", "Account created successfully. Please log in."))
            st.session_state["auth_tab"] = "Login"
        except ApiError as err:
            st.error(str(err))

    st.write("")
    _render_switch_link("Already have an account?", "Login", "Login", key="register_go_login")
