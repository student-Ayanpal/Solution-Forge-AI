"""
styles.py
=========
Central place for the CSS/branding that makes the app look like a polished,
professional product — consistent spacing, a real color system, and text
that stays legible regardless of the visitor's browser theme.

Two bugs this file (plus .streamlit/config.toml) permanently fixes:

1. "Text turns white / disappears" — the previous CSS only ever set
   *background* colors and never explicit *text* colors, so on a
   dark-themed browser Streamlit's default text rendered near-white on
   top of white cards. Every text-bearing rule below sets an explicit
   color, and config.toml pins the app to a light theme so this can't
   silently regress again.

2. "White box on top of the logo" — that's Streamlit's own default
   toolbar header, which renders as an opaque white bar across the very
   top of the page (above the sidebar logo and above the login card).
   It's made transparent below so it blends into the brand background
   instead of sitting on top of it like a stray rectangle.
"""

import base64
from pathlib import Path

import streamlit as st

ASSETS_DIR = Path(__file__).parent / "assets"
LOGO_FULL = ASSETS_DIR / "logo_full.png"      # shield + wordmark
LOGO_ICON = ASSETS_DIR / "logo_icon.png"      # shield only


@st.cache_data(show_spinner=False)
def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def logo_data_uri(icon_only: bool = False) -> str:
    """Base64 data-URI for the SolutionForge AI logo, for use in raw <img> tags."""
    path = LOGO_ICON if icon_only else LOGO_FULL
    if not path.exists():
        return ""
    return f"data:image/png;base64,{_b64(path)}"


