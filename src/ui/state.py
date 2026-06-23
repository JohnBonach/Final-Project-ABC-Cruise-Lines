"""Session-state helpers for the Streamlit application shell."""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import MutableMapping
from copy import deepcopy
from math import isfinite
from numbers import Real
from typing import Any

import pandas as pd

from src.constants import RESERVATION_CATEGORIES
from src.forecasting.weighted_moving_average import calculate_weighted_moving_average
from src.orchestration import build_application_result
from src.validation import EXPECTED_SCENARIO_NAMES

APP_SECTIONS: tuple[str, ...] = (
    "Overview",
    "Demand Inputs",
    "Operations",
    "Results",
)

DEFAULT_SESSION_STATE: dict[str, Any] = {
    "shell_initialized": False,
    "active_section": APP_SECTIONS[0],
    "selected_category": RESERVATION_CATEGORIES[0],
    "forecast_mode": "automatic",
    "scenario_label": EXPECTED_SCENARIO_NAMES[1],
    "weeks_to_display": 12,
    "show_contract_snapshot": False,
    "manual_override_notes": "",
    "draft_inputs": None,
    "applied_inputs": None,
    "baseline_inputs": None,
    "analysis_result": None,
    "analysis_error": None,
    "results_stale": False,
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


def _percent_widget_key(base_key: str) -> str:
    """Return the backing widget key for a percent-valued control."""

    return f"{base_key}__percent"


def _normalize_shell_preferences(session_state: MutableMapping[str, Any]) -> None:
    """Normalize shell preference fields in place."""

    session_state.setdefault("active_section", APP_SECTIONS[0])
    if session_state["active_section"] not in APP_SECTIONS:
        session_state["active_section"] = APP_SECTIONS[0]

    session_state.setdefault("selected_category", RESERVATION_CATEGORIES[0])
    if session_state["selected_category"] not in RESERVATION_CATEGORIES:
        session_state["selected_category"] = RESERVATION_CATEGORIES[0]

    session_state.setdefault("forecast_mode", DEFAULT_SESSION_STATE["forecast_mode"])
    if session_state["forecast_mode"] in FORECAST_MODE_MIGRATIONS:
        session_state["forecast_mode"] = FORECAST_MODE_MIGRATIONS[session_state["forecast_mode"]]
    if session_state["forecast_mode"] not in FORECAST_MODE_MIGRATIONS.values():
        session_state["forecast_mode"] = DEFAULT_SESSION_STATE["forecast_mode"]

    session_state.setdefault("scenario_label", DEFAULT_SESSION_STATE["scenario_label"])
    if session_state["scenario_label"] not in EXPECTED_SCENARIO_NAMES:
        session_state["scenario_label"] = DEFAULT_SESSION_STATE["scenario_label"]

    session_state.setdefault("weeks_to_display", DEFAULT_SESSION_STATE["weeks_to_display"])
    session_state["weeks_to_display"] = int(session_state["weeks_to_display"])

    session_state.setdefault(
        "show_contract_snapshot",
        DEFAULT_SESSION_STATE["show_contract_snapshot"],
    )
    session_state["show_contract_snapshot"] = bool(session_state["show_contract_snapshot"])

    session_state.setdefault(
        "manual_override_notes",
        DEFAULT_SESSION_STATE["manual_override_notes"],
    )


def build_baseline_inputs(
    defaults: Mapping[str, Any],
    history: pd.DataFrame,
) -> dict[str, Any]:
    """Build the normalized baseline input payload from validated defaults and history."""

    automatic_forecast = calculate_weighted_moving_average(
        history,
        list(defaults["forecast_configuration"].weights),
    )

    return {
        "shell": {
            "forecast_mode": DEFAULT_SESSION_STATE["forecast_mode"],
            "scenario_label": DEFAULT_SESSION_STATE["scenario_label"],
        },
        "manual_overrides": {
            category: {
                "enabled": False,
                "value": float(automatic_forecast[category]),
            }
            for category in RESERVATION_CATEGORIES
        },
        "category_assumptions": [
            item.to_dict()
            for item in defaults["category_assumptions"]
        ],
        "workforce_assumptions": defaults["workforce_assumptions"].to_dict(),
        "simulation_settings": {
            "iterations": int(defaults["simulation_configuration"].iterations),
            "random_seed": int(defaults["simulation_configuration"].random_seed or 0),
        },
        "confidence_targets": defaults["confidence_targets"].to_dict(),
    }


def draft_inputs_differ_from_applied(session_state: Mapping[str, Any]) -> bool:
    """Return whether the stored draft and applied input payloads differ."""

    draft_inputs = session_state.get("draft_inputs")
    applied_inputs = session_state.get("applied_inputs")
    if draft_inputs is None or applied_inputs is None:
        return False
    return draft_inputs != applied_inputs


def build_application_result_from_inputs(
    input_payload: Mapping[str, Any],
    *,
    history: pd.DataFrame,
    defaults: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the orchestration result from a normalized input payload."""

    manual_overrides = {
        category: float(item["value"])
        for category, item in input_payload["manual_overrides"].items()
        if item["enabled"]
    }

    simulation_defaults = defaults["simulation_configuration"]
    simulation_configuration = {
        "iterations": int(input_payload["simulation_settings"]["iterations"]),
        "random_seed": int(input_payload["simulation_settings"]["random_seed"]),
        "variability_multiplier": float(simulation_defaults.variability_multiplier),
        "distribution_name": str(simulation_defaults.distribution_name),
    }

    return build_application_result(
        history=history,
        category_assumptions=tuple(
            dict(item) for item in input_payload["category_assumptions"]
        ),
        workforce_assumptions=dict(input_payload["workforce_assumptions"]),
        forecast_configuration=defaults["forecast_configuration"],
        simulation_configuration=simulation_configuration,
        confidence_targets=dict(input_payload["confidence_targets"]),
        previous_week_staffing=int(history.iloc[-1]["staffing_agents"]),
        manager_planned_staffing=int(
            input_payload["workforce_assumptions"]["planned_staffing_agents"]
        ),
        manual_overrides=manual_overrides or None,
    )


def _analysis_error_payload(result: Mapping[str, Any]) -> dict[str, str]:
    """Return a user-readable analysis error payload."""

    error = result.get("error", {})
    return {
        "type": str(error.get("type", "AnalysisError")),
        "message": str(error.get("message", "Unable to complete the analysis.")),
    }


def sync_widgets_from_draft(session_state: MutableMapping[str, Any]) -> None:
    """Sync widget-backed keys from the stored draft inputs."""

    draft_inputs = session_state.get("draft_inputs")
    if not isinstance(draft_inputs, Mapping):
        return

    shell = draft_inputs["shell"]
    session_state["forecast_mode"] = shell["forecast_mode"]
    session_state["scenario_label"] = shell["scenario_label"]

    for category in RESERVATION_CATEGORIES:
        manual_override = draft_inputs["manual_overrides"][category]
        session_state[manual_override_enabled_key(category)] = bool(manual_override["enabled"])
        session_state[manual_override_value_key(category)] = float(manual_override["value"])

    for item in draft_inputs["category_assumptions"]:
        category = str(item["category"])
        session_state[category_assumption_key(category, "handling_time_minutes")] = float(
            item["handling_time_minutes"]
        )
        session_state[category_assumption_key(category, "average_revenue")] = float(
            item["average_revenue"]
        )
        session_state[
            category_assumption_key(category, "contribution_per_reservation")
        ] = float(item["contribution_per_reservation"])

    workforce = draft_inputs["workforce_assumptions"]
    session_state[workforce_control_key("paid_hours_per_agent")] = float(
        workforce["paid_hours_per_agent"]
    )
    session_state[_percent_widget_key(workforce_control_key("productive_processing_pct"))] = (
        decimal_to_percent(float(workforce["productive_processing_pct"]))
    )
    session_state[workforce_control_key("regular_hourly_wage")] = float(
        workforce["regular_hourly_wage"]
    )
    session_state[workforce_control_key("overtime_multiplier")] = float(
        workforce["overtime_multiplier"]
    )
    session_state[_percent_widget_key(workforce_control_key("abandonment_rate"))] = (
        decimal_to_percent(float(workforce["abandonment_rate"]))
    )
    session_state[workforce_control_key("planned_staffing_agents")] = int(
        workforce["planned_staffing_agents"]
    )

    simulation_settings = draft_inputs["simulation_settings"]
    session_state[simulation_control_key("iterations")] = int(
        simulation_settings["iterations"]
    )
    session_state[simulation_control_key("random_seed")] = int(
        simulation_settings["random_seed"]
    )

    confidence_targets = draft_inputs["confidence_targets"]
    session_state[_percent_widget_key(confidence_target_control_key("lean"))] = (
        decimal_to_percent(float(confidence_targets["lean"]))
    )
    session_state[_percent_widget_key(confidence_target_control_key("balanced"))] = (
        decimal_to_percent(float(confidence_targets["balanced"]))
    )
    session_state[_percent_widget_key(confidence_target_control_key("conservative"))] = (
        decimal_to_percent(float(confidence_targets["conservative"]))
    )


def collect_draft_inputs_from_widgets(
    session_state: Mapping[str, Any],
) -> dict[str, Any]:
    """Collect a normalized draft input payload from current widget-backed state."""

    manual_overrides = build_manual_overrides_from_state(session_state)

    return {
        "shell": {
            "forecast_mode": str(session_state["forecast_mode"]),
            "scenario_label": str(session_state["scenario_label"]),
        },
        "manual_overrides": {
            category: {
                "enabled": bool(
                    session_state.get(manual_override_enabled_key(category), False)
                ),
                "value": float(
                    manual_overrides.get(
                        category,
                        session_state[manual_override_value_key(category)],
                    )
                ),
            }
            for category in RESERVATION_CATEGORIES
        },
        "category_assumptions": [
            {
                "category": category,
                "handling_time_minutes": float(
                    session_state[category_assumption_key(category, "handling_time_minutes")]
                ),
                "average_revenue": float(
                    session_state[category_assumption_key(category, "average_revenue")]
                ),
                "contribution_per_reservation": float(
                    session_state[
                        category_assumption_key(category, "contribution_per_reservation")
                    ]
                ),
            }
            for category in RESERVATION_CATEGORIES
        ],
        "workforce_assumptions": {
            "paid_hours_per_agent": float(
                session_state[workforce_control_key("paid_hours_per_agent")]
            ),
            "productive_processing_pct": percent_to_decimal(
                float(
                    session_state[
                        _percent_widget_key(workforce_control_key("productive_processing_pct"))
                    ]
                )
            ),
            "regular_hourly_wage": float(
                session_state[workforce_control_key("regular_hourly_wage")]
            ),
            "overtime_multiplier": float(
                session_state[workforce_control_key("overtime_multiplier")]
            ),
            "abandonment_rate": percent_to_decimal(
                float(
                    session_state[
                        _percent_widget_key(workforce_control_key("abandonment_rate"))
                    ]
                )
            ),
            "planned_staffing_agents": int(
                session_state[workforce_control_key("planned_staffing_agents")]
            ),
        },
        "simulation_settings": {
            "iterations": int(session_state[simulation_control_key("iterations")]),
            "random_seed": int(session_state[simulation_control_key("random_seed")]),
        },
        "confidence_targets": {
            "lean": percent_to_decimal(
                float(
                    session_state[
                        _percent_widget_key(confidence_target_control_key("lean"))
                    ]
                )
            ),
            "balanced": percent_to_decimal(
                float(
                    session_state[
                        _percent_widget_key(confidence_target_control_key("balanced"))
                    ]
                )
            ),
            "conservative": percent_to_decimal(
                float(
                    session_state[
                        _percent_widget_key(confidence_target_control_key("conservative"))
                    ]
                )
            ),
        },
    }


def update_draft_inputs_from_widgets(session_state: MutableMapping[str, Any]) -> None:
    """Persist current widget values as the stored draft payload."""

    session_state["draft_inputs"] = collect_draft_inputs_from_widgets(session_state)
    session_state["results_stale"] = draft_inputs_differ_from_applied(session_state)


def refresh_draft_shell_preferences(session_state: MutableMapping[str, Any]) -> None:
    """Update shell-backed draft preferences from the current top-level session state."""

    draft_inputs = session_state.get("draft_inputs")
    if not isinstance(draft_inputs, Mapping):
        return

    updated_draft_inputs = deepcopy(dict(draft_inputs))
    forecast_mode = str(
        session_state.get("forecast_mode", DEFAULT_SESSION_STATE["forecast_mode"])
    )
    if forecast_mode in FORECAST_MODE_MIGRATIONS:
        forecast_mode = FORECAST_MODE_MIGRATIONS[forecast_mode]
    if forecast_mode not in FORECAST_MODE_MIGRATIONS.values():
        forecast_mode = DEFAULT_SESSION_STATE["forecast_mode"]

    scenario_label = str(
        session_state.get("scenario_label", DEFAULT_SESSION_STATE["scenario_label"])
    )
    if scenario_label not in EXPECTED_SCENARIO_NAMES:
        scenario_label = DEFAULT_SESSION_STATE["scenario_label"]

    updated_draft_inputs["shell"]["forecast_mode"] = forecast_mode
    updated_draft_inputs["shell"]["scenario_label"] = scenario_label
    session_state["draft_inputs"] = updated_draft_inputs
    session_state["results_stale"] = draft_inputs_differ_from_applied(session_state)


def run_analysis_for_current_draft(
    session_state: MutableMapping[str, Any],
    *,
    history: pd.DataFrame,
    defaults: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply the current draft payload and run orchestration once."""

    candidate_draft_inputs = collect_draft_inputs_from_widgets(session_state)
    analysis_result = build_application_result_from_inputs(
        candidate_draft_inputs,
        history=history,
        defaults=defaults,
    )
    session_state["draft_inputs"] = candidate_draft_inputs

    if analysis_result.get("ok", False):
        session_state["applied_inputs"] = deepcopy(candidate_draft_inputs)
        session_state["analysis_result"] = analysis_result
        session_state["analysis_error"] = None
        session_state["results_stale"] = False
    else:
        session_state["analysis_error"] = _analysis_error_payload(analysis_result)
        session_state["results_stale"] = True

    return analysis_result


def initialize_session_state(
    session_state: MutableMapping[str, Any],
    *,
    history: pd.DataFrame,
    defaults: Mapping[str, Any],
) -> None:
    """Populate and initialize durable session-state keys."""

    for key, value in DEFAULT_SESSION_STATE.items():
        session_state.setdefault(key, deepcopy(value))

    _normalize_shell_preferences(session_state)

    if not session_state.get("shell_initialized", False):
        baseline_inputs = build_baseline_inputs(defaults, history)
        baseline_result = build_application_result_from_inputs(
            baseline_inputs,
            history=history,
            defaults=defaults,
        )

        session_state["baseline_inputs"] = deepcopy(baseline_inputs)
        session_state["draft_inputs"] = deepcopy(baseline_inputs)
        session_state["applied_inputs"] = deepcopy(baseline_inputs)
        session_state["analysis_result"] = (
            baseline_result if baseline_result.get("ok", False) else None
        )
        session_state["analysis_error"] = (
            None if baseline_result.get("ok", False) else _analysis_error_payload(baseline_result)
        )
        session_state["results_stale"] = False
        session_state["shell_initialized"] = True
        sync_widgets_from_draft(session_state)


def reset_session_state(
    session_state: MutableMapping[str, Any],
    *,
    history: pd.DataFrame,
    defaults: Mapping[str, Any],
) -> None:
    """Restore the application shell and analysis state to baseline."""

    baseline_inputs = build_baseline_inputs(defaults, history)
    baseline_result = build_application_result_from_inputs(
        baseline_inputs,
        history=history,
        defaults=defaults,
    )

    session_state["active_section"] = APP_SECTIONS[0]
    session_state["selected_category"] = RESERVATION_CATEGORIES[0]
    session_state["weeks_to_display"] = DEFAULT_SESSION_STATE["weeks_to_display"]
    session_state["show_contract_snapshot"] = DEFAULT_SESSION_STATE["show_contract_snapshot"]
    session_state["manual_override_notes"] = DEFAULT_SESSION_STATE["manual_override_notes"]
    session_state["baseline_inputs"] = deepcopy(baseline_inputs)
    session_state["draft_inputs"] = deepcopy(baseline_inputs)
    session_state["applied_inputs"] = deepcopy(baseline_inputs)
    session_state["analysis_result"] = (
        baseline_result if baseline_result.get("ok", False) else None
    )
    session_state["analysis_error"] = (
        None if baseline_result.get("ok", False) else _analysis_error_payload(baseline_result)
    )
    session_state["results_stale"] = False
    session_state["shell_initialized"] = True
    sync_widgets_from_draft(session_state)


def section_options() -> tuple[str, ...]:
    """Return the supported top-level app sections."""

    return APP_SECTIONS


__all__ = [
    "APP_SECTIONS",
    "DEFAULT_SESSION_STATE",
    "FORECAST_MODE_MIGRATIONS",
    "build_application_result_from_inputs",
    "build_baseline_inputs",
    "build_manual_overrides_from_state",
    "category_assumption_key",
    "collect_draft_inputs_from_widgets",
    "confidence_target_control_key",
    "confidence_targets_are_ordered",
    "decimal_to_percent",
    "draft_inputs_differ_from_applied",
    "initialize_session_state",
    "manual_override_enabled_key",
    "manual_override_value_key",
    "percent_to_decimal",
    "refresh_draft_shell_preferences",
    "reset_session_state",
    "run_analysis_for_current_draft",
    "section_options",
    "simulation_control_key",
    "sync_widgets_from_draft",
    "update_draft_inputs_from_widgets",
    "workforce_control_key",
]
