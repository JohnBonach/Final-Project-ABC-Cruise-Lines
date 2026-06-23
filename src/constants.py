"""Canonical shared constants for the ABC Cruise Lines DSS."""

from __future__ import annotations

from typing import Final

RESERVATION_CATEGORIES: Final[tuple[str, str, str]] = (
    "day_cruise",
    "seven_night_cruise",
    "nine_night_cruise",
)

CATEGORY_DISPLAY_LABELS: Final[dict[str, str]] = {
    "day_cruise": "Day / Half-Day Cruise",
    "seven_night_cruise": "Seven-Night Canada Cruise",
    "nine_night_cruise": "Nine-Night Canada Cruise",
}

HISTORICAL_DEMAND_COLUMNS: Final[tuple[str, ...]] = (
    "week_id",
    "week_start",
    *RESERVATION_CATEGORIES,
    "staffing_agents",
)

CATEGORY_ASSUMPTIONS_COLUMNS: Final[tuple[str, ...]] = (
    "category",
    "handling_time_minutes",
    "average_booking_value",
)

WORKFORCE_ASSUMPTION_FIELDS: Final[tuple[str, ...]] = (
    "paid_hours_per_agent",
    "weekly_booking_processing_hours_per_agent",
    "regular_hourly_wage",
    "minimum_schedulable_agents",
    "maximum_inhouse_agents",
    "planned_staffing_agents",
)

STRATEGIC_ASSUMPTION_FIELDS: Final[tuple[str, ...]] = (
    "third_party_commission_rate",
    "inhouse_capture_target",
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
    "probability_overflow_required",
    "expected_spare_capacity_hours",
    "expected_overflow_workload_hours",
    "expected_overflow_day_cruise",
    "expected_overflow_seven_night_cruise",
    "expected_overflow_nine_night_cruise",
    "regular_labor_cost",
    "expected_overflow_commission",
    "expected_total_weekly_operating_cost",
    "expected_inhouse_booking_value",
    "expected_overflow_booking_value",
    "expected_commission_avoided",
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