GLOBAL_CSS = """
<style>
    :root {
        --sf-navy: #0f2a4d;
        --sf-navy-2: #16345c;
        --sf-blue: #1d5fb8;
        --sf-blue-dark: #144a94;
        --sf-blue-light: #eaf1fd;
        --sf-teal: #1f5f66;
        --sf-silver: #aeb6c2;
        --sf-bg: #f3f5f9;
        --sf-text: #1a2233;
        --sf-text-muted: #626c7c;
        --sf-border: #e4e8ef;
        --sf-radius: 14px;
        --sf-shadow: 0 6px 20px rgba(15, 42, 77, 0.07);
        --sf-shadow-lg: 0 20px 48px rgba(15, 42, 77, 0.14);
    }

    /* ---------- Kill Streamlit's default chrome that fights the design ---------- */
    header[data-testid="stHeader"] {
        background: transparent;
        box-shadow: none;
    }
    #MainMenu, footer { visibility: hidden; }
    div[data-testid="stDecoration"] { display: none; }
    .block-container { padding-top: 2.2rem; max-width: 1180px; }

    /* ---------- Base canvas & typography ---------- */
    .stApp {
        background: var(--sf-bg);
    }
    html, body, [class*="css"] {
        color: var(--sf-text) !important;
        font-family: "Inter", "Source Sans Pro", -apple-system, BlinkMacSystemFont, sans-serif;
    }
    h1, h2, h3, h4, h5, h6,
    p, span, label, li, div,
    .stMarkdown, .stCaption, .stText {
        color: var(--sf-text);
    }
    h2 {
        font-weight: 800;
        letter-spacing: -0.015em;
        color: var(--sf-navy) !important;
        margin-bottom: 1.3rem;
    }
    h3 { color: var(--sf-navy) !important; font-weight: 700; }
    .stCaption, small, [data-testid="stCaptionContainer"] {
        color: var(--sf-text-muted) !important;
    }
    hr { border-color: var(--sf-border); }

    /* ---------- Branded page header (icon + title + thin accent rule) ---------- */
    .sf-header {
        display: flex;
        align-items: center;
        gap: 0.8rem;
        margin-bottom: 0.35rem;
    }
    .sf-header img { height: 34px; }
    .sf-header .sf-header-title {
        font-size: 1.55rem;
        font-weight: 800;
        color: var(--sf-navy);
        letter-spacing: -0.015em;
    }
    .sf-header-rule {
        height: 3px;
        width: 46px;
        background: linear-gradient(90deg, var(--sf-blue), var(--sf-teal));
        border-radius: 999px;
        margin-bottom: 1.6rem;
    }

    /* ---------- Card container used across pages ---------- */
    .sf-card {
        background: #ffffff;
        border: 1px solid var(--sf-border);
        border-radius: var(--sf-radius);
        padding: 1.6rem 1.85rem;
        box-shadow: var(--sf-shadow);
        margin-bottom: 1.1rem;
        color: var(--sf-text);
        transition: box-shadow 0.15s ease, transform 0.15s ease;
    }
    .sf-card * { color: inherit; }
    .sf-card strong, .sf-card b { color: var(--sf-navy); }
    .sf-card.sf-hover:hover {
        box-shadow: var(--sf-shadow-lg);
        transform: translateY(-1px);
    }
    .sf-card-title {
        font-weight: 800;
        color: var(--sf-navy);
        font-size: 1.02rem;
        margin-bottom: 0.9rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .sf-section-label {
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--sf-blue);
        margin: 0.2rem 0 0.5rem 0;
    }

    /* Mermaid's floating toolbar has a dark surface. The base typography
       rule above otherwise gives its icon spans the same dark foreground. */
    div[data-testid="stMarkdownContainer"] button[title],
    div[data-testid="stMarkdownContainer"] button[aria-label] {
        color: #ffffff !important;
        width: auto !important;
        min-width: 0 !important;
        min-height: 2rem !important;
        padding: 0.35rem 0.55rem !important;
        gap: 0.35rem;
    }
    div[data-testid="stMarkdownContainer"] button[title] *,
    div[data-testid="stMarkdownContainer"] button[aria-label] * {
        color: #ffffff !important;
        fill: currentColor !important;
    }
    /* Mermaid only exposes these actions as icons by default. Keep the action
       name visible, so users do not have to hover to discover it. */
    div[data-testid="stMarkdownContainer"] button[title]::after {
        content: attr(title);
        font-size: 0.75rem;
        line-height: 1;
        white-space: nowrap;
    }
    div[data-testid="stMarkdownContainer"] button[aria-label]:not([title])::after {
        content: attr(aria-label);
        font-size: 0.75rem;
        line-height: 1;
        white-space: nowrap;
    }
    [role="tooltip"], [role="tooltip"] * {
        color: #ffffff !important;
    }

    /* ================= AUTH PAGE ================= */
    .sf-auth-outer {
        display: flex;
        justify-content: center;
        margin-top: 1rem;
    }
    .sf-auth-shell {
        width: 100%;
        max-width: 920px;
        background: #ffffff;
        border-radius: 22px;
        box-shadow: var(--sf-shadow-lg);
        border: 1px solid var(--sf-border);
        overflow: hidden;
    }
    /* Left brand panel */
    .sf-auth-brand {
        background:
            radial-gradient(120% 140% at 0% 0%, rgba(255,255,255,0.10), transparent 55%),
            linear-gradient(160deg, var(--sf-navy) 0%, var(--sf-navy-2) 55%, var(--sf-blue-dark) 100%);
        padding: 2.6rem 2.2rem;
        height: 100%;
        min-height: 560px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        position: relative;
    }
    .sf-auth-brand img.sf-auth-icon {
        height: 68px;
        width: auto;
        align-self: flex-start;
        margin-bottom: 1.4rem;
        filter: drop-shadow(0 8px 18px rgba(0,0,0,0.35));
    }
    .sf-auth-brand-name {
        color: #ffffff !important;
        font-size: 1.55rem;
        font-weight: 800;
        letter-spacing: -0.01em;
        margin-bottom: 0.5rem;
    }
    .sf-auth-brand-tagline {
        color: #c3d2e8 !important;
        font-size: 0.95rem;
        line-height: 1.55;
        margin-bottom: 1.8rem;
        max-width: 320px;
    }
    .sf-auth-feature {
        display: flex;
        align-items: flex-start;
        gap: 0.65rem;
        margin-bottom: 0.9rem;
    }
    .sf-auth-feature, .sf-auth-feature span, .sf-auth-feature * {
        color: #e3eaf7 !important;
        font-size: 0.87rem;
    }
    .sf-auth-feature .sf-dot {
        flex: none;
        width: 22px; height: 22px;
        border-radius: 7px;
        background: rgba(255,255,255,0.12);
        border: 1px solid rgba(255,255,255,0.18);
        display: flex; align-items: center; justify-content: center;
        font-size: 0.8rem;
        margin-top: 0.05rem;
    }
    /* Right form panel */
    .sf-auth-form-pad {
        padding: 2.6rem 2.6rem 2rem 2.6rem;
    }
    .sf-auth-title {
        font-size: 1.35rem;
        font-weight: 800;
        color: var(--sf-navy);
        margin-bottom: 0.2rem;
    }
    .sf-auth-subtitle {
        font-size: 0.88rem;
        color: var(--sf-text-muted);
        margin-bottom: 1.5rem;
    }
    /* Remove the seam between the two auth panels */
    .sf-auth-shell div[data-testid="stHorizontalBlock"] { gap: 0 !important; }
    .sf-auth-shell div[data-testid="column"] { padding: 0 !important; }

    /* Segmented Login/Register toggle */
    .sf-toggle-row div[data-testid="column"] { padding: 0 3px; }
    .sf-toggle-row { margin-bottom: 1.3rem; }
    .sf-toggle-row button {
        border-radius: 10px !important;
        font-weight: 700 !important;
        border: 1px solid var(--sf-border) !important;
    }

    /* Inline link-style button (e.g. "Register" inside the login footer line) */
    .sf-link-marker + div[data-testid="stButton"] button,
    .sf-link-marker + div[data-testid="stVerticalBlock"] button {
        background: none !important;
        border: none !important;
        color: var(--sf-blue) !important;
        font-weight: 700 !important;
        padding: 0 !important;
        text-decoration: underline;
        box-shadow: none !important;
        width: auto !important;
    }
    .sf-link-marker + div[data-testid="stButton"] button:hover,
    .sf-link-marker + div[data-testid="stVerticalBlock"] button:hover {
        color: var(--sf-blue-dark) !important;
    }
    .sf-auth-footer-text {
        color: var(--sf-text-muted) !important;
        font-size: 0.87rem;
        display: inline;
    }

    /* ---------- Inputs ---------- */
    .stTextInput input, .stNumberInput input, .stTextArea textarea,
    .stSelectbox div[data-baseweb="select"] > div {
        border-radius: 10px !important;
        border: 1px solid #d5dae3 !important;
        color: var(--sf-text) !important;
        background-color: #ffffff !important;
    }
    /* Fix base-web popovers (Selectbox dropdown lists) falling back to dark mode */
    div[data-baseweb="popover"] > div, 
    ul[data-baseweb="menu"], 
    div[role="listbox"], 
    ul[role="listbox"] {
        background-color: #ffffff !important;
    }
    li[role="option"], ul[data-baseweb="menu"] li {
        color: var(--sf-text) !important;
        background-color: #ffffff !important;
    }
    li[role="option"]:hover, li[role="option"][aria-selected="true"],
    ul[data-baseweb="menu"] li:hover, ul[data-baseweb="menu"] li[aria-selected="true"] {
        background-color: var(--sf-blue-light) !important;
        color: var(--sf-navy) !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: var(--sf-blue) !important;
        box-shadow: 0 0 0 3px rgba(29,95,184,0.12) !important;
    }
    .stTextInput input::placeholder, .stTextArea textarea::placeholder {
        color: #9aa3b0 !important;
    }
    .stTextInput label, .stNumberInput label, .stTextArea label,
    .stSelectbox label, .stSlider label, .stCheckbox label p {
        color: var(--sf-text) !important;
        font-weight: 600 !important;
        font-size: 0.86rem !important;
    }
    .stSlider [data-baseweb="slider"] div[role="slider"] {
        background-color: var(--sf-blue) !important;
    }

    /* ---------- Buttons ---------- */
    div.stButton > button {
        border-radius: 10px;
        font-weight: 700;
        transition: all 0.15s ease;
    }
    div.stButton > button[kind="primary"] {
        background-color: var(--sf-blue);
        border-color: var(--sf-blue);
        color: #ffffff !important;
        box-shadow: 0 4px 14px rgba(29,95,184,0.28);
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: var(--sf-blue-dark);
        border-color: var(--sf-blue-dark);
        box-shadow: 0 6px 18px rgba(29,95,184,0.38);
    }
    div.stButton > button[kind="secondary"] {
        color: var(--sf-navy) !important;
        border-color: var(--sf-border);
        background-color: #ffffff;
    }
    div.stButton > button[kind="secondary"]:hover {
        border-color: var(--sf-blue);
        color: var(--sf-blue) !important;
    }
    div[data-testid="stDownloadButton"] button {
        border-radius: 10px;
        font-weight: 700;
        background-color: var(--sf-teal) !important;
        border-color: var(--sf-teal) !important;
        color: #ffffff !important;
    }

    /* ---------- Agent pipeline / stepper ---------- */
    .sf-agent-pill {
        border-radius: 12px;
        padding: 0.9rem 1rem;
        border: 1px solid #d7dde6;
        font-weight: 700;
        text-align: left;
        position: relative;
    }
    .sf-agent-pill, .sf-agent-pill * { color: inherit; }
    .sf-agent-pill.done { background: #eaf6ee; border-color: #b7e3c4; color: #186a3b; }
    .sf-agent-pill.in_progress {
        background: #fff8e6; border-color: #f3d98a; color: #8a6a00;
        animation: sf-pulse 1.4s ease-in-out infinite;
    }
    .sf-agent-pill.pending { background: #f4f5f7; border-color: #e1e4e8; color: #7a828c; }
    .sf-agent-pill.error { background: #fdecec; border-color: #f3b7b7; color: #a12626; }
    .sf-agent-sub { font-weight: 500; font-size: 0.82rem; display: block; margin-top: 0.15rem; }
    @keyframes sf-pulse { 0% { opacity: 1; } 50% { opacity: 0.6; } 100% { opacity: 1; } }

    /* ---------- Status badge ---------- */
    .sf-badge {
        display: inline-block;
        padding: 0.22rem 0.75rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 800;
    }
    .sf-badge.ready { background:#e4f6ea; color:#186a3b; }
    .sf-badge.updated { background:#eaf2fe; color:#1a4f9c; }
    .sf-badge.processing { background:#fff4e0; color:#946200; }
    .sf-badge.failed { background:#fdecec; color:#a12626; }

    /* ---------- Metrics ---------- */
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid var(--sf-border);
        border-radius: 12px;
        padding: 0.9rem 1rem;
        box-shadow: var(--sf-shadow);
    }
    div[data-testid="stMetricValue"] { color: var(--sf-navy) !important; font-weight: 800; }
    div[data-testid="stMetricLabel"] { color: var(--sf-text-muted) !important; }

    /* ---------- Sidebar ---------- */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--sf-navy) 0%, var(--sf-navy-2) 100%);
        border-right: 1px solid #0c2038;
    }
    section[data-testid="stSidebar"] * { color: #eef2f9 !important; }
    section[data-testid="stSidebar"] > div:first-child { padding-top: 1.4rem; }
    section[data-testid="stSidebar"] .sf-brand-row {
        display: flex; align-items: center; gap: 0.6rem; margin: 0.2rem 0 0.3rem 0;
    }
    section[data-testid="stSidebar"] .sf-brand-row img { height: 32px; }
    section[data-testid="stSidebar"] .sf-brand {
        font-size: 1.12rem; font-weight: 800; margin-bottom: 0;
        color: #ffffff !important; line-height: 1.15;
    }
    section[data-testid="stSidebar"] .sf-welcome {
        color: #aebeda !important; font-size: 0.85rem; margin-bottom: 1.3rem;
        padding-bottom: 1rem; border-bottom: 1px solid rgba(255,255,255,0.12);
    }
    section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.14); }
    section[data-testid="stSidebar"] div.stButton > button {
        background-color: transparent;
        border: 1px solid transparent;
        color: #c3cfe3 !important;
        text-align: left;
        justify-content: flex-start;
        font-weight: 600;
        padding-left: 0.9rem;
    }
    section[data-testid="stSidebar"] div.stButton > button:hover {
        background-color: rgba(255,255,255,0.08);
        color: #ffffff !important;
    }
    section[data-testid="stSidebar"] div.stButton > button[kind="primary"] {
        background-color: rgba(255,255,255,0.14);
        border-color: rgba(255,255,255,0.22);
        color: #ffffff !important;
        box-shadow: inset 3px 0 0 0 #4f9dff;
    }
    section[data-testid="stSidebar"] .stCaption, section[data-testid="stSidebar"] small {
        color: #8697b5 !important;
    }
</style>
"""


def inject_global_css() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def page_header(title: str) -> None:
    """Renders the '<logo>  Page Title' header + accent rule used on every page."""
    logo = logo_data_uri(icon_only=True)
    logo_html = f'<img src="{logo}" alt="logo" />' if logo else ""
    st.markdown(
        f'<div class="sf-header">{logo_html}'
        f'<span class="sf-header-title">{title}</span></div>'
        f'<div class="sf-header-rule"></div>',
        unsafe_allow_html=True,
    )


def agent_status_class(status: str) -> str:
    return {
        "completed": "completed",
        "in_progress": "in_progress",
        "pending": "pending",
        "error": "error",
    }.get(status, "pending")


def status_badge_class(status_label: str) -> str:
    label = (status_label or "").lower()
    if "ready" in label:
        return "ready"
    if "updated" in label:
        return "updated"
    if "fail" in label:
        return "failed"
    return "processing"
