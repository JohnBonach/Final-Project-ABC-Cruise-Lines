"""Canonical shared constants for the ABC Cruise Lines DSS."""

from __future__ import annotations

from typing import Final

RESERVATION_CATEGORIES: Final[tuple[str, str, str, str]] = (
    "simple",
    "standard",
    "complex_group",
    "change_cancellation",
)

HISTORICAL_DEMAND_COLUMNS: Final[tuple[str, ...]] = (
    "week_id",
    "week_start",
    *RESERVATION_CATEGORIES,
    "staffing_agents",
)

CATEGORY_ASSUMPTIONS_COLUMNS: Final[tuple[str, ...]] = (
    "category",
    "handling_time_minutes",
    "average_revenue",
    "contribution_per_reservation",
)

WORKFORCE_ASSUMPTION_FIELDS: Final[tuple[str, ...]] = (
    "paid_hours_per_agent",
    "productive_processing_pct",
    "regular_hourly_wage",
    "overtime_multiplier",
    "abandonment_rate",
    "planned_staffing_agents",
)

FORECAST_RESULT_COLUMNS: Final[tuple[str, ...]] = (
    "category",
    "point_forecast",
    "historical_mean",
    "historical_std",
    "adjusted_std",
    "forecast_source",
)

SIMULATION_CONFIGURATION_FIELDS: Final[tuple[str, ...]] = (
    "iterations",
    "random_seed",
    "variability_multiplier",
    "distribution_name",
)

SIMULATION_SUPPORTED_DISTRIBUTIONS: Final[tuple[str, ...]] = ("normal",)

SIMULATION_OUTPUT_COLUMNS: Final[tuple[str, ...]] = (
    "simulation_id",
    *RESERVATION_CATEGORIES,
)

STAFFING_EVALUATION_COLUMNS: Final[tuple[str, ...]] = (
    "staffing_agents",
    "capacity_confidence",
    "probability_overtime_required",
    "expected_overtime_hours",
    "expected_abandoned_total",
    "expected_abandoned_simple",
    "expected_abandoned_standard",
    "expected_abandoned_complex_group",
    "expected_abandoned_change_cancellation",
    "regular_labor_cost",
    "expected_overtime_cost",
    "expected_lost_revenue",
    "expected_lost_contribution",
    "expected_total_economic_cost",
    "expected_retained_revenue",
    "expected_retained_contribution",
    "expected_net_contribution",
    "expected_unused_regular_hours",
)

NAMED_PLAN_COLUMNS: Final[tuple[str, ...]] = (
    "plan_name",
    "confidence_target",
    "staffing_agents",
    "staffing_evaluation_reference",
)

FORECAST_SOURCES: Final[tuple[str, str]] = (
    "automatic",
    "manual_override",
)

CONFIDENCE_TARGET_FIELDS: Final[tuple[str, str, str]] = (
    "lean",
    "balanced",
    "conservative",
)
