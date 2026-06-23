"""Session-state helpers for the Streamlit application shell."""

from __future__ import annotations

from collections.abc import MutableMapping
from collections.abc import Mapping
from math import isfinite
from numbers import Real
from typing import Any

from src.constants import RESERVATION_CATEGORIES
from src.validation import EXPECTED_SCENARIO_NAMES

APP_SECTIONS: tuple[str, ...] = (
    "Overview",
    "Demand Inputs",
    "Operations",
    "Results",
)

DEFAULT_SESSION_STATE: dict[str, Any] = {
    "shell_initialized": True,
    "active_section": APP_SECTIONS[0],
    "selected_category": RESERVATION_CATEGORIES[0],
    "forecast_mode": "automatic",
    "scenario_label": EXPECTED_SCENARIO_NAMES[1],
    "weeks_to_display": 12,
    "show_contract_snapshot": False,
    "manual_override_notes": "",
    "operations_checkpoint": "",
}

FORECAST_MODE_MIGRATIONS: dict[str, str] = {
    "Automatic": "automatic",
    "Manual": "manual_override",
}


def decimal_to_percent(value: float) -> float:
    """Convert an internal decimal fraction to a UI-friendly percent value."""

    return float(value) * 100.0


def percent_to_decimal(value: float) -> float:
    """Convert a UI-friendly percent value to an internal decimal fraction."""

    return float(value) / 100.0


def confidence_targets_are_ordered(targets: Mapping[str, Any]) -> bool:
    """Return whether Lean, Balanced, and Conservative are in logical order."""

    try:
        lean = float(targets["lean"])
        balanced = float(targets["balanced"])
        conservative = float(targets["conservative"])
    except (KeyError, TypeError, ValueError):
        return False

    return lean <= balanced <= conservative


def category_assumption_key(category: str, field_name: str) -> str:
    """Return the widget key for a category assumption control."""

    return f"category_{category}_{field_name}"


def manual_override_enabled_key(category: str) -> str:
    """Return the widget key for a forecast manual-override toggle."""

    return f"forecast_manual_override_enabled_{category}"


def manual_override_value_key(category: str) -> str:
    """Return the widget key for a forecast manual-override input."""

    return f"forecast_manual_override_value_{category}"


def workforce_control_key(field_name: str) -> str:
    """Return the widget key for a workforce-assumption control."""

    return f"workforce_{field_name}"


def simulation_control_key(field_name: str) -> str:
    """Return the widget key for a simulation control."""

    return f"simulation_{field_name}"


def confidence_target_control_key(field_name: str) -> str:
    """Return the widget key for a confidence-target control."""

    return f"confidence_target_{field_name}"


def build_manual_overrides_from_state(session_state: Mapping[str, Any]) -> dict[str, float]:
    """Collect enabled manual overrides and validate their numeric values."""

    overrides: dict[str, float] = {}
    for category in RESERVATION_CATEGORIES:
        if not session_state.get(manual_override_enabled_key(category), False):
            continue

        raw_value = session_state.get(manual_override_value_key(category))
        if isinstance(raw_value, bool) or not isinstance(raw_value, Real):
            raise ValueError(f"manual override for {category} must be a real number")

        normalized = float(raw_value)
        if not isfinite(normalized):
            raise ValueError(f"manual override for {category} must be finite")
        if normalized < 0.0:
            raise ValueError(f"manual override for {category} must be non-negative")

        overrides[category] = normalized
    return overrides


def initialize_session_state(session_state: MutableMapping[str, Any]) -> None:
    """Populate missing session-state keys without overwriting user changes."""

    for key, value in DEFAULT_SESSION_STATE.items():
        session_state.setdefault(key, value)

    if session_state["forecast_mode"] in FORECAST_MODE_MIGRATIONS:
        session_state["forecast_mode"] = FORECAST_MODE_MIGRATIONS[session_state["forecast_mode"]]
    if session_state["forecast_mode"] not in FORECAST_MODE_MIGRATIONS.values():
        session_state["forecast_mode"] = DEFAULT_SESSION_STATE["forecast_mode"]

    if session_state["scenario_label"] not in EXPECTED_SCENARIO_NAMES:
        session_state["scenario_label"] = DEFAULT_SESSION_STATE["scenario_label"]


def reset_session_state(session_state: MutableMapping[str, Any]) -> None:
    """Restore the application shell to its default state."""

    for key in list(session_state.keys()):
        del session_state[key]
    initialize_session_state(session_state)


def section_options() -> tuple[str, ...]:
    """Return the supported top-level app sections."""

    return APP_SECTIONS


__all__ = [
    "APP_SECTIONS",
    "DEFAULT_SESSION_STATE",
    "FORECAST_MODE_MIGRATIONS",
    "build_manual_overrides_from_state",
    "category_assumption_key",
    "confidence_target_control_key",
    "confidence_targets_are_ordered",
    "decimal_to_percent",
    "initialize_session_state",
    "manual_override_enabled_key",
    "manual_override_value_key",
    "percent_to_decimal",
    "reset_session_state",
    "section_options",
    "simulation_control_key",
    "workforce_control_key",
]
