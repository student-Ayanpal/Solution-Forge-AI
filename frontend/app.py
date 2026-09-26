"""
app.py
======
Entry point. Run with:

    streamlit run app.py

Routing is driven entirely by st.session_state["page"], set by
session_state.go_to(). We don't use Streamlit's native multipage
`pages/` folder because it renders its own nav in the sidebar — the
mockups require full control over the sidebar's look, so a single-file
router keeps that control.
"""

from pathlib import Path

import streamlit as st
from PIL import Image

import config
import session_state as ss
from sidebar import render_sidebar
from styles import inject_global_css
from views import auth_view, consultation_view, live_results_view, chat_history_view, help_view

_ICON_PATH = Path(__file__).parent / "assets" / "logo_icon.png"
_PAGE_ICON = Image.open(_ICON_PATH) if _ICON_PATH.exists() else "🧩"

st.set_page_config(
    page_title=config.APP_NAME,
    page_icon=_PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

ss.init_session_state()
inject_global_css()
render_sidebar()

PAGE_ROUTES = {
    "login": auth_view.render,
    "new_consultation": consultation_view.render,
    "live_results": live_results_view.render,
    "chat_history": chat_history_view.render,
    "help": help_view.render,
}


def main() -> None:
    if not ss.is_authenticated():
        auth_view.render()
        return

    page = st.session_state.get("page", "new_consultation")
    render_fn = PAGE_ROUTES.get(page, consultation_view.render)
    render_fn()


if __name__ == "__main__":
    main()
