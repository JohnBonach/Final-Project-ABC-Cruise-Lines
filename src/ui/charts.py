"""Pure helpers for UI data tables and chart-ready frames."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from src.constants import CATEGORY_DISPLAY_LABELS, HISTORICAL_DEMAND_COLUMNS, RESERVATION_CATEGORIES
from src.validation import FieldValidationError

PLAN_ORDER: tuple[str, ...] = (
    "Previous Week",
    "Manager Plan",
    "Lean",
    "Balanced",
    "Conservative",
    "Financial Recommendation",
)


def _require_history_table(history: pd.DataFrame) -> pd.DataFrame:
    """Validate the shared history table contract used by the UI."""
    if not isinstance(history, pd.DataFrame):
        raise FieldValidationError("history must be a pandas DataFrame")
    missing_columns = [
        column for column in HISTORICAL_DEMAND_COLUMNS if column not in history.columns
    ]
    if missing_columns:
        raise FieldValidationError(
            f"history is missing required columns: {missing_columns}"
        )
    return history.copy(deep=True)


def _require_forecast_table(
    forecast_result: pd.DataFrame,
    automatic_forecast: Mapping[str, float],
) -> pd.DataFrame:
    """Validate the forecast display inputs before building the review table."""
    if not isinstance(forecast_result, pd.DataFrame):
        raise FieldValidationError("forecast_result must be a pandas DataFrame")
    missing_columns = [
        column
        for column in (
            "category",
            "point_forecast",
            "historical_mean",
            "historical_std",
            "adjusted_std",
            "forecast_source",
        )
        if column not in forecast_result.columns
    ]
    if missing_columns:
        raise FieldValidationError(
            f"forecast_result is missing required columns: {missing_columns}"
        )
    missing_categories = [
        category
        for category in RESERVATION_CATEGORIES
        if category not in forecast_result["category"].tolist()
    ]
    if missing_categories:
        raise FieldValidationError(
            f"forecast_result is missing required categories: {missing_categories}"
        )
    missing_automatic_categories = [
        category for category in RESERVATION_CATEGORIES if category not in automatic_forecast
    ]
    if missing_automatic_categories:
        raise FieldValidationError(
            f"automatic_forecast is missing required categories: {missing_automatic_categories}"
        )
    return forecast_result.copy(deep=True)


def build_history_display_frame(
    history: pd.DataFrame,
    *,
    weeks_to_display: int | None = None,
) -> pd.DataFrame:
    """Return a UI-friendly history table with normalized date formatting."""
    if weeks_to_display is not None and weeks_to_display <= 0:
        raise ValueError("weeks_to_display must be greater than 0")
    display_history = _require_history_table(history)
    if weeks_to_display is not None:
        display_history = display_history.tail(weeks_to_display)
    display_history = display_history.loc[:, HISTORICAL_DEMAND_COLUMNS].copy()
    display_history["week_start"] = pd.to_datetime(
        display_history["week_start"],
        errors="raise",
    ).dt.strftime("%Y-%m-%d")
    return display_history


def build_history_display_frame_with_labels(history: pd.DataFrame) -> pd.DataFrame:
    """Return a UI-friendly history table with human-readable category labels."""
    display = build_history_display_frame(history)
    display = display.rename(
        columns={cat: CATEGORY_DISPLAY_LABELS[cat] for cat in RESERVATION_CATEGORIES}
    )
    return display


def build_forecast_display_frame(
    automatic_forecast: Mapping[str, float],
    forecast_result: pd.DataFrame,
    manual_overrides: Mapping[str, float] | None = None,
) -> pd.DataFrame:
    """Combine automatic and effective forecast values into a reviewable table."""
    ordered_forecast = _require_forecast_table(forecast_result, automatic_forecast).set_index(
        "category"
    )
    manual_overrides = manual_overrides or {}

    rows: list[dict[str, Any]] = []
    for category in RESERVATION_CATEGORIES:
        row = ordered_forecast.loc[category]
        rows.append(
            {
                "category": category,
                "automatic_forecast": float(automatic_forecast[category]),
                "manual_override": (
                    float(manual_overrides[category])
                    if category in manual_overrides
                    else None
                ),
                "effective_forecast": float(row["point_forecast"]),
                "forecast_source": str(row["forecast_source"]),
                "historical_mean": float(row["historical_mean"]),
                "historical_std": float(row["historical_std"]),
                "adjusted_std": float(row["adjusted_std"]),
            }
        )

    return pd.DataFrame(
        rows,
        columns=(
            "category",
            "automatic_forecast",
            "manual_override",
            "effective_forecast",
            "forecast_source",
            "historical_mean",
            "historical_std",
            "adjusted_std",
        ),
    )


def build_category_assumptions_frame(
    category_rows: Sequence[Mapping[str, Any]],
) -> pd.DataFrame:
    """Return a review table for the category-level assumption controls."""
    return pd.DataFrame(
        list(category_rows),
        columns=(
            "category",
            "handling_time_minutes",
            "average_booking_value",
        ),
    )


def build_deterministic_kpi_frame(
    deterministic_result: Mapping[str, Any],
    effective_forecast: Mapping[str, float],
) -> pd.DataFrame:
    """Extract primary KPIs from the deterministic staffing result."""
    total_bookings = sum(effective_forecast.values())
    return pd.DataFrame(
        [
            {"metric": "Forecasted bookings", "value": round(total_bookings, 1), "units": "bookings / week"},
            {
                "metric": "Forecasted workload",
                "value": round(float(deterministic_result["total_workload_hours"]), 1),
                "units": "hours / week",
            },
            {
                "metric": "Raw staffing need",
                "value": round(float(deterministic_result["raw_required_fte"]), 2),
                "units": "FTE",
            },
            {
                "metric": "Whole-agent need",
                "value": int(deterministic_result["unconstrained_required_agents"]),
                "units": "agents",
            },
            {
                "metric": "Recommended staffing",
                "value": int(deterministic_result["recommended_inhouse_agents"]),
                "units": "agents",
            },
        ],
        columns=("metric", "value", "units"),
    )


def build_secondary_kpi_frame(
    deterministic_result: Mapping[str, Any],
    previous_week_staffing: int,
    manager_planned_staffing: int,
    financial_recommendation: Mapping[str, Any],
) -> pd.DataFrame:
    """Extract secondary management KPIs."""
    recommended = int(deterministic_result["recommended_inhouse_agents"])
    recommended_record = financial_recommendation["recommended_staffing_record"]
    total_operating_cost = float(recommended_record["expected_total_weekly_operating_cost"])
    spare_capacity = float(deterministic_result["spare_capacity_hours"])
    overflow = float(deterministic_result["overflow_workload_hours"])

    rows = [
        {
            "metric": "Previous-week staffing",
            "value": previous_week_staffing,
            "units": "agents",
        },
        {
            "metric": "Manager-planned staffing",
            "value": manager_planned_staffing,
            "units": "agents",
        },
        {
            "metric": "Change from previous week",
            "value": f"{recommended - previous_week_staffing:+d}",
            "units": "agents",
        },
        {
            "metric": "Spare capacity or overflow",
            "value": f"{spare_capacity:.1f} spare" if overflow == 0.0 else f"{overflow:.1f} overflow",
            "units": "hours / week",
        },
        {
            "metric": "Total weekly operating cost",
            "value": total_operating_cost,
            "units": "USD / week",
        },
    ]
    return pd.DataFrame(rows, columns=("metric", "value", "units"))


def build_workload_breakdown_frame(
    effective_forecast: Mapping[str, float],
    deterministic_result: Mapping[str, Any],
    category_assumptions: Sequence[Mapping[str, Any]],
) -> pd.DataFrame:
    """Build per-category workload breakdown table with human-readable labels."""
    handling_times = {
        item["category"]: float(item["handling_time_minutes"])
        for item in category_assumptions
    }
    workload_by_cat = deterministic_result["workload_hours_by_category"]
    total_workload = float(deterministic_result["total_workload_hours"])

    rows = []
    for category in RESERVATION_CATEGORIES:
        bookings = float(effective_forecast[category])
        handling = handling_times[category]
        wl_hours = float(workload_by_cat[category])
        share = (wl_hours / total_workload * 100.0) if total_workload > 0 else 0.0
        rows.append(
            {
                "cruise_product": CATEGORY_DISPLAY_LABELS[category],
                "forecast_bookings": bookings,
                "handling_time_min": handling,
                "workload_hours": round(wl_hours, 1),
                "share_of_workload_pct": round(share, 1),
            }
        )

    return pd.DataFrame(
        rows,
        columns=(
            "cruise_product",
            "forecast_bookings",
            "handling_time_min",
            "workload_hours",
            "share_of_workload_pct",
        ),
    )


def build_staffing_capacity_frame(
    deterministic_result: Mapping[str, Any],
    workforce_assumptions: Mapping[str, Any],
) -> pd.DataFrame:
    """Build staffing and capacity explanation table."""
    return pd.DataFrame(
        [
            {
                "step": "Raw FTE",
                "value": round(float(deterministic_result["raw_required_fte"]), 2),
                "units": "FTE",
                "note": f"Workload / {workforce_assumptions['weekly_booking_processing_hours_per_agent']} hrs per agent",
            },
            {
                "step": "Unconstrained required agents",
                "value": int(deterministic_result["unconstrained_required_agents"]),
                "units": "agents",
                "note": "ceil(Raw FTE)",
            },
            {
                "step": "Minimum operating floor",
                "value": int(workforce_assumptions["minimum_schedulable_agents"]),
                "units": "agents",
                "note": "Minimum schedulable",
            },
            {
                "step": "Maximum in-house capacity",
                "value": int(workforce_assumptions["maximum_inhouse_agents"]),
                "units": "agents",
                "note": "Maximum in-house",
            },
            {
                "step": "Recommended in-house agents",
                "value": int(deterministic_result["recommended_inhouse_agents"]),
                "units": "agents",
                "note": "Clamped to floor and cap",
            },
            {
                "step": "Spare capacity",
                "value": round(float(deterministic_result["spare_capacity_hours"]), 1),
                "units": "hours / week",
                "note": "Available for other tasks",
            },
            {
                "step": "Overflow workload",
                "value": round(float(deterministic_result["overflow_workload_hours"]), 1),
                "units": "hours / week",
                "note": "Routed to third-party",
            },
        ],
        columns=("step", "value", "units", "note"),
    )


def build_financial_breakdown_frame(
    financial_recommendation: Mapping[str, Any],
    deterministic_result: Mapping[str, Any],
    category_assumptions: Sequence[Mapping[str, Any]],
    strategic_assumptions: Mapping[str, Any],
) -> pd.DataFrame:
    """Build financial breakdown table."""
    recommended_record = financial_recommendation["recommended_staffing_record"]
    labor_cost = float(recommended_record["regular_labor_cost"])
    overflow_commission = float(recommended_record["expected_overflow_commission"])
    total_cost = float(recommended_record["expected_total_weekly_operating_cost"])
    overflow_bookings = deterministic_result.get("overflow_bookings_by_category", {})

    avg_booking_values = {
        item["category"]: float(item["average_booking_value"])
        for item in category_assumptions
    }

    rows = [
        {
            "item": "In-house labor cost",
            "value": labor_cost,
            "units": "USD / week",
        },
        {
            "item": "Third-party overflow commission",
            "value": overflow_commission,
            "units": "USD / week",
        },
        {
            "item": "Total weekly operating cost",
            "value": total_cost,
            "units": "USD / week",
        },
    ]

    for category in RESERVATION_CATEGORIES:
        overflow_bk = float(overflow_bookings.get(category, 0.0))
        if overflow_bk > 0.0:
            label = CATEGORY_DISPLAY_LABELS[category]
            booking_value = overflow_bk * avg_booking_values[category]
            comm = booking_value * float(strategic_assumptions["third_party_commission_rate"])
            rows.append(
                {
                    "item": f"  - Overflow {label} (commission)",
                    "value": round(comm, 2),
                    "units": "USD / week",
                }
            )

    return pd.DataFrame(rows, columns=("item", "value", "units"))


def build_forecast_breakdown_frame(
    automatic_forecast: Mapping[str, float],
    scenario_adjusted_forecast: Mapping[str, float],
    effective_forecast: Mapping[str, float],
    manual_overrides: Mapping[str, float] | None,
    scenario_name: str,
) -> pd.DataFrame:
    """Build forecast breakdown showing all layers."""
    manual_overrides = manual_overrides or {}
    rows = []
    for category in RESERVATION_CATEGORIES:
        auto = float(automatic_forecast[category])
        adj = float(scenario_adjusted_forecast[category])
        eff = float(effective_forecast[category])
        is_manual = category in manual_overrides
        rows.append(
            {
                "cruise_product": CATEGORY_DISPLAY_LABELS[category],
                "automatic_forecast": round(auto, 1),
                "scenario_adjusted": round(adj, 1),
                "manual_override": float(manual_overrides[category]) if is_manual else None,
                "effective_forecast": round(eff, 1),
                "forecast_source": "manual_override" if is_manual else f"automatic ({scenario_name})",
            }
        )
    return pd.DataFrame(
        rows,
        columns=(
            "cruise_product",
            "automatic_forecast",
            "scenario_adjusted",
            "manual_override",
            "effective_forecast",
            "forecast_source",
        ),
    )


def build_overflow_detail_frame(
    deterministic_result: Mapping[str, Any],
) -> pd.DataFrame:
    """Build overflow detail by category."""
    overflow_bookings = deterministic_result.get("overflow_bookings_by_category", {})
    overflow_hours = deterministic_result.get("overflow_hours_by_category", {})

    rows = []
    for category in RESERVATION_CATEGORIES:
        bk = float(overflow_bookings.get(category, 0.0))
        hr = float(overflow_hours.get(category, 0.0))
        rows.append(
            {
                "cruise_product": CATEGORY_DISPLAY_LABELS[category],
                "overflow_bookings": round(bk, 1),
                "overflow_hours": round(hr, 1),
            }
        )

    return pd.DataFrame(
        rows,
        columns=("cruise_product", "overflow_bookings", "overflow_hours"),
    )


def build_results_export_frames(
    application_result: Mapping[str, Any],
    recommendation_summary: pd.DataFrame,
    comparison_frame: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Collect the most useful structured outputs for CSV export."""
    named_plans = application_result["named_plans"]
    narrative = application_result["narrative"]
    return {
        "forecast_result": application_result["forecast_result"].copy(),
        "staffing_evaluation_table": application_result["staffing_evaluation_table"].copy(),
        "named_plan_table": named_plans["table"].copy(),
        "comparison_table": narrative["comparison_table"].copy(),
        "plan_comparison_display": comparison_frame.copy(),
        "recommendation_summary": recommendation_summary.copy(),
    }


def build_methodology_points() -> tuple[str, ...]:
    """Return manager-friendly summary points for the recommendation flow."""
    return (
        "Validate the shared history and scenario inputs before any staffing calculation begins.",
        "Build the weekly demand forecast from recent four-week weighted moving average history, "
        "then apply scenario multipliers for Low, Expected, or High demand.",
        "Convert forecast demand into weekly workload using category handling times and "
        "weekly booking-processing hours per agent.",
        "Apply the operating floor (minimum schedulable agents) and in-house cap "
        "(maximum in-house agents) to determine recommended staffing.",
        "Calculate spare capacity or third-party overflow based on in-house capacity vs. demand.",
        "Compute in-house labor cost, overflow commission, and total weekly operating cost.",
    )