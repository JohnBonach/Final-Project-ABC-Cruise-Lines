"""Deterministic workload calculations for reservation demand."""

from __future__ import annotations

from collections.abc import Mapping

from src.constants import RESERVATION_CATEGORIES
from src.validation import validate_non_negative, validate_positive

MINUTES_PER_HOUR = 60.0


def _normalize_category_mapping(
    field_name: str,
    values: Mapping[str, float],
) -> dict[str, float]:
    """Validate exact canonical categories and return values in shared order."""

    actual_categories = set(values)
    expected_categories = set(RESERVATION_CATEGORIES)

    if actual_categories != expected_categories:
        missing = sorted(expected_categories - actual_categories)
        unexpected = sorted(actual_categories - expected_categories)
        problems: list[str] = []
        if missing:
            problems.append(f"missing categories: {missing}")
        if unexpected:
            problems.append(f"unexpected categories: {unexpected}")
        details = ", ".join(problems)
        raise ValueError(
            f"{field_name} must contain exactly the canonical reservation categories ({details})"
        )

    return {
        category: float(values[category])
        for category in RESERVATION_CATEGORIES
    }


def calculate_workload_minutes_by_category(
    demand_by_category: Mapping[str, float],
    handling_times_minutes: Mapping[str, float],
) -> dict[str, float]:
    """Convert weekly demand into workload minutes for each reservation category."""

    normalized_demand = _normalize_category_mapping(
        "demand_by_category",
        demand_by_category,
    )
    normalized_handling_times = _normalize_category_mapping(
        "handling_times_minutes",
        handling_times_minutes,
    )

    workload_minutes_by_category: dict[str, float] = {}
    for category in RESERVATION_CATEGORIES:
        demand = validate_non_negative(
            f"demand_by_category[{category!r}]",
            normalized_demand[category],
        )
        handling_time = validate_positive(
            f"handling_times_minutes[{category!r}]",
            normalized_handling_times[category],
        )
        workload_minutes_by_category[category] = demand * handling_time

    return workload_minutes_by_category


def calculate_workload_hours_by_category(
    demand_by_category: Mapping[str, float],
    handling_times_minutes: Mapping[str, float],
) -> dict[str, float]:
    """Convert weekly demand into workload hours for each reservation category."""

    workload_minutes_by_category = calculate_workload_minutes_by_category(
        demand_by_category,
        handling_times_minutes,
    )
    return {
        category: workload_minutes / MINUTES_PER_HOUR
        for category, workload_minutes in workload_minutes_by_category.items()
    }


def calculate_workload_hours(
    demand_by_category: Mapping[str, float],
    handling_times_minutes: Mapping[str, float],
) -> float:
    """Calculate total weekly workload hours across all reservation categories."""

    workload_hours_by_category = calculate_workload_hours_by_category(
        demand_by_category,
        handling_times_minutes,
    )
    return sum(workload_hours_by_category.values())


__all__ = [
    "MINUTES_PER_HOUR",
    "calculate_workload_hours",
    "calculate_workload_hours_by_category",
    "calculate_workload_minutes_by_category",
]
