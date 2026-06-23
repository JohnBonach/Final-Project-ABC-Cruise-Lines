"""Pure helpers for UI data tables and chart-ready frames."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from src.constants import HISTORICAL_DEMAND_COLUMNS, RESERVATION_CATEGORIES
from src.decision.narrative import REQUIRED_COMPARISON_COLUMNS
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
            "average_revenue",
            "contribution_per_reservation",
        ),
    )


def _require_comparison_table(comparison_table: pd.DataFrame) -> pd.DataFrame:
    """Validate the shared comparison-table contract used by the dashboard."""

    if not isinstance(comparison_table, pd.DataFrame):
        raise FieldValidationError("comparison_table must be a pandas DataFrame")

    missing_columns = [
        column for column in REQUIRED_COMPARISON_COLUMNS if column not in comparison_table.columns
    ]
    if missing_columns:
        raise FieldValidationError(
            f"comparison_table is missing required columns: {missing_columns}"
        )
    return comparison_table.copy(deep=True)


def _find_plan_record(comparison_table: pd.DataFrame, plan_name: str) -> dict[str, Any]:
    """Return the first comparison row for a named plan."""

    matches = comparison_table.loc[comparison_table["plan_name"] == plan_name]
    if matches.empty:
        raise FieldValidationError(f"comparison_table is missing the {plan_name!r} row")
    return dict(matches.iloc[0].to_dict())


def build_recommendation_summary_frame(
    recommendation: Mapping[str, Any],
    comparison_table: pd.DataFrame,
) -> pd.DataFrame:
    """Build a compact executive summary table from the orchestration result."""

    normalized_table = _require_comparison_table(comparison_table)
    recommended_record = recommendation["recommended_staffing_record"]
    recommended_staffing_agents = int(recommendation["recommended_staffing_agents"])

    previous_week_record = _find_plan_record(normalized_table, "Previous Week")
    manager_plan_record = _find_plan_record(normalized_table, "Manager Plan")

    return pd.DataFrame(
        [
            {
                "metric": "Recommended staffing",
                "value": recommended_staffing_agents,
                "units": "agents",
                "reference_plan": "Financial Recommendation",
            },
            {
                "metric": "Capacity confidence",
                "value": float(recommended_record["capacity_confidence"]) * 100.0,
                "units": "%",
                "reference_plan": "Financial Recommendation",
            },
            {
                "metric": "Expected overtime",
                "value": float(recommended_record["expected_overtime_hours"]),
                "units": "hours/week",
                "reference_plan": "Financial Recommendation",
            },
            {
                "metric": "Expected abandonment",
                "value": float(recommended_record["expected_abandoned_total"]),
                "units": "reservations/week",
                "reference_plan": "Financial Recommendation",
            },
            {
                "metric": "Expected total economic cost",
                "value": float(recommended_record["expected_total_economic_cost"]),
                "units": "USD/week",
                "reference_plan": "Financial Recommendation",
            },
            {
                "metric": "Difference vs previous week",
                "value": recommended_staffing_agents - int(previous_week_record["staffing_agents"]),
                "units": "agents",
                "reference_plan": "Previous Week",
            },
            {
                "metric": "Difference vs manager plan",
                "value": recommended_staffing_agents - int(manager_plan_record["staffing_agents"]),
                "units": "agents",
                "reference_plan": "Manager Plan",
            },
        ],
        columns=("metric", "value", "units", "reference_plan"),
    )


def build_plan_comparison_frame(comparison_table: pd.DataFrame) -> pd.DataFrame:
    """Return a comparison table with clear units and recommendation deltas."""

    normalized_table = _require_comparison_table(comparison_table)
    recommended_record = _find_plan_record(
        normalized_table,
        "Financial Recommendation",
    )
    recommended_staffing = int(recommended_record["staffing_agents"])
    recommended_cost = float(recommended_record["expected_total_economic_cost"])

    rows: list[dict[str, Any]] = []
    for plan_name in PLAN_ORDER:
        record = _find_plan_record(normalized_table, plan_name)
        staffing_agents = int(record["staffing_agents"])
        total_cost = float(record["expected_total_economic_cost"])
        rows.append(
            {
                "plan_name": plan_name,
                "staffing_agents": staffing_agents,
                "delta_staffing_vs_recommendation": staffing_agents - recommended_staffing,
                "capacity_confidence_pct": float(record["capacity_confidence"]) * 100.0,
                "expected_overtime_hours": float(record["expected_overtime_hours"]),
                "expected_abandoned_total": float(record["expected_abandoned_total"]),
                "expected_total_economic_cost_usd": total_cost,
                "delta_total_economic_cost_usd_vs_recommendation": total_cost - recommended_cost,
            }
        )

    return pd.DataFrame(
        rows,
        columns=(
            "plan_name",
            "staffing_agents",
            "delta_staffing_vs_recommendation",
            "capacity_confidence_pct",
            "expected_overtime_hours",
            "expected_abandoned_total",
            "expected_total_economic_cost_usd",
            "delta_total_economic_cost_usd_vs_recommendation",
        ),
    )


def build_tradeoff_chart_frames(
    comparison_table: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Return chart-ready frames for cost and risk comparison plots."""

    normalized_table = _require_comparison_table(comparison_table)
    comparison_frame = build_plan_comparison_frame(normalized_table)

    return {
        "cost": comparison_frame.loc[
            :, ["plan_name", "expected_total_economic_cost_usd"]
        ].copy(),
        "overtime": comparison_frame.loc[
            :, ["plan_name", "expected_overtime_hours"]
        ].copy(),
        "abandonment": comparison_frame.loc[
            :, ["plan_name", "expected_abandoned_total"]
        ].copy(),
    }


def build_methodology_points() -> tuple[str, ...]:
    """Return manager-friendly summary points for the recommendation flow."""

    return (
        "Validate the shared history and scenario inputs before any staffing calculation begins.",
        "Build the weekly demand forecast from recent history, then let manual overrides replace only the categories the manager enables.",
        "Convert forecast demand into weekly workload using category handling times and workforce productivity assumptions.",
        "Compare the candidate staffing plans on cost, overtime, abandonment, and capacity confidence.",
        "Choose the plan with the lowest expected weekly economic cost among the evaluated options.",
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


__all__ = [
    "build_category_assumptions_frame",
    "build_methodology_points",
    "build_results_export_frames",
    "build_plan_comparison_frame",
    "build_forecast_display_frame",
    "build_history_display_frame",
    "build_recommendation_summary_frame",
    "build_tradeoff_chart_frames",
]
