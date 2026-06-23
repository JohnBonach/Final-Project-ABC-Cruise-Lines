"""Shortage allocation helpers for category-level shortage, abandonment, and overtime."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.constants import RESERVATION_CATEGORIES
from src.operations.workload import MINUTES_PER_HOUR
from src.validation import (
    FieldValidationError,
    validate_non_negative_integer,
    validate_non_negative,
    validate_percentage,
    validate_positive,
)

CategoryValueMap = dict[str, float]
ShortageAllocationResult = dict[str, CategoryValueMap | float]
CategoryShortageAllocationResult = dict[str, CategoryValueMap | float]


def _validate_category_value_map(
    values: Mapping[str, Any],
    *,
    field_name: str,
    allow_zero: bool = True,
) -> CategoryValueMap:
    """Validate a canonical category mapping and normalize its values to floats."""

    if not isinstance(values, Mapping):
        raise FieldValidationError(f"{field_name} must be a mapping keyed by category")

    actual_categories = tuple(values.keys())
    if actual_categories != RESERVATION_CATEGORIES:
        raise FieldValidationError(
            f"{field_name} must include each canonical category exactly once "
            f"and in the shared order {RESERVATION_CATEGORIES}"
        )

    validator = validate_non_negative if allow_zero else validate_positive
    return {
        category: validator(f"{field_name}[{category!r}]", values[category])
        for category in RESERVATION_CATEGORIES
    }


def _validate_handling_times_minutes(
    handling_times_minutes: Mapping[str, Any],
) -> CategoryValueMap:
    """Validate canonical handling times and normalize them to positive floats."""

    return _validate_category_value_map(
        handling_times_minutes,
        field_name="handling_times_minutes",
        allow_zero=False,
    )


def _validate_abandonment_rate(abandonment_rate: Any) -> float:
    """Validate the global abandonment rate as an internal decimal."""

    return validate_percentage("abandonment_rate", abandonment_rate)


def calculate_shortage_allocation_by_category(
    demand_by_category: Mapping[str, Any],
    handling_times_minutes: Mapping[str, Any],
    staffing_agents: Any,
    productive_hours_per_agent: Any,
) -> CategoryShortageAllocationResult:
    """Allocate any regular-capacity shortage proportionally across categories.

    The shortage workload is split by each category's share of total workload hours.
    The returned category maps preserve the canonical reservation order.
    """

    normalized_demand = _validate_category_value_map(
        demand_by_category,
        field_name="demand_by_category",
    )
    normalized_handling_times = _validate_handling_times_minutes(handling_times_minutes)
    normalized_staffing_agents = validate_non_negative_integer(
        "staffing_agents",
        staffing_agents,
    )
    normalized_productive_hours_per_agent = validate_positive(
        "productive_hours_per_agent",
        productive_hours_per_agent,
    )

    workload_hours_by_category = {
        category:
            normalized_demand[category]
            * normalized_handling_times[category]
            / MINUTES_PER_HOUR
        for category in RESERVATION_CATEGORIES
    }
    total_workload_hours = sum(workload_hours_by_category.values())
    regular_capacity_hours = (
        normalized_staffing_agents * normalized_productive_hours_per_agent
    )
    shortage_workload_hours = max(total_workload_hours - regular_capacity_hours, 0.0)

    if total_workload_hours > 0.0 and shortage_workload_hours > 0.0:
        excess_workload_hours_by_category = {
            category:
                workload_hours_by_category[category]
                / total_workload_hours
                * shortage_workload_hours
            for category in RESERVATION_CATEGORIES
        }
    else:
        excess_workload_hours_by_category = {
            category: 0.0
            for category in RESERVATION_CATEGORIES
        }

    excess_reservations_by_category = {
        category:
            excess_workload_hours_by_category[category]
            / (normalized_handling_times[category] / MINUTES_PER_HOUR)
        for category in RESERVATION_CATEGORIES
    }
    completed_reservations_by_category = {
        category: normalized_demand[category] - excess_reservations_by_category[category]
        for category in RESERVATION_CATEGORIES
    }

    return {
        "workload_hours_by_category": workload_hours_by_category,
        "completed_reservations_by_category": completed_reservations_by_category,
        "excess_reservations_by_category": excess_reservations_by_category,
        "excess_workload_hours_by_category": excess_workload_hours_by_category,
        "total_workload_hours": total_workload_hours,
        "regular_capacity_hours": regular_capacity_hours,
        "shortage_workload_hours": shortage_workload_hours,
    }


def calculate_abandonment_and_overtime(
    excess_reservations_by_category: Mapping[str, Any],
    handling_times_minutes: Mapping[str, Any],
    abandonment_rate: Any,
) -> ShortageAllocationResult:
    """Apply abandonment to excess reservations and convert the remainder to overtime."""

    normalized_excess = _validate_category_value_map(
        excess_reservations_by_category,
        field_name="excess_reservations_by_category",
    )
    normalized_handling_times = _validate_handling_times_minutes(handling_times_minutes)
    normalized_abandonment_rate = _validate_abandonment_rate(abandonment_rate)

    abandoned_reservations_by_category = {
        category: normalized_excess[category] * normalized_abandonment_rate
        for category in RESERVATION_CATEGORIES
    }
    overtime_reservations_by_category = {
        category: normalized_excess[category] - abandoned_reservations_by_category[category]
        for category in RESERVATION_CATEGORIES
    }

    overtime_minutes = sum(
        overtime_reservations_by_category[category] * normalized_handling_times[category]
        for category in RESERVATION_CATEGORIES
    )
    overtime_hours = overtime_minutes / MINUTES_PER_HOUR

    return {
        "abandoned_reservations_by_category": abandoned_reservations_by_category,
        "overtime_reservations_by_category": overtime_reservations_by_category,
        "overtime_hours": overtime_hours,
    }


__all__ = [
    "CategoryValueMap",
    "CategoryShortageAllocationResult",
    "ShortageAllocationResult",
    "calculate_shortage_allocation_by_category",
    "calculate_abandonment_and_overtime",
]
