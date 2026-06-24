"""Session-state helpers for the ABC Cruise Lines single-page dashboard."""

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

DEFAULT_SESSION_STATE: dict[str, Any] = {
    "shell_initialized": False,
    "draft_inputs": None,
    "applied_inputs": None,
    "baseline_inputs": None,
    "analysis_result": None,
    "analysis_error": None,
    "results_stale": False,
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


def strategic_control_key(field_name: str) -> str:
    """Return the widget key for a strategic assumption control."""
    return f"strategic_{field_name}"


def decision_policy_control_key(field_name: str) -> str:
    """Return the widget key for a decision-policy control."""
    return f"decision_policy_{field_name}"


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
        "decision_policy": defaults["decision_policy"].to_dict(),
        "strategic_assumptions": defaults["strategic_assumptions"].to_dict(),
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
        decision_policy=dict(input_payload["decision_policy"]),
        strategic_assumptions=dict(input_payload["strategic_assumptions"]),
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

    for category in RESERVATION_CATEGORIES:
        manual_override = draft_inputs["manual_overrides"][category]
        session_state[manual_override_enabled_key(category)] = bool(manual_override["enabled"])
        session_state[manual_override_value_key(category)] = float(manual_override["value"])

    for item in draft_inputs["category_assumptions"]:
        category = str(item["category"])
        session_state[category_assumption_key(category, "handling_time_minutes")] = float(
            item["handling_time_minutes"]
        )
        session_state[category_assumption_key(category, "average_booking_value")] = float(
            item["average_booking_value"]
        )

    workforce = draft_inputs["workforce_assumptions"]
    session_state[workforce_control_key("paid_hours_per_agent")] = float(
        workforce["paid_hours_per_agent"]
    )
    session_state[workforce_control_key("weekly_booking_processing_hours_per_agent")] = float(
        workforce["weekly_booking_processing_hours_per_agent"]
    )
    session_state[workforce_control_key("regular_hourly_wage")] = float(
        workforce["regular_hourly_wage"]
    )
    session_state[workforce_control_key("minimum_schedulable_agents")] = int(
        workforce["minimum_schedulable_agents"]
    )
    session_state[workforce_control_key("maximum_inhouse_agents")] = int(
        workforce["maximum_inhouse_agents"]
    )
    session_state[workforce_control_key("planned_staffing_agents")] = int(
        workforce["planned_staffing_agents"]
    )

    decision_policy = draft_inputs["decision_policy"]
    session_state[
        decision_policy_control_key("minimum_inhouse_coverage_target")
    ] = float(decision_policy["minimum_inhouse_coverage_target"])

    strategic = draft_inputs["strategic_assumptions"]
    session_state[strategic_control_key("third_party_commission_rate")] = float(
        strategic["third_party_commission_rate"]
    )

    simulation_settings = draft_inputs["simulation_settings"]
    session_state[simulation_control_key("iterations")] = int(
        simulation_settings["iterations"]
    )
    session_state[simulation_control_key("random_seed")] = int(
        simulation_settings["random_seed"]
    )

    confidence_targets = draft_inputs["confidence_targets"]
    session_state[confidence_target_control_key("lean")] = float(
        confidence_targets["lean"]
    )
    session_state[confidence_target_control_key("balanced")] = float(
        confidence_targets["balanced"]
    )
    session_state[confidence_target_control_key("conservative")] = float(
        confidence_targets["conservative"]
    )


def collect_draft_inputs_from_widgets(
    session_state: Mapping[str, Any],
) -> dict[str, Any]:
    """Collect a normalized draft input payload from current widget-backed state."""
    manual_overrides = build_manual_overrides_from_state(session_state)

    return {
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
                "average_booking_value": float(
                    session_state[category_assumption_key(category, "average_booking_value")]
                ),
            }
            for category in RESERVATION_CATEGORIES
        ],
        "workforce_assumptions": {
            "paid_hours_per_agent": float(
                session_state[workforce_control_key("paid_hours_per_agent")]
            ),
            "weekly_booking_processing_hours_per_agent": float(
                session_state[workforce_control_key("weekly_booking_processing_hours_per_agent")]
            ),
            "regular_hourly_wage": float(
                session_state[workforce_control_key("regular_hourly_wage")]
            ),
            "minimum_schedulable_agents": int(
                session_state[workforce_control_key("minimum_schedulable_agents")]
            ),
            "maximum_inhouse_agents": int(
                session_state[workforce_control_key("maximum_inhouse_agents")]
            ),
            "planned_staffing_agents": int(
                session_state[workforce_control_key("planned_staffing_agents")]
            ),
        },
        "decision_policy": {
            "minimum_inhouse_coverage_target": float(
                session_state[
                    decision_policy_control_key("minimum_inhouse_coverage_target")
                ]
            ),
        },
        "strategic_assumptions": {
            "third_party_commission_rate": float(
                session_state[strategic_control_key("third_party_commission_rate")]
            ),
        },
        "simulation_settings": {
            "iterations": int(session_state[simulation_control_key("iterations")]),
            "random_seed": int(session_state[simulation_control_key("random_seed")]),
        },
        "confidence_targets": {
            "lean": float(
                session_state[confidence_target_control_key("lean")]
            ),
            "balanced": float(
                session_state[confidence_target_control_key("balanced")]
            ),
            "conservative": float(
                session_state[confidence_target_control_key("conservative")]
            ),
        },
    }


def update_draft_inputs_from_widgets(session_state: MutableMapping[str, Any]) -> None:
    """Persist current widget values as the stored draft payload."""
    session_state["draft_inputs"] = collect_draft_inputs_from_widgets(session_state)
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
