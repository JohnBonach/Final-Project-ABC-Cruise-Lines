"""Streamlit entry point for the ABC Cruise Lines Reservation Staffing DSS."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st


def _load_components_module():
    """Load a fresh UI components module when Streamlit leaves a partial import cached."""
    module = importlib.import_module("src.ui.components")
    if hasattr(module, "render_main_dashboard"):
        return module

    sys.modules.pop("src.ui.components", None)
    return importlib.import_module("src.ui.components")


def main() -> None:
    st.set_page_config(
        page_title="ABC Cruise Lines Reservation Staffing DSS",
        page_icon="\U0001f6a2",
        layout="wide",
    )
    components = _load_components_module()
    components.render_main_dashboard()


if __name__ == "__main__":
    main()
