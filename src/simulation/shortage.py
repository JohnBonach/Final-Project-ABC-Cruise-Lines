"""Overflow allocation helpers for constrained in-house staffing."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.constants import RESERVATION_CATEGORIES
from src.operations.capacity import calculate_capacity_hours
from src.operations.workload import MINUTES_PER_HOUR
from src.validation import (
    FieldValidationError,
    validate_non_negative,
    validate_non_negative_integer,
    validate_positive,
)

CategoryValueMap = dict[str, float]
OverflowAllocationResult = dict[str, CategoryValueMap | float]


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


def calculate_overflow_allocation_by_category(
    demand_by_category: Mapping[str, Any],
    handling_times_minutes: Mapping[str, Any],
    staffing_agents: Any,
    booking_processing_hours_per_agent: Any,
) -> OverflowAllocationResult:
    """Allocate any workload above in-house capacity proportionally by workload share."""

    normalized_demand = _validate_category_value_map(
        demand_by_category,
        field_name="demand_by_category",
    )
    normalized_handling_times = _validate_category_value_map(
        handling_times_minutes,
        field_name="handling_times_minutes",
        allow_zero=False,
    )
    normalized_staffing_agents = validate_non_negative_integer(
        "staffing_agents",
        staffing_agents,
    )
    normalized_processing_hours = validate_positive(
        "booking_processing_hours_per_agent",
        booking_processing_hours_per_agent,
    )

    workload_hours_by_category = {
        category:
            normalized_demand[category]
            * normalized_handling_times[category]
            / MINUTES_PER_HOUR
        for category in RESERVATION_CATEGORIES
    }
    total_workload_hours = sum(workload_hours_by_category.values())
    inhouse_capacity_hours = calculate_capacity_hours(
        normalized_staffing_agents,
        normalized_processing_hours,
    )
    spare_capacity_hours = max(inhouse_capacity_hours - total_workload_hours, 0.0)
    overflow_workload_hours = max(total_workload_hours - inhouse_capacity_hours, 0.0)

    if total_workload_hours > 0.0 and overflow_workload_hours > 0.0:
        overflow_hours_by_category = {
            category:
                workload_hours_by_category[category]
                / total_workload_hours
                * overflow_workload_hours
            for category in RESERVATION_CATEGORIES
        }
    else:
        overflow_hours_by_category = {
            category: 0.0
            for category in RESERVATION_CATEGORIES
        }

    overflow_bookings_by_category = {}
    for category in RESERVATION_CATEGORIES:
        raw_overflow_bookings = (
            overflow_hours_by_category[category]
            * MINUTES_PER_HOUR
            / normalized_handling_times[category]
        )
        overflow_bookings_by_category[category] = min(
            max(raw_overflow_bookings, 0.0),
            normalized_demand[category],
        )
    inhouse_bookings_by_category = {
        category: max(
            normalized_demand[category] - overflow_bookings_by_category[category],
            0.0,
        )
        for category in RESERVATION_CATEGORIES
    }

    return {
        "workload_hours_by_category": workload_hours_by_category,
        "total_workload_hours": total_workload_hours,
        "inhouse_capacity_hours": inhouse_capacity_hours,
        "spare_capacity_hours": spare_capacity_hours,
        "overflow_workload_hours": overflow_workload_hours,
        "overflow_hours_by_category": overflow_hours_by_category,
        "overflow_bookings_by_category": overflow_bookings_by_category,
        "inhouse_bookings_by_category": inhouse_bookings_by_category,
    }


__all__ = [
    "CategoryValueMap",
    "OverflowAllocationResult",
    "calculate_overflow_allocation_by_category",
]
