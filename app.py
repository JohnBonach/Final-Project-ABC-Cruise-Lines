"""Streamlit entry point for the ABC Cruise Lines Reservation Staffing DSS."""

import streamlit as st

from src.ui.components import (
    _load_defaults,
    _load_history,
    render_active_section,
    render_header,
    render_sidebar,
)
from src.ui.state import initialize_session_state


def main() -> None:
    """Render the integrated ABC Cruise Lines reservation staffing DSS."""

    st.set_page_config(
        page_title="ABC Cruise Lines Reservation Staffing DSS",
        page_icon="🚢",
        layout="wide",
    )
    initialize_session_state(
        st.session_state,
        history=_load_history(),
        defaults=_load_defaults(),
    )
    render_sidebar(st.session_state)
    render_header()
    render_active_section(st.session_state)


if __name__ == "__main__":
    main()
