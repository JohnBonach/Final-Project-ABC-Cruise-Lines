"""Streamlit entry point for the ABC Cruise Lines Reservation Staffing DSS."""

import streamlit as st

from src.ui.components import _load_defaults, _load_history, render_main_dashboard


def main() -> None:
    st.set_page_config(
        page_title="ABC Cruise Lines Reservation Staffing DSS",
        page_icon="\U0001f6a2",
        layout="wide",
    )
    render_main_dashboard()


if __name__ == "__main__":
    main()